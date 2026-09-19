"""An upstream timeout must not erase a planned evaluation from the trajectory."""
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from sle.algorithms import openevolve_backend as adapter
from sle.llm import LLMClient, LLMConfig
from sle.metric_visibility import (
    EvaluationInfrastructureError, require_healthy_evaluations, store_full_metrics,
)
from sle.protocol import load_trajectory, sha256_text
from _branch_fixtures import find_task


@pytest.mark.parametrize("missing", ["baseline", "proposal", None])
def test_reconstruction_requires_every_trusted_sidecar(tmp_path, monkeypatch, missing):
    spec = find_task("Mathematics/CapSet")
    baseline = spec.initial_program_path.read_text()
    programs = [
        NS(id="baseline", code=baseline, iteration_found=0, timestamp=0,
           parent_id=None, metrics={"combined_score": .1, "valid": 1.0}),
        NS(id="proposal", code="def build_capset(n): return [1]\n",
           iteration_found=1, timestamp=1, parent_id="baseline",
           metrics={"combined_score": .6, "valid": 1.0}),
        NS(id="later", code="def build_capset(n): return [2]\n",
           iteration_found=2, timestamp=2, parent_id="proposal",
           metrics={"combined_score": .8, "valid": 1.0}),
    ]
    for program in programs:
        if program.id == missing:
            # This is the persisted upstream record when its evaluator times out.
            program.metrics = {"error": 0.0, "timeout": True}

    def config():
        return NS(max_code_length=10000, database=NS(), evaluator=NS(),
                  prompt=NS(), llm=NS())

    class Controller:
        def __init__(self, **kwargs):
            self.workdir = Path(kwargs["output_dir"]).parent
            self.database = NS(programs={program.id: program for program in programs})

        async def run(self, **kwargs):
            for program in programs:
                if program.id != missing:
                    candidate = self.workdir / (program.id + ".py")
                    candidate.write_text(program.code)
                    store_full_metrics(self.workdir / "trusted_full_metrics",
                                       candidate, program.metrics)
            return programs[-1]

    monkeypatch.setattr(adapter, "_load_openevolve",
                        lambda: (config, Controller, lambda **kwargs: NS(**kwargs), {}))
    llm = LLMClient(LLMConfig(model="fixture"))
    kwargs = dict(budget=2, workdir=tmp_path, log_fn=lambda _: None)
    if missing is not None:
        with pytest.raises(EvaluationInfrastructureError, match="missing its trusted metric sidecar"):
            adapter.openevolve(spec, llm, **kwargs)
        for name in ("trajectory.jsonl", "summary.json", "best_program.py"):
            assert not (tmp_path / name).exists()
        private = tmp_path / "trusted_full_metrics"
        markers = list((private / "infrastructure_failures").glob("*.json"))
        assert len(markers) == 1
        marker = json.loads(markers[0].read_text())
        assert marker["reason"] == "missing_trusted_metric_sidecar"
        assert marker["upstream_program_id"] == missing
        with pytest.raises(EvaluationInfrastructureError):
            require_healthy_evaluations(private)
    else:
        result = adapter.openevolve(spec, llm, **kwargs)
        events = load_trajectory(tmp_path / "trajectory.jsonl")
        assert [event["step"] for event in events] == [0, 1, 2]
        assert [event["algorithm_metadata"]["upstream_iteration"] for event in events] == [0, 1, 2]
        assert events[0]["candidate_sha256"] == sha256_text(baseline)
        assert result.baseline_score == .1
        assert result.best_score == .8
        assert result.evaluated == 3
        assert result.summary["upstream_unevaluated_programs"] == 0
        assert (tmp_path / "best_program.py").read_text() == programs[-1].code
        assert (tmp_path / "summary.json").is_file()
