"""Real sandbox plumbing for all twelve worlds; scripted client, no API calls."""
import shutil
import sys

import pytest

from env.registry import load_world
from env.runner import DEFAULT_LIMITS, run_episode
from env.unified_campaign import ENVIRONMENTS
from env.unified_scoring import PROTOCOL
from env.unified_panels import generate_panel
from env.scoring import canonical_hash
from env.tests.test_pilot_protocol import FakeClient
from env.analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL


@pytest.mark.skipif(sys.platform != "linux" or shutil.which("bwrap") is None,
                    reason="real candidate isolation requires Linux and bubblewrap")
@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_real_world_analysis_and_frozen_prediction(environment, tmp_path):
    world, _ = load_world(environment, 61913)
    spec = world.panel(71513, "development", 1)[0]
    predictor = "def predict(spec):\n    return [[0.0] * %d for _ in spec[%r]]\n" % (len(world.channels), world.axis_field)
    client = FakeClient([
        {"note":"Plumbing observation, not a scientific baseline.", "experiments":[spec]},
        {"note":"Read public data in real isolated analysis.",
         "analyze":{"code":"import numpy as np\nresult = {'rows': len(records[0]['observation']['values']), 'finite': bool(np.isfinite(records[0]['observation']['values']).all())}"}},
        {"note":"Freeze a constant predictor for plumbing only.",
         "submit":{"predictor_code":predictor,"claims":[],"explanation":"Engineering smoke, not model scientific evidence."}},
    ])
    instance=dict(episode_id="native-"+environment,environment=environment,world_seed=61913,
                  panel_seed=71514,confirmation_key="native-check-only",scoring_protocol=PROTOCOL,
                  analysis_protocol=SNAPSHOT_PROTOCOL)
    instance["panel_hashes"]={k:canonical_hash(generate_panel(world,71514,k,1)) for k in ("conditions","interventions")}
    limits=dict(DEFAULT_LIMITS,rounds=3,exploration_rounds=2,panel_count=1,
                experiment_units=30000,analysis_active_seconds=60,wall_seconds=180,
                verification_reserve_seconds=30)
    report=run_episode(instance,limits,tmp_path,client)
    assert report["status"] == "completed", report.get("stop_reason")
    assert report["history"][1]["analysis"]["ok"]
    assert report["history"][1]["analysis"]["result"]["finite"]
    assert all(r["valid"] for rows in report["panels"].values() for r in rows)
    assert report["subscores"]["claims"] == 0
