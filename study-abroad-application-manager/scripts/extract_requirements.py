#!/usr/bin/env python3
"""Normalize parsed program JSON into requirement JSON and a comparison table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


FIELDS = [
    ("deadline", "Deadline"),
    ("gpa", "GPA"),
    ("toefl", "TOEFL"),
    ("ielts", "IELTS"),
    ("gre", "GRE"),
    ("gmat", "GMAT"),
    ("recommendation_letters", "Recommendation Letters"),
    ("prerequisites", "Prerequisites"),
    ("writing_requirements", "Writing Requirements"),
    ("required_documents", "Required Documents"),
    ("application_fee", "Application Fee"),
    ("contact_info", "Contact"),
]


def load_programs(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "programs" in data:
            return list(data["programs"])
        return [data]
    return list(data)


def compact(value: Any) -> str:
    if value in (None, "", [], {}):
        return "not_found"
    if isinstance(value, list):
        return "; ".join(compact(item) for item in value if item not in (None, "", [], {})) or "not_found"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {compact(val)}" for key, val in value.items()) or "not_found"
    return str(value).replace("\n", " ").strip()


def normalized_program(program: dict[str, Any]) -> dict[str, Any]:
    hard = program.get("hard_requirements") or {}
    return {
        "school_name": program.get("school_name", ""),
        "program_name": program.get("program_name", ""),
        "source_file": program.get("source_file", ""),
        "source_text_path": program.get("source_text_path", ""),
        "deadline": program.get("deadline", ""),
        "required_documents": program.get("required_documents", []),
        "hard_requirements": {
            "gpa": hard.get("gpa", ""),
            "toefl": hard.get("toefl", ""),
            "ielts": hard.get("ielts", ""),
            "gre": hard.get("gre", ""),
            "gmat": hard.get("gmat", ""),
            "prerequisites": hard.get("prerequisites", []),
            "recommendation_letters": hard.get("recommendation_letters", ""),
            "writing_requirements": hard.get("writing_requirements", []),
        },
        "application_fee": program.get("application_fee", ""),
        "contact_info": program.get("contact_info", ""),
        "evidence": program.get("evidence", {}),
        "warnings": program.get("warnings", []),
    }


def render_markdown(programs: list[dict[str, Any]]) -> str:
    names = [compact(p.get("program_name") or p.get("school_name") or f"Program {idx + 1}") for idx, p in enumerate(programs)]
    lines = ["# Requirement Comparison", "", "| Dimension | " + " | ".join(names) + " |"]
    lines.append("|---|" + "|".join("---" for _ in names) + "|")
    for key, label in FIELDS:
        row = [label]
        for program in programs:
            if key in program.get("hard_requirements", {}):
                value = program["hard_requirements"].get(key)
            else:
                value = program.get(key)
            row.append(compact(value))
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |")
    lines.append("")
    lines.append("## Verification Notes")
    for program in programs:
        warnings = program.get("warnings") or []
        if warnings:
            lines.append(f"- {compact(program.get('program_name'))}: " + "; ".join(warnings))
    if lines[-1] == "## Verification Notes":
        lines.append("- No parser warnings. Still verify deadlines and requirements against official sources before submission.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create normalized requirements JSON and Markdown table.")
    parser.add_argument("parsed_json", help="JSON from parse_pdf.py")
    parser.add_argument("--json-out", required=True, help="Normalized JSON output")
    parser.add_argument("--md-out", required=True, help="Markdown comparison table output")
    args = parser.parse_args()

    programs = [normalized_program(p) for p in load_programs(Path(args.parsed_json))]
    Path(args.json_out).write_text(json.dumps({"programs": programs}, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md_out).write_text(render_markdown(programs), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
