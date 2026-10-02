import json

import pytest

from env.analysis_api import PROTOCOL, contract
from env.campaign import create_manifest, run_cohort


def test_snapshot_protocol_is_explicit_and_frozen():
    legacy = create_manifest("legacy", ["ising_spin"], instances=1)
    assert legacy["analysis_protocol"] == "legacy"
    assert legacy["analysis_contract"] is None
    saved = create_manifest("saved", ["ising_spin"], instances=1,
                            presentation_profile="apparatus_only", analysis_protocol=PROTOCOL)
    assert saved["analysis_contract"] == contract()
    assert saved["instances"][0]["analysis_protocol"] == PROTOCOL
    with pytest.raises(ValueError, match="unsupported analysis"):
        create_manifest("unknown", ["ising_spin"], instances=1, analysis_protocol="latest")


@pytest.mark.parametrize("change", ["contract", "instance"])
def test_snapshot_manifest_drift_fails_before_ledger_or_network(tmp_path, change):
    manifest = create_manifest("drift", ["ising_spin"], instances=1, analysis_protocol=PROTOCOL)
    if change == "contract":
        manifest["analysis_contract"]["limits"]["snapshots"] += 1
    else:
        manifest["instances"][0]["analysis_protocol"] = "legacy"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    root = tmp_path / "not-created"
    with pytest.raises(ValueError, match="analysis (contract|protocol)"):
        run_cohort(path, tmp_path / "no-config.json", root)
    assert not root.exists()
