from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Photovoltaics/PhotovoltaicTandemDesign"
DATA = TASK / "verification/astm_g173_v1.json"
DATA_SHA256 = "eeb37120e14ad2fbb5e986d63b5f7711fbf622a03ebf67edabea618df397a728"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "photovoltaic_test_oracle")
BUILDER = _load(
    ROOT / "scripts/build_photovoltaic_spectrum_data.py",
    "photovoltaic_test_builder",
)
CALIBRATION = _load(
    ROOT / "scripts/calibrate_photovoltaic_tandem.py",
    "photovoltaic_test_calibration",
)
ADMISSION = _load(
    ROOT / "scripts/audit_candidate_wave6.py",
    "photovoltaic_test_admission",
)


def _independent_ideal_efficiency(gaps_ev):
    """Independent infinite-absorber radiative detailed-balance integration."""
    document = json.loads(DATA.read_text(encoding="utf-8"))
    rows = np.asarray(document["rows"], dtype=float)
    wavelength_nm = rows[:, 0]
    irradiance = rows[:, 2]
    wavelength_m = wavelength_nm * 1.0e-9
    h = 6.62607015e-34
    c = 299792458.0
    q = 1.602176634e-19
    k = 1.380649e-23
    energy_ev = 1239.8419843320026 / wavelength_nm
    photon_flux = irradiance / (energy_ev * q)
    blackbody = (
        2.0 * math.pi * c / wavelength_m**4
        / np.expm1(np.clip(h * c / (wavelength_m * k * 300.0), 0.0, 700.0))
        * 1.0e-9
    )
    transmission = np.ones_like(wavelength_nm)
    jsc = []
    j0 = []
    for gap in gaps_ev:
        absorbs = (energy_ev >= float(gap)).astype(float)
        accepted = transmission * absorbs
        jsc.append(q * float(np.trapz(photon_flux * accepted, wavelength_nm)))
        j0.append(q * float(np.trapz(blackbody * absorbs, wavelength_nm)))
        transmission *= 1.0 - absorbs
    jsc = np.asarray(jsc)
    j0 = np.maximum(np.asarray(j0), 1e-300)
    thermal_voltage = k * 300.0 / q

    def derivative(current):
        voltage = thermal_voltage * np.sum(np.log1p((jsc - current) / j0))
        voltage_slope = -thermal_voltage * np.sum(
            1.0 / (j0 + jsc - current)
        )
        return float(voltage + current * voltage_slope)

    current = brentq(
        derivative,
        0.0,
        float(np.min(jsc)) * (1.0 - 1e-12),
        xtol=1e-12,
        rtol=1e-14,
    )
    voltage = thermal_voltage * np.sum(np.log1p((jsc - current) / j0))
    incident = float(np.trapz(irradiance, wavelength_nm))
    return float(current * voltage) / incident


