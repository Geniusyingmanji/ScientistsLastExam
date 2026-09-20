"""Frozen cleaning, source lineage and privacy checks for an observational import."""
from datetime import datetime, timedelta
import csv
import io
from pathlib import Path
import tempfile
import unittest

from benchmarks.ComputerScience.MeasurementAudit.verification.episode import load_bundle
from scripts.prepare_beijing_measurement_pilot import (
    COLUMNS, SOURCE_FIELDS, create_private_root, digest, json_bytes, manifest,
    parse_source, transform,
)


def source_csv(blocks):
    """Synthetic parser fixtures only; never represented as measured science."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(SOURCE_FIELDS)
    number = 0
    for start, hours, pm_count, wind in blocks:
        for hour in range(hours):
            number += 1
            when = start + timedelta(hours=hour)
            direction = wind(hour) if callable(wind) else wind
            writer.writerow([number, when.year, when.month, when.day, when.hour,
                             10 if hour < pm_count else "NA", -1, 5, 1010,
                             direction, 0, 0, 0])
    return output.getvalue().encode("utf-8")


def read_derived(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


class BeijingPilotTests(unittest.TestCase):
    def test_coverage_threshold_does_not_impute_or_use_outcome_magnitude(self):
        raw = source_csv([(datetime(2010, 1, 1), 168, 126, "NW"),
                          (datetime(2010, 1, 8), 168, 125, "SE")])
        data, counts, lineage = transform(raw)
        self.assertEqual(len(read_derived(data)), 1)
        self.assertEqual(float(read_derived(data)[0]["pm_mean"]), 10)
        self.assertEqual(counts["excluded_blocks_by_first_reason"]["pm_coverage_below_126"], 1)
        self.assertEqual(counts["retained_pm_missing_hours"], 42)
        changed = raw.replace(b",10,-1,", b",9999,-1,")
        changed_data, changed_counts, changed_lineage = transform(changed)
        self.assertEqual(counts, changed_counts)
        self.assertEqual(lineage, changed_lineage)
        self.assertEqual(float(read_derived(changed_data)[0]["pm_mean"]), 9999)

    def test_embargo_is_bilateral_whole_block_and_end_is_exclusive(self):
        starts = [datetime(2012, 1, 1) + timedelta(days=7 * n) for n in (49, 50, 51)]
        starts += [datetime(2013, 1, 1), datetime(2013, 1, 8), datetime(2013, 1, 15)]
        _, counts, lineage = transform(source_csv([(start, 168, 168, "NW") for start in starts]))
        actual = {row["start_inclusive"]: row for row in lineage if row["source_row_ids"]}
        for start in starts:
            row = actual[start.isoformat()]
            excluded = datetime(2012, 12, 11) < start < datetime(2013, 1, 15)
            self.assertEqual(row["retained"], not excluded)
            if excluded:
                self.assertEqual(row["exclusion_reason"], "boundary_embargo")
        self.assertEqual(counts["partition_counts"], {"exploration": 1, "replication": 1})

    def test_incomplete_calendar_and_missing_hour_are_different_exclusions(self):
        raw = source_csv([(datetime(2010, 1, 1), 167, 167, "NW"),
                          (datetime(2010, 12, 31), 24, 24, "SE")])
        _, counts, lineage = transform(raw)
        found = {r["start_inclusive"]: r for r in lineage}
        self.assertEqual(found["2010-01-01T00:00:00"]["exclusion_reason"], "incomplete_hourly_grid")
        self.assertEqual(found["2010-12-31T00:00:00"]["exclusion_reason"], "incomplete_calendar_block")
        self.assertEqual(counts["source_rows"], sum(counts["excluded_source_rows_by_first_reason"].values()))

    def test_wind_tie_is_mixed_and_source_rows_never_overlap(self):
        raw = source_csv([(datetime(2010, 1, 1), 168, 168, lambda hour: "NW" if hour < 84 else "SE"),
                          (datetime(2010, 1, 8), 168, 168, "SE")])
        data, _, lineage = transform(raw)
        self.assertEqual([int(r["wind_regime"]) for r in read_derived(data)], [2, 1])
        retained = [r for r in lineage if r["retained"]]
        self.assertFalse(set(retained[0]["source_row_ids"]) & set(retained[1]["source_row_ids"]))
        self.assertEqual(len(retained[0]["source_row_ids"]), 168)
        self.assertIn("pm2.5", retained[0]["source_columns"])
        self.assertIn("cbwd", retained[0]["source_columns"])
        self.assertEqual([c["name"] for c in COLUMNS], ["year", "season_code", "pm_mean", "wind_regime"])

    def test_reject_duplicate_identifier_timestamp_and_invalid_observation(self):
        raw = source_csv([(datetime(2010, 1, 1), 168, 168, "NW")])
        rows = raw.decode().splitlines()
        duplicate_id = rows[2].split(",")
        duplicate_id[0] = "1"
        duplicate_time = rows[1].split(",")
        duplicate_time[0] = "999"
        for replacement in (",".join(duplicate_id), ",".join(duplicate_time), rows[2].replace(",10,-1,", ",nan,-1,"),
                            rows[2].replace(",NW,", ",UNKNOWN,")):
            invalid = ("\n".join(rows[:2] + [replacement] + rows[3:]) + "\n").encode()
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                parse_source(invalid)

    def test_byte_determinism_and_actual_adapter_compatibility(self):
        raw = source_csv([(datetime(2010, 1, 1), 336, 336, "NW"),
                          (datetime(2013, 1, 15), 336, 336, "SE")])
        data, counters, lineage = transform(raw)
        self.assertEqual((data, counters, lineage), transform(raw))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve()
            (path / "measurements.csv").write_bytes(data)
            (path / "manifest.json").write_bytes(json_bytes(manifest(data, digest(raw), "a" * 64)))
            _manifest, rows, binding = load_bundle(path)
        self.assertEqual({p: len(v) for p, v in rows.items()}, {"exploration": 2, "replication": 2})
        self.assertEqual(binding["ground_truth"], "absent")
        self.assertEqual(binding["provenance"]["replication_design"], "held_out_same_source")

    def test_output_is_private_new_and_outside_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = create_private_root(parent / "private")
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_private_root(root)
            (parent / ".git").mkdir()
            with self.assertRaisesRegex(ValueError, "outside every Git"):
                create_private_root(parent / "forbidden")
        with self.assertRaisesRegex(ValueError, "outside every Git"):
            create_private_root(Path(__file__).resolve().parents[1] / "not-allowed-pilot-data")


if __name__ == "__main__":
    unittest.main()
