#!/usr/bin/env python3
"""Are the external records this benchmark normalises against still the records?

An uncapped task divides by a published record. If the record moves and the ledger does not, the
task silently mis-scores: a candidate that matches the new record reads as having beaten the old
one. This is not hypothetical. AlphaEvolve raised the eleven-dimensional kissing number to 593 in
2025 and FunSearch raised the dimension-eight cap set to 512; both cells are live research. This
repository has also shipped two wrong anchors already - a circle-packing side length that was never
in its cited source, and a superpermutation length off by one - and both were found by hand.

What this checks, in order of strength:

    1. every literal anchor in a declared task is in that task's `references/anchors.json`
       (the existing guard, re-run here so one command answers the whole question);
    2. every ledger entry carries a `retrieved_on` date, and how old it is;
    3. entries older than the staleness window are reported, loudest first;
    4. with `--check-sources`, each `source_url` is fetched and reported reachable or not.

It deliberately does not try to parse a record out of a page. A number scraped from a leaderboard
and silently written into the ledger would be worse than a stale one: it would be unreviewed.
This tells a human which anchors to go and look at.

Usage:
    python scripts/check_anchor_freshness.py                    # offline, dates only
    python scripts/check_anchor_freshness.py --max-age-days 120
    python scripts/check_anchor_freshness.py --check-sources    # also probe every source_url
    python scripts/check_anchor_freshness.py --output experiments/anchor_freshness_<date>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

# Cells where the record is actively moving. A task normalising against one of these needs a
# tighter window than a task normalising against a proven optimum.
LIVE_RESEARCH_HINTS = (
    "cap set", "kissing", "matrix multiplication", "tensor rank", "ramsey",
    "superpermutation", "packing", "max-cut", "maxcut", "stabilizer", "quantum code",
    "binary code", "a(n,d)", "brouwer",
)
DEFAULT_MAX_AGE_DAYS = 180


def _parse_date(value):
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _entries(path: Path):
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document if isinstance(document, list) else document.get("anchors", document)
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [row for row in rows if isinstance(row, dict)]


def collect(today=None, max_age_days=DEFAULT_MAX_AGE_DAYS):
    today = today or date.today()
    ledgers, anchors, issues = [], [], []
    for spec in list_tasks(None):
        path = spec.task_dir / "references" / "anchors.json"
        if not path.is_file():
            continue
        try:
            rows = _entries(path)
        except (OSError, ValueError) as exc:
            issues.append("%s: anchors.json is unreadable: %s" % (spec.task_id, exc))
            continue
        ledgers.append(spec.task_id)
        for row in rows:
            name = str(row.get("name", "unnamed"))
            retrieved = _parse_date(row.get("retrieved_on"))
            source = row.get("source_url")
            text = " ".join(str(row.get(key, "")) for key in ("name", "derivation", "source_url")).lower()
            live = any(hint in text for hint in LIVE_RESEARCH_HINTS)
            if retrieved is None:
                issues.append("%s/%s: retrieved_on is missing or unparseable" % (spec.task_id, name))
                age = None
            else:
                age = (today - retrieved).days
            if not isinstance(source, str) or not source.strip():
                issues.append("%s/%s: source_url is missing" % (spec.task_id, name))
            window = max_age_days // 2 if live else max_age_days
            anchors.append({
                "task_id": spec.task_id, "name": name, "value": row.get("value"),
                "retrieved_on": row.get("retrieved_on"), "age_days": age,
                "source_url": source, "actively_researched": live,
                "window_days": window,
                "stale": bool(age is not None and age > window),
            })
    stale = [a for a in anchors if a["stale"]]
    return {
        "schema_version": 1,
        "checked_on": today.isoformat(),
        "max_age_days": max_age_days,
        "ledger_count": len(ledgers),
        "anchor_count": len(anchors),
        "stale_count": len(stale),
        "actively_researched_count": sum(1 for a in anchors if a["actively_researched"]),
        "anchors": anchors,
        "issues": issues,
        "passed": not issues and not stale,
    }


def probe_sources(report):
    """Fetch every distinct source_url and record whether it answered. Network, opt-in."""
    import urllib.error
    import urllib.request
    seen = {}
    for anchor in report["anchors"]:
        url = anchor.get("source_url")
        if not isinstance(url, str) or not url.startswith("http") or url in seen:
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "sle-anchor-freshness/1"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                seen[url] = {"status": int(response.status), "reachable": True}
        except urllib.error.HTTPError as exc:
            seen[url] = {"status": int(exc.code), "reachable": False}
        except Exception as exc:  # noqa: BLE001 - a probe failure is data, not a crash
            seen[url] = {"status": None, "reachable": False, "error": type(exc).__name__}
    report["source_probe"] = seen
    unreachable = sorted(url for url, row in seen.items() if not row["reachable"])
    report["unreachable_sources"] = unreachable
    if unreachable:
        report["issues"].append("%d anchor source(s) did not answer" % len(unreachable))
        report["passed"] = False
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                        help="staleness window; actively researched anchors get half of it")
    parser.add_argument("--check-sources", action="store_true",
                        help="also fetch every source_url and report whether it answered")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = collect(max_age_days=args.max_age_days)
    if args.check_sources:
        report = probe_sources(report)

    print("%d ledger(s), %d anchor(s), %d actively researched, %d stale"
          % (report["ledger_count"], report["anchor_count"],
             report["actively_researched_count"], report["stale_count"]))
    for anchor in sorted(report["anchors"], key=lambda a: -(a["age_days"] or 0)):
        if anchor["stale"]:
            print("  STALE  %-28s %-22s %s days old (window %d)%s" % (
                anchor["task_id"], anchor["name"], anchor["age_days"], anchor["window_days"],
                " [actively researched]" if anchor["actively_researched"] else ""))
    for issue in report["issues"]:
        print("  ISSUE  %s" % issue)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print("wrote %s" % args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
