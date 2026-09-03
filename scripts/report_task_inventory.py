#!/usr/bin/env python3
"""Render TASKS.md, the human-readable inventory of every task package, from the registry.

The README links to this document as "the current task summary". A hand-maintained table would
drift the first time a task is added, so the table is generated: registry (`sle.registry`) for
the packages, `sle/conf/exam_taxonomy.yaml` for the form cell each one fills, `sle/certification.yaml`
for the evidence status, `frontier_eval/metadata.yaml` for score mode and oracle type, and the first
heading of `Task.md` for the one-line description. `--check` exits non-zero when the committed file
is stale, which is what the test asserts.

Usage:
    python scripts/report_task_inventory.py            # rewrite TASKS.md
    python scripts/report_task_inventory.py --check    # exit 1 if TASKS.md is stale
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

OUTPUT = ROOT / "TASKS.md"
TAXONOMY = ROOT / "sle" / "conf" / "exam_taxonomy.yaml"
CERTIFICATION = ROOT / "sle" / "certification.yaml"

FORM_TITLES = OrderedDict([("optimization", "Optimization"), ("discovery", "Discovery")])
ANALOGUE_TITLES = OrderedDict([
    ("frontier_eng", "工程设计(frontier_eng)"),
    ("combinatorial", "开放组合纪录(combinatorial,无上限)"),
    ("molecular_design", "分子与大分子设计(molecular_design)"),
])
KIND_TITLES = OrderedDict([
    ("formula", "公式(formula)"),
    ("structure", "结构(structure)"),
    ("evidence", "证据(evidence)"),
    ("substance", "物质(substance)"),
    ("parameter_inversion", "参数反演(parameter_inversion)"),
])


def _one_line(task_md: str) -> str:
    """The part of the first heading after the task name; failing that, the opening sentence."""
    lines = task_md.splitlines()
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            for sep in (" — ", " – ", " - ", ": "):
                if sep in title:
                    return title.split(sep, 1)[1].strip()
            break
    for line in lines:
        text = line.strip()
        if not text or text.startswith(("#", "|", "-", "*", "`", ">", "```")):
            continue
        sentence = re.split(r"(?<=[.。!?])\s", text, maxsplit=1)[0].strip()
        return sentence if len(sentence) <= 140 else sentence[:137].rstrip() + "..."
    return ""


def build_rows() -> list[dict]:
    taxonomy = (yaml.safe_load(TAXONOMY.read_text()) or {}).get("tasks") or {}
    certification = (yaml.safe_load(CERTIFICATION.read_text()) or {}).get("tasks") or {}
    rows = []
    for spec in list_tasks(None):
        cell = taxonomy.get(spec.task_id) or {}
        cert = certification.get(spec.task_id) or {}
        task_md = spec.task_md if isinstance(spec.task_md, str) else (spec.task_dir / "Task.md").read_text()
        rows.append({
            "task_id": spec.task_id,
            "name": spec.task_id.split("/")[-1],
            "discipline": spec.discipline,
            "domain": spec.domain,
            "path": spec.task_dir.relative_to(ROOT).as_posix(),
            "form": cell.get("form", "unmapped"),
            "cell": cell.get("analogue") or cell.get("kind") or "unmapped",
            "note": cell.get("note") or "",
            "score_mode": str(spec.metadata.get("score_mode", "")),
            "oracle_type": str(spec.metadata.get("oracle_type", "")),
            "status": cert.get("status", "unregistered"),
            "summary": _one_line(task_md),
        })
    return sorted(rows, key=lambda r: (r["form"], r["cell"], r["discipline"], r["name"]))


def _table(rows: list[dict]) -> list[str]:
    out = ["| 任务 | 学科 | 领域 | 打分 | oracle | 认证 | 说明 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        note = " · on-ramp,不配对" if "on_ramp" in r["note"] else ""
        summary = (r["summary"] or "").replace("|", "\\|")
        out.append("| [`%s`](%s/) | %s | %s | %s | %s | %s | %s%s |" % (
            r["name"], r["path"], r["discipline"], r["domain"], r["score_mode"],
            r["oracle_type"], r["status"], summary, note))
    return out


def render(rows: list[dict]) -> str:
    forms = Counter(r["form"] for r in rows)
    statuses = Counter(r["status"] for r in rows)
    disciplines = Counter(r["discipline"] for r in rows)
    lines = [
        "# 任务汇总",
        "",
        "由 `python scripts/report_task_inventory.py` 从注册表生成,`tests/test_task_inventory_document.py` 保证它不过期;"
        "不要手改。权威实时清单是 `python -m sle list --all`。",
        "",
        "| | |",
        "|---|---:|",
        "| 任务包 | %d |" % len(rows),
    ]
    for form in FORM_TITLES:
        lines.append("| %s | %d |" % (form, forms.get(form, 0)))
    for status in ("certified", "candidate", "quarantined"):
        if statuses.get(status):
            lines.append("| %s | %d |" % (status, statuses[status]))
    lines.append("| 学科 | %d(%s) |" % (
        len(disciplines), ",".join("%s %d" % (k, v) for k, v in sorted(disciplines.items()))))
    lines.append("")
    lines.append("认证描述的是证据质量,不是难度。标 on-ramp 的任务首个前沿模型提案已够到参考解,不用于配对 Δ 测量。")
    lines.append("")
    for form, title in FORM_TITLES.items():
        subset = [r for r in rows if r["form"] == form]
        lines.append("## %s(%d)" % (title, len(subset)))
        lines.append("")
        titles = ANALOGUE_TITLES if form == "optimization" else KIND_TITLES
        cells = list(titles) + sorted({r["cell"] for r in subset} - set(titles))
        for cell in cells:
            group = [r for r in subset if r["cell"] == cell]
            if not group:
                continue
            lines.append("### %s — %d" % (titles.get(cell, cell), len(group)))
            lines.append("")
            lines.extend(_table(group))
            lines.append("")
    stray = [r for r in rows if r["form"] not in FORM_TITLES]
    if stray:
        lines.append("## 未映射到 exam_taxonomy.yaml 的任务(%d)" % len(stray))
        lines.append("")
        lines.extend(_table(stray))
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if TASKS.md differs from the registry")
    ap.add_argument("--output", type=Path, default=OUTPUT)
    args = ap.parse_args(argv)
    content = render(build_rows())
    if args.check:
        current = args.output.read_text() if args.output.exists() else ""
        if current != content:
            print("%s is stale; run: python scripts/report_task_inventory.py" % args.output.relative_to(ROOT))
            return 1
        print("%s is current" % args.output.relative_to(ROOT))
        return 0
    args.output.write_text(content)
    print("wrote %s (%d tasks)" % (args.output.relative_to(ROOT), content.count("| [`")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
