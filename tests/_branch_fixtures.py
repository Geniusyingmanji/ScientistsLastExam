"""Small test-owned protocol fixtures, independent of either task inventory.

Historical infrastructure tests used certified optimization packages merely to
obtain TaskSpec objects. These aliases retain their test identifiers while owning
all source locally: there are no scientific optimization implementations, records,
anchors, or registry additions here. Unknown names still use the real registry,
so missing scientific tasks never silently become fixtures.
"""
import atexit
import tempfile
from dataclasses import replace
from pathlib import Path

from sle.registry import find_task as _registered_task
from sle.spec import load_task_spec


_ALIASES = {
    "LennardJonesCluster": ("Chemistry", "Chemistry", "optimize_cluster"),
    "CapSet": ("Mathematics", "Mathematics", "construct_cap_set"),
    "DiffractionGratingDesign": ("Physics", "Optics", "design_grating"),
    "InvertedPendulumSwingUp": ("Engineering", "ControlTheory", "control_pendulum"),
    "ElectrolyteConductivityDesign": ("Chemistry", "Electrochemistry", "design_electrolyte"),
}
_temporary = tempfile.TemporaryDirectory(prefix="sle_protocol_fixtures_")
atexit.register(_temporary.cleanup)
_specs = {}


def find_task(name, include_uncertified=False):
    bare = name.split("/")[-1]
    if bare not in _ALIASES:
        return _registered_task(name, include_uncertified=include_uncertified)
    if bare in _specs:
        return replace(_specs[bare], metadata=dict(_specs[bare].metadata))
    discipline, domain, entrypoint = _ALIASES[bare]
    root = Path(_temporary.name) / discipline / bare
    (root / "frontier_eval").mkdir(parents=True)
    (root / "verification").mkdir()
    (root / "Task.md").write_text("# Protocol fixture\nReturn a finite scalar. No scientific claim is measured.\n")
    (root / "TASK_CARD.yaml").write_text("schema_version: 2\nscientific_question: Test runtime accounting only.\n")
    (root / "solution.py").write_text("def %s(context):\n    return 0.0\n" % entrypoint)
    (root / "frontier_eval/entrypoint.txt").write_text(entrypoint + "\n")
    (root / "frontier_eval/constraints.txt").write_text("Return a finite scalar.\n")
    (root / "frontier_eval/metadata.yaml").write_text(
        "domain: %s\nscientific_role: sandbox_fixture\nscore_mode: clipped\ndifficulty: unmeasured\n" % domain)
    (root / "verification/evaluator.py").write_text(
        "def evaluate(candidate):\n"
        "    value = float(candidate({'probe': 1}))\n"
        "    return {'combined_score': value, 'valid': 1.0, 'raw_score': value, "
        "'robustness_score': 0.25, 'per_scenario': [{'probe': 1}]}\n")
    _specs[bare] = load_task_spec(root)
    return replace(_specs[bare], metadata=dict(_specs[bare].metadata))
