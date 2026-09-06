"""Executable validity checks for the five biology expansion prototypes."""
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

TASKS=(
    ("MetabolicStrainDesign","design_strain","reference_design.py"),
    ("BatchEffectDiscovery","analyze_expression","reference_analysis.py"),
    ("MetagenomeCompositionAssignment","assign_composition","reference_assignment.py"),
    ("FedBatchBioprocessDesign","design_process","reference_design.py"),
    ("PhylogeneticParsimonySearch","build_tree","reference_search.py"),
)

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
            self.assertGreater(reference["combined_score"],0.35,task)

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
        for task,entry,ref in TASKS[1:3]:
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
        for task in ("BatchEffectDiscovery","MetagenomeCompositionAssignment"):
            self.assertTrue(keys<=set(self.loaded[task][3]),task)

    def test_blanket_abstention_scores_zero(self):
        batch=self.loaded["BatchEffectDiscovery"][0]
        b=batch.evaluate(lambda problem,measure:{"discoveries":[],"abstain":True,"reason_code":"not_identifiable"})
        meta=self.loaded["MetagenomeCompositionAssignment"][0]
        m=meta.evaluate(lambda problem,sequence:{"taxa":[],"ambiguous_groups":[],"abstain":True})
        self.assertEqual(b["combined_score"],0.0)
        self.assertEqual(m["combined_score"],0.0)

    def test_metabolic_worst_case_face_requires_blocking_all_competing_routes(self):
        ev=self.loaded["MetabolicStrainDesign"][0]
        # Independent two-pool fixture: either redox drain can evade product
        # coupling, so a favorable single FBA optimum must not receive credit.
        p={"reaction_ids":["up","biomass","product","drain_a","drain_b"],
           "stoichiometric_matrix":[[1,-1,-1,0,0],[1,-.2,-2,-1,-1]],
           "lower_bounds":[0]*5,"upper_bounds":[10,100,100,100,100],
           "biomass_reaction":"biomass","product_reaction":"product",
           "minimum_growth":1.,"growth_optimality_tolerance":1e-7}
        competitors=["drain_a","drain_b"]
        self.assertEqual(ev._utility(p,()),0.0)
        self.assertEqual(ev._utility(p,tuple(competitors[:-1])),0.0)
        self.assertGreater(ev._utility(p,tuple(competitors)),0.0)

    def test_metabolic_structural_shortcuts_cannot_saturate(self):
        ev=self.loaded["MetabolicStrainDesign"][0]
        def rule(p, mode):
            pairs=zip(p["reaction_ids"],zip(*p["stoichiometric_matrix"]))
            return {"reaction_knockouts":[r for r,c in pairs
                    if r in p["allowed_reaction_knockouts"] and
                    (all(v<=0 for v in c) if mode=="drains" else c[0]==0 and c[1]<0)]}
        for mode in ("drains","redox"):
            metrics=ev.evaluate(lambda p:rule(p,mode))
            self.assertEqual(metrics["valid"],1.0)
            self.assertLess(metrics["combined_score"],.9)
            self.assertLess(metrics["heldout_score"],.9)

    def test_metabolic_fixed_positions_do_not_transfer(self):
        ev=self.loaded["MetabolicStrainDesign"][0]
        fixed=ev.evaluate(lambda p:{"reaction_knockouts":p["allowed_reaction_knockouts"][:4]})
        self.assertLess(fixed["combined_score"],0.5)
        self.assertLess(fixed["heldout_score"],0.5)

    def test_batch_scores_effects_and_reason_codes(self):
        ev=self.loaded["BatchEffectDiscovery"][0]
        ref=load(BIO/"BatchEffectDiscovery"/"verification"/"reference_analysis.py","batch_mut_ref")
        def zero_effect(problem,measure):
            out=ref.analyze_expression(problem,measure)
            out["discoveries"]=[{**row,"effect":0.0} for row in out["discoveries"]]
            return out
        def wrong_reason(problem,measure):
            out=ref.analyze_expression(problem,measure)
            out["reason_code"]="supported"
            return out
        reference=self.loaded["BatchEffectDiscovery"][3]
        self.assertLess(ev.evaluate(zero_effect)["combined_score"],reference["combined_score"])
        self.assertLess(ev.evaluate(wrong_reason)["combined_score"],reference["combined_score"])

    def test_batch_confounded_world_has_no_cross_cell(self):
        ev=self.loaded["BatchEffectDiscovery"][0]; lab=ev._Lab("confounded",103)
        self.assertEqual(lab.available,[[0,0],[1,1]])
        with self.assertRaises(ValueError): lab(1,0)

    def test_batch_sampling_layout_does_not_disclose_effect_presence(self):
        ev=self.loaded["BatchEffectDiscovery"][0]
        layouts=[]
        for kind in ("supported","null","confounded"):
            rows=ev._initial(kind,101)
            layouts.append([(r["batch"],r["condition"],r["library_size"]) for r in rows])
        self.assertEqual(layouts[0],layouts[1])
        self.assertEqual(layouts[0],layouts[2])
        self.assertEqual(ev._Lab("supported",101).available,ev._Lab("null",101).available)

    def test_batch_no_discovery_policies_score_zero(self):
        ev=self.loaded["BatchEffectDiscovery"][0]
        def deny(p,measure):
            return {"discoveries":[],"abstain":False,"reason_code":"no_effect"}
        def layout_only(p,measure):
            confounded=len(p["available_cells"])<3
            return {"discoveries":[],"abstain":confounded,
                    "reason_code":"not_identifiable" if confounded else "no_effect"}
        for candidate in (deny,layout_only):
            self.assertEqual(ev.evaluate(candidate)["combined_score"],0.0)

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

    def test_fedbatch_rejects_malformed_schedule_values_without_crashing(self):
        ev=self.loaded["FedBatchBioprocessDesign"][0]
        bad_rates=([[.1],[.1],[.1]],[[],[],[]],[[.1,.2]]*3,[],[.1],
                   [.1]*4,[True,.1,.1],[".1",.1,.1],[None,.1,.1],
                   [float("nan"),.1,.1],[float("inf"),.1,.1],[-.1,.1,.1],[1.,.1,.1])
        for rates in bad_rates:
            result=ev.evaluate(lambda p:{"feed_rates":rates,"induction_time_h":10.,"harvest_time_h":20.})
            self.assertEqual(result["valid"],0.0,repr(rates))
            self.assertEqual(result["combined_score"],0.0,repr(rates))

    def test_task_entrypoints_start_without_pythonpath_from_another_directory(self):
        env=dict(os.environ)
        env.pop("PYTHONPATH",None)
        with tempfile.TemporaryDirectory() as tmp:
            for task,_,_ in TASKS:
                result=subprocess.run([sys.executable,"-I",str(BIO/task/"frontier_eval/run_eval.py"),"--help"],
                                      cwd=tmp,env=env,capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn("--candidate",result.stdout)

    def test_fedbatch_fixed_schedule_does_not_transfer(self):
        ev=self.loaded["FedBatchBioprocessDesign"][0]
        ref=load(BIO/"FedBatchBioprocessDesign"/"verification"/"reference_design.py","fed_fixed_ref")
        cached=[]
        def fixed(problem):
            if not cached: cached.append(ref.design_process(problem))
            return cached[0]
        self.assertLess(ev.evaluate(fixed)["combined_score"],0.5)

    def test_phylogenetic_fitch_is_leaf_order_invariant(self):
        ev=self.loaded["PhylogeneticParsimonySearch"][0]; p=ev._problem(501)
        taxa=p["taxa"]; left=ev._caterpillar(taxa)
        # Swapping the two children at the final root preserves the same unrooted topology.
        inner=left[:-1]
        split=inner.rfind(",")
        swapped="("+inner[split+1:-1]+","+inner[1:split]+");"
        self.assertEqual(ev._fitch(left,p),ev._fitch(swapped,p))

    def test_phylogenetic_score_has_measured_headroom(self):
        ev=self.loaded["PhylogeneticParsimonySearch"][0]
        probe=load(BIO/"PhylogeneticParsimonySearch"/"verification"/"headroom_probe.py","phylo_headroom")
        metrics=ev.evaluate(probe.build_tree)
        self.assertGreater(metrics["combined_score"],1.0)
        self.assertGreater(metrics["heldout_score"],1.0)

if __name__=="__main__":
    unittest.main()
