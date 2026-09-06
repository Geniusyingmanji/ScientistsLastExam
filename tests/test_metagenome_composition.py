"""Executable validity checks for the first biology expansion prototypes."""
from __future__ import annotations
import importlib.util
import sys
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BIO=ROOT/"benchmarks/Biology"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

TASKS=(('MetagenomeCompositionAssignment', 'assign_composition', 'reference_assignment.py'),)

class BiologyExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded={}
        for task,entry,refname in TASKS:
            ev=load(BIO/task/"verification/evaluator.py","ev_"+task)
            base=load(BIO/task/"solution.py","base_"+task)
            ref=load(BIO/task/"verification"/refname,"ref_"+task)
            cls.loaded[task]=(ev,entry,ev.evaluate(getattr(base,entry)),ev.evaluate(getattr(ref,entry)))

    def test_baselines_are_valid_zero_and_references_improve(self):
        for task,(_,_,baseline,reference) in self.loaded.items():
            self.assertEqual(baseline["valid"],1.0,task)
            self.assertAlmostEqual(baseline["combined_score"],0.0,places=12,msg=task)
            self.assertEqual(reference["valid"],1.0,task)
            self.assertGreaterEqual(reference["combined_score"],0.5,task)
            self.assertLessEqual(reference["combined_score"],0.8,task)

    def test_evaluators_are_deterministic(self):
        for task,entry,refname in TASKS:
            ev=load(BIO/task/"verification/evaluator.py","det_ev_"+task)
            ref=load(BIO/task/"verification"/refname,"det_ref_"+task)
            one=ev.evaluate(getattr(ref,entry)); two=ev.evaluate(getattr(ref,entry))
            self.assertEqual(one,two,task)

    def test_discovery_metrics_do_not_depend_on_process_hash_seed(self):
        script="""
import importlib.util, json, pathlib, sys
def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
root=pathlib.Path(sys.argv[1]); entry=sys.argv[2]
ev=load(root/'verification/evaluator.py','ev')
base=load(root/'solution.py','base')
ref=load(root/'verification'/sys.argv[3],'ref')
print(json.dumps([ev.evaluate(getattr(base,entry)),ev.evaluate(getattr(ref,entry))],sort_keys=True))
"""
        for task,entry,ref in TASKS:
            results=[]
            for seed in ("1","2","7"):
                env={**os.environ,"PYTHONHASHSEED":seed,"OPENBLAS_NUM_THREADS":"1"}
                results.append(subprocess.check_output(
                    [sys.executable,"-c",script,str(BIO/task),entry,ref],env=env,text=True,timeout=30))
            self.assertEqual(results,[results[0]]*len(results),task)

    def test_malformed_candidates_fail_closed(self):
        bad=(lambda *args:{},lambda *args:None,lambda *args:"bad",lambda *args:[],
             lambda *args:{"unexpected":1},lambda *args:float("nan"),
             lambda *args:(_ for _ in ()).throw(RuntimeError("boom")))
        for task,(ev,_,_,_) in self.loaded.items():
            for candidate in bad:
                metrics=ev.evaluate(candidate)
                self.assertEqual(metrics["valid"],0.0,task)
                self.assertEqual(metrics["combined_score"],0.0,task)

    def test_discovery_tasks_publish_axes_and_denominators(self):
        keys={"development_mechanism_score","development_false_discovery_rate",
              "development_false_discovery_count","development_unsupported_claim_count",
              "development_correct_refusal_rate","development_discovery_coverage"}
        for task in ('MetagenomeCompositionAssignment',):
            self.assertTrue(keys<=set(self.loaded[task][3]),task)

    def test_blanket_abstention_scores_zero(self):
        ev=self.loaded['MetagenomeCompositionAssignment'][0]
        self.assertEqual(ev.evaluate(lambda p, callback: {"taxa":[],"ambiguous_groups":[],"abstain":True})["combined_score"],0.)

    def test_metagenome_alias_columns_are_identical_and_outlier_marker_is_external(self):
        ev=self.loaded["MetagenomeCompositionAssignment"][0]
        np.testing.assert_allclose(ev.REF[:,0],ev.REF[:,1])
        self.assertTrue(np.all(ev.REF[-1,:]==0))
        self.assertGreater(ev._truth("out_of_library",33)[2][-1],0.2)

    def test_metagenome_rejects_broad_aliases_and_scores_alias_abundance(self):
        ev=self.loaded["MetagenomeCompositionAssignment"][0]
        broad=ev.evaluate(lambda problem,sequence:{
            "taxa":[],"ambiguous_groups":[problem["taxon_ids"]],"abstain":False})
        self.assertEqual(broad["valid"],0.0)
        ref=load(BIO/"MetagenomeCompositionAssignment"/"verification"/"reference_assignment.py","meta_mut_ref")
        def wrong_abundance(problem,sequence):
            out=ref.assign_composition(problem,sequence)
            for row in out["taxa"]:
                row["abundance"]=0.0
            return out
        self.assertLess(ev.evaluate(wrong_abundance)["combined_score"],
                        self.loaded["MetagenomeCompositionAssignment"][3]["combined_score"])

    def test_metagenome_panel_budget_is_real(self):
        ev=self.loaded["MetagenomeCompositionAssignment"][0]
        def over_budget(problem,sequence):
            for panel in problem["available_panels"][:3]:
                sequence(panel)
            return {"taxa":[],"ambiguous_groups":[],"abstain":True}
        metrics=ev.evaluate(over_budget)
        self.assertEqual(metrics["valid"],0.0)
        self.assertEqual(metrics["combined_score"],0.0)

    def test_metagenome_alias_world_penalizes_every_extra_false_taxon(self):
        ev=self.loaded["MetagenomeCompositionAssignment"][0]
        ref=load(BIO/"MetagenomeCompositionAssignment"/"verification/reference_assignment.py","meta_extra_ref")
        def extra(p,sequence):
            out=ref.assign_composition(p,sequence)
            if out["ambiguous_groups"]:
                out["taxa"] += [{"taxon":t,"abundance":.08} for t in ("t3","t4","t5","t6","t7")]
            return out
        metrics=ev.evaluate(extra)
        self.assertEqual(metrics["valid"],1.0)
        self.assertEqual(metrics["development_false_discovery_count"],10)
        self.assertGreater(metrics["development_false_discovery_rate"],0.0)
        self.assertLess(metrics["combined_score"],self.loaded["MetagenomeCompositionAssignment"][3]["combined_score"])
        self.assertLess(metrics["heldout_scientific_score"],self.loaded["MetagenomeCompositionAssignment"][3]["heldout_scientific_score"])

    def test_metagenome_absent_alias_groups_reduce_supported_credit(self):
        ev=self.loaded["MetagenomeCompositionAssignment"][0]
        ref=load(BIO/"MetagenomeCompositionAssignment"/"verification/reference_assignment.py","meta_group_ref")
        def extra(p,sequence):
            out=ref.assign_composition(p,sequence)
            if not out["abstain"] and not out["ambiguous_groups"]:
                out["ambiguous_groups"]=[["t0","t1"]]
            return out
        clean=ev.evaluate(ref.assign_composition)
        result=ev.evaluate(extra)
        self.assertEqual(result["valid"],1.)
        self.assertLess(result["combined_score"],clean["combined_score"])
        self.assertLess(result["heldout_scientific_score"],clean["heldout_scientific_score"])
        for before,after in zip(clean["per_world"],result["per_world"]):
            if before["kind"]=="supported":
                self.assertEqual(after["false"],before["false"]+1)
                self.assertEqual(after["claimed"],before["claimed"]+1)
                self.assertLess(after["scientific"],before["scientific"])
            else:
                self.assertEqual(before,after)

    def test_metagenome_group_only_claims_count_in_false_discovery_rate(self):
        ev=self.loaded["MetagenomeCompositionAssignment"][0]
        result=ev.evaluate(lambda p,s:dict(taxa=[],ambiguous_groups=[["t0","t1"]],abstain=False))
        self.assertEqual(result["valid"],1.)
        self.assertEqual(result["development_false_discovery_count"],1)
        self.assertEqual(result["development_unsupported_claim_count"],3)
        self.assertAlmostEqual(result["development_false_discovery_rate"],1/3)
        for row in result["per_world"]:
            self.assertEqual(row["claimed"],1)
            self.assertEqual(row["false"],int(row["kind"]!="alias"))
            self.assertEqual(row["scientific"],.5 if row["kind"]=="alias" else 0.)

    def test_task_entrypoints_start_without_pythonpath_from_another_directory(self):
        env=dict(os.environ)
        env.pop("PYTHONPATH",None)
        with tempfile.TemporaryDirectory() as tmp:
            for task,_,_ in TASKS:
                result=subprocess.run([sys.executable,"-I",str(BIO/task/"frontier_eval/run_eval.py"),"--help"],
                                      cwd=tmp,env=env,capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn("--candidate",result.stdout)