class PhotovoltaicTandemTests(unittest.TestCase):
    def test_hash_bound_spectrum_provenance_and_exact_builder(self):
        payload = DATA.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), DATA_SHA256)
        document = json.loads(payload.decode("utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(len(document["rows"]), 2002)
        self.assertEqual(document["rows"][0][0], 280.0)
        self.assertEqual(document["rows"][-1][0], 4000.0)
        provenance = document["source_provenance"]
        self.assertEqual(provenance["upstream_release"], "v0.13.1")
        self.assertEqual(provenance["upstream_commit"], BUILDER.UPSTREAM_COMMIT)
        self.assertEqual(provenance["upstream_sha256"], BUILDER.UPSTREAM_SHA256)
        self.assertEqual(provenance["license"], "BSD-3-Clause")
        wavelength = np.asarray([row[0] for row in document["rows"]])
        global_tilt = np.asarray([row[2] for row in document["rows"]])
        self.assertAlmostEqual(
            float(np.trapz(global_tilt, wavelength)),
            1000.3706555734423,
            places=10,
        )
        upstream = Path("/tmp/ASTMG173_pvlib_0.13.1.csv")
        if upstream.is_file():
            self.assertEqual(
                hashlib.sha256(upstream.read_bytes()).hexdigest(),
                BUILDER.UPSTREAM_SHA256,
            )
            rebuilt = BUILDER.build(upstream.read_bytes())
            rebuilt["source_provenance"]["retrieved_at"] = provenance["retrieved_at"]
            rendered = json.dumps(
                rebuilt, separators=(",", ":"), allow_nan=False
            ) + "\n"
            self.assertEqual(rendered.encode("utf-8"), payload)

    def test_independent_ideal_one_through_four_junction_limits(self):
        # Fixed near-optimal gaps on the stored ASTM grid. These reproduce the
        # canonical approximately 33.7/45.8/51.3/55.4 percent progression.
        witnesses = (
            ((1.33720284,), 0.33695),
            ((1.63179147, 0.96009112), 0.45735),
            ((1.79229367, 1.20029685, 0.69869468), 0.51291),
            ((2.00087736, 1.49345882, 1.11424413, 0.71512019), 0.55329),
        )
        observed = []
        for gaps, expected in witnesses:
            value = _independent_ideal_efficiency(gaps)
            observed.append(value)
            self.assertAlmostEqual(value, expected, delta=6e-5)
            oracle_value = ORACLE._device_performance(
                ORACLE.BASE_WAVELENGTH_NM,
                ORACLE.BASE_GLOBAL_IRRADIANCE,
                300.0,
                gaps,
                [1e5] * len(gaps),
            )["efficiency"]
            self.assertAlmostEqual(value, oracle_value, delta=2e-10)
        self.assertTrue(np.all(np.diff(observed) > 0.035))

    def test_absorption_transmission_and_series_current_invariants(self):
        energies = np.linspace(0.3, 3.0, 400)
        below = ORACLE._absorptance(energies[energies < 1.1], 1.1, 2.0)
        self.assertTrue(np.all(below == 0.0))
        for depth in (0.2, 1.0, 3.0, 5.0):
            curve = ORACLE._absorptance(energies, 1.1, depth)
            self.assertTrue(np.all((curve >= 0.0) & (curve <= 1.0)))
            self.assertTrue(np.all(np.diff(curve) >= -1e-15))
        depths = [0.2, 1.0, 3.0, 5.0]
        at_energy = [ORACLE._absorptance(np.asarray([1.8]), 1.1, d)[0] for d in depths]
        self.assertTrue(np.all(np.diff(at_energy) > 0.0))

        performance = ORACLE._device_performance(
            ORACLE.BASE_WAVELENGTH_NM,
            ORACLE.BASE_GLOBAL_IRRADIANCE,
            300.0,
            [1.75, 1.15, 0.72],
            [2.1, 2.7, 3.4],
        )
        currents = performance["short_circuit_currents_a_m2"]
        self.assertGreater(performance["power_w_m2"], 0.0)
        self.assertGreater(performance["operating_current_a_m2"], 0.0)
        self.assertLessEqual(
            performance["operating_current_a_m2"], float(np.min(currents))
        )
        self.assertGreater(performance["operating_voltage_v"], 0.0)
        self.assertGreater(performance["current_matching_ratio"], 0.0)
        self.assertLessEqual(performance["current_matching_ratio"], 1.0)
        self.assertLessEqual(sum(performance["absorbed_power_fractions"]), 1.0 + 1e-12)

    def test_references_have_headroom_and_budget_changes_topology(self):
        baseline = ORACLE.evaluate(ORACLE.baseline_policy)
        nominal = ORACLE.evaluate(ORACLE.nominal_reference_policy)
        robust = ORACLE.evaluate(ORACLE.robust_reference_policy)
        self.assertEqual(len(ORACLE.DEVELOPMENT_SPECS), 5)
        self.assertEqual(len(ORACLE.HELDOUT_SPECS), 3)
        self.assertEqual(len(ORACLE.SHIFT_NAMES), 6)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertEqual(robust["valid"], 1.0)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertGreater(robust["combined_score"], 0.45)
        counts = [
            row["junction_count"]
            for instance in nominal["per_instance"]
            for row in instance["options"]
        ]
        self.assertGreaterEqual(len(set(counts)), 3)
        self.assertLess(min(counts), max(counts))
        nominal_by_option = [set() for _ in range(ORACLE.ARCHIVE_SIZE)]
        robust_by_option = [set() for _ in range(ORACLE.ARCHIVE_SIZE)]
        for instance in nominal["per_instance"]:
            for index, option in enumerate(instance["options"]):
                nominal_by_option[index].add(option["junction_count"])
        for instance in robust["per_instance"]:
            for index, option in enumerate(instance["options"]):
                robust_by_option[index].add(option["junction_count"])
        self.assertEqual(nominal_by_option[0], {1})
        self.assertTrue(nominal_by_option[1].issubset({2, 3}))
        self.assertNotIn(1, nominal_by_option[1])
        self.assertTrue(nominal_by_option[2].issubset({3, 4}))
        self.assertNotIn(1, nominal_by_option[2])
        self.assertEqual(robust_by_option, [{1}, {2}, {3}])
        for instance in nominal["per_instance"]:
            for option in instance["options"]:
                self.assertGreater(
                    option["reference_nominal_efficiency"],
                    option["baseline_nominal_efficiency"] + 1e-8,
                )
        for instance in robust["per_instance"]:
            for option in instance["options"]:
                self.assertGreater(
                    option["reference_worst_shift_efficiency"],
                    option["baseline_worst_shift_efficiency"] + 1e-8,
                )

    def test_malformed_nonfinite_complex_duplicate_and_overbudget_fail_closed(self):
        def baseline(problem):
            return ORACLE.baseline_policy(problem)

        factories = (
            lambda problem: {"designs": []},
            lambda problem: {
                "designs": [{"bandgaps_ev": [np.nan], "optical_depths": [1.0]}] * 3
            },
            lambda problem: {
                "designs": [{"bandgaps_ev": [1.1 + 1e-3j], "optical_depths": [1.0]}] * 3
            },
            lambda problem: {
                "designs": [baseline(problem)["designs"][0]] * 3
            },
            lambda problem: {
                "designs": [
                    {"bandgaps_ev": [1.0, 1.4], "optical_depths": [0.3, 0.3]},
                    *baseline(problem)["designs"][1:],
                ]
            },
            lambda problem: {
                "designs": [
                    {"bandgaps_ev": [1.1], "optical_depths": [5.0]},
                    *baseline(problem)["designs"][1:],
                ]
            },
            lambda problem: {**baseline(problem), "diagnostic": 1.0},
        )
        for factory in factories:
            metrics = ORACLE.evaluate(factory)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)

    def test_public_problem_and_metrics_seal_private_axes(self):
        forbidden_problem = {
            "seed", "split", "shift", "reference", "baseline",
            "nominal_reference_designs", "robust_reference_designs",
        }
        for spec in ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS:
            problem = ORACLE._public_problem(ORACLE._make_world(spec))
            self.assertTrue(forbidden_problem.isdisjoint(problem))
        shown = search_visible_metrics(ORACLE.evaluate(ORACLE.baseline_policy))
        self.assertEqual(
            set(shown), {"combined_score", "valid", "feasibility_rate", "raw_score"}
        )
        for key in (
            "robustness_score", "heldout_policy_score",
            "development_mean_nominal_efficiency",
            "development_mean_current_matching_ratio",
            "development_mean_junction_count", "per_instance",
        ):
            self.assertNotIn(key, shown)

    def test_secure_baseline_and_fresh_sessions(self):
        spec = find_task(
            "Photovoltaics/PhotovoltaicTandemDesign", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=120)
        self.assertEqual(secure["valid"], 1.0)
        self.assertEqual(secure["combined_score"], 0.0)
        self.assertEqual(secure["candidate_instance_call_count"], 8)

        source = textwrap.dedent("""
            import os
            import numpy as np
            module_counter = 0
            def design_tandem(problem):
                global module_counter
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/photovoltaic-instance-state')
                with open('/tmp/photovoltaic-instance-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_photovoltaic_counter', 0)
                np._photovoltaic_counter = imported_counter + 1
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    raise RuntimeError('state crossed photovoltaic regime')
                designs = []
                for index, cap in enumerate(problem['fabrication_budget_caps']):
                    depth = min(problem['optical_depth_bounds'][1],
                        (cap - problem['junction_overhead_cost']) /
                        problem['optical_depth_cost'])
                    designs.append({'bandgaps_ev': [1.55 + 0.03 * index],
                                    'optical_depths': [depth]})
                return {'designs': designs}
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            isolated = evaluate_candidate(spec, candidate, timeout_s=120)
        self.assertEqual(isolated["valid"], 1.0)
        self.assertEqual(isolated["combined_score"], 0.0)
        self.assertEqual(isolated["candidate_instance_valid_rate"], 1.0)

    def test_calibration_and_admission_gates_execute(self):
        calibration = CALIBRATION.audit()
        self.assertTrue(calibration["execution_passed"], calibration)
        self.assertGreater(calibration["minimum_nominal_headroom"], 0.02)
        self.assertGreater(calibration["minimum_robust_headroom"], 0.02)
        self.assertLess(
            calibration["maximum_independent_runtime_efficiency_gap"], 2e-10
        )
        self.assertEqual(
            calibration["nominal_reference_junction_counts_by_budget_option"],
            [[1], [2, 3], [3, 4]],
        )
        self.assertEqual(
            calibration["robust_reference_junction_counts_by_budget_option"],
            [[1], [2], [3]],
        )
        admission = ADMISSION.audit()
        self.assertTrue(admission["execution_passed"], admission)
        self.assertEqual(
            admission["summary"]["recommended_candidate_count"], 1
        )
        self.assertEqual(
            admission["summary"]["recommended_quarantine_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
