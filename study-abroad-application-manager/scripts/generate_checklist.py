#!/usr/bin/env python3
"""Generate application countdown checklists and an importable ICS calendar."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from typing import Any


TASKS = [
    (60, "Prepare recommendation letters and contact recommenders"),
    (45, "Finish first draft of PS/SOP/cover letter"),
    (30, "Finalize essays and request language-score reports"),
    (14, "Complete online application forms"),
    (7, "Upload materials, review documents, and pay fees"),
    (1, "Final submission check"),
]


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def load_programs(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "programs" in data:
        return list(data["programs"])
    if isinstance(data, list):
        return data
    return [data]


def parse_deadline(value: Any) -> date | None:
    text = str(value or "")
    iso = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    mdy = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if mdy:
        month = MONTHS.get(mdy.group(1).lower())
        if month:
            return date(int(mdy.group(3)), month, int(mdy.group(2)))
    slash = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if slash:
        first = int(slash.group(1))
        second = int(slash.group(2))
        year = int(slash.group(3))
        if first > 12:
            return date(year, second, first)
        return date(year, first, second)
    return None


def program_name(program: dict[str, Any], index: int) -> str:
    return str(program.get("program_name") or program.get("school_name") or f"Program {index + 1}")


def escape_ics(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def render_markdown(programs: list[dict[str, Any]], timezone: str) -> str:
    today = date.today()
    lines = [f"# Application Deadline Tracker", "", f"Timezone: {timezone}", ""]
    for index, program in enumerate(programs):
        name = program_name(program, index)
        deadline = parse_deadline(program.get("deadline"))
        if not deadline:
            lines.append(f"## {name} (deadline needs verification)")
            lines.append("- [ ] Confirm official application deadline and timezone")
            lines.append("")
            continue
        remaining = (deadline - today).days
        lines.append(f"## {name} (deadline: {deadline.isoformat()}, remaining {remaining} days)")
        for days_before, label in TASKS:
            task_date = deadline - timedelta(days=days_before)
            lines.append(f"- [ ] T-{days_before} days ({task_date.isoformat()}): {label}")
        lines.append(f"- [ ] T-0 days ({deadline.isoformat()}): Submit application and save confirmation receipt")
        lines.append("")
    return "\n".join(lines)


def render_ics(programs: list[dict[str, Any]], timezone: str) -> str:
    now = datetime.now(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Codex//Study Abroad Application Manager//EN", "CALSCALE:GREGORIAN"]
    for index, program in enumerate(programs):
        name = program_name(program, index)
        deadline = parse_deadline(program.get("deadline"))
        if not deadline:
            continue
        for days_before, label in TASKS + [(0, "Submit application and save confirmation receipt")]:
            task_date = deadline - timedelta(days=days_before)
            uid = f"{uuid.uuid4()}@study-abroad-application-manager"
            summary = f"{name}: {label}"
            description = f"Deadline: {deadline.isoformat()} ({timezone}). Source: {program.get('source_file', 'not specified')}"
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{now}",
                    f"DTSTART;VALUE=DATE:{task_date.strftime('%Y%m%d')}",
                    f"SUMMARY:{escape_ics(summary)}",
                    f"DESCRIPTION:{escape_ics(description)}",
                    "END:VEVENT",
                ]
            )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Markdown checklist and ICS calendar.")
    parser.add_argument("requirements_json", help="Normalized requirements JSON")
    parser.add_argument("--timezone", required=True, help="Deadline timezone, e.g. Asia/Shanghai or America/New_York")
    parser.add_argument("--out-md", required=True, help="Markdown checklist output")
    parser.add_argument("--out-ics", required=True, help="ICS calendar output")
    args = parser.parse_args()

    programs = load_programs(Path(args.requirements_json))
    Path(args.out_md).write_text(render_markdown(programs, args.timezone), encoding="utf-8")
    Path(args.out_ics).write_text(render_ics(programs, args.timezone), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
