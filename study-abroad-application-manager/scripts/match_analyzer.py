#!/usr/bin/env python3
"""Score program fit against an applicant profile using transparent rules."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SOFT_TERMS = {
    "research": ["research", "lab", "publication", "thesis", "paper"],
    "internship": ["intern", "work experience", "industry"],
    "project": ["project", "capstone", "portfolio"],
    "leadership": ["leadership", "president", "founder", "organizer"],
    "quant": ["math", "statistics", "calculus", "linear algebra", "probability"],
    "cs": ["computer science", "programming", "python", "java", "algorithm", "machine learning"],
}


def load_programs(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "programs" in data:
        return list(data["programs"])
    if isinstance(data, list):
        return data
    return [data]


def read_profile(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception:
            pass
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout
        except Exception:
            pass
        try:
            try:
                from pypdf import PdfReader  # type: ignore
            except Exception:
                from PyPDF2 import PdfReader  # type: ignore
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise RuntimeError(f"Could not extract text from PDF profile: {path}") from exc
    return path.read_text(encoding="utf-8", errors="replace")


def number_after(label: str, text: str) -> float | None:
    match = re.search(label + r"[^\d]{0,30}(\d+(?:\.\d+)?)", text, re.I)
    return float(match.group(1)) if match else None


def parse_profile(text: str) -> dict[str, Any]:
    return {
        "gpa": number_after(r"\bGPA\b", text),
        "toefl": number_after(r"\bTOEFL\b", text),
        "ielts": number_after(r"\bIELTS\b", text),
        "gre": number_after(r"\bGRE\b", text),
        "gmat": number_after(r"\bGMAT\b", text),
        "text": text,
        "lower": text.lower(),
    }


def parse_threshold(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None
    text = " ".join(str(v) for v in value) if isinstance(value, list) else str(value)
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def check_numeric(profile: dict[str, Any], reqs: dict[str, Any], key: str, label: str) -> tuple[bool | None, str]:
    threshold = parse_threshold(reqs.get(key))
    if threshold is None:
        return None, f"{label}: not specified"
    actual = profile.get(key)
    if actual is None:
        return False, f"{label}: missing in profile / required {threshold:g}"
    ok = actual >= threshold
    return ok, f"{label}: {actual:g}/{threshold:g} {'pass' if ok else 'below requirement'}"


def check_recommendations(reqs: dict[str, Any]) -> tuple[bool | None, str]:
    threshold = parse_threshold(reqs.get("recommendation_letters"))
    if threshold is None:
        return None, "Recommendation letters: not specified"
    return None, f"Recommendation letters: required {threshold:g}; confirm recommender availability manually"


def soft_fit(profile: dict[str, Any], program: dict[str, Any]) -> tuple[float, list[str]]:
    text = profile["lower"]
    hits: list[str] = []
    for label, terms in SOFT_TERMS.items():
        if any(term in text for term in terms):
            hits.append(label)
    score = min(len(hits) / 5.0, 1.0)
    if any(word in text for word in str(program.get("program_name", "")).lower().split()):
        score = min(score + 0.1, 1.0)
    return score, hits


def analyze(program: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    reqs = program.get("hard_requirements") or {}
    checks: list[tuple[bool | None, str]] = [
        check_numeric(profile, reqs, "gpa", "GPA"),
        check_numeric(profile, reqs, "toefl", "TOEFL"),
        check_numeric(profile, reqs, "ielts", "IELTS"),
        check_numeric(profile, reqs, "gre", "GRE"),
        check_numeric(profile, reqs, "gmat", "GMAT"),
        check_recommendations(reqs),
    ]
    known = [item for item in checks if item[0] is not None]
    hard_rate = sum(1 for ok, _ in known if ok) / len(known) if known else 0.5
    soft_score, soft_hits = soft_fit(profile, program)
    score = round((hard_rate * 0.6 + soft_score * 0.4) * 100)
    unmet = [detail for ok, detail in checks if ok is False]
    if score >= 85 and not unmet:
        recommendation = "core target"
    elif score >= 75:
        recommendation = "recommended"
    elif score >= 60:
        recommendation = "cautious reach"
    else:
        recommendation = "high risk"
    return {
        "program_name": program.get("program_name", ""),
        "school_name": program.get("school_name", ""),
        "score": score,
        "recommendation": recommendation,
        "hard_pass_rate": round(hard_rate, 3),
        "soft_fit_score": round(soft_score, 3),
        "checks": [detail for _, detail in checks],
        "soft_fit_hits": soft_hits,
        "unmet_hard_requirements": unmet,
        "notes": ["Manually verify non-numeric prerequisites and writing prompts before submission."],
    }


def render_markdown(results: list[dict[str, Any]]) -> str:
    lines = ["# Match Report", ""]
    for result in sorted(results, key=lambda item: item["score"], reverse=True):
        marker = "OK" if result["score"] >= 75 and not result["unmet_hard_requirements"] else "CHECK"
        lines.append(f"## {result['program_name'] or result['school_name']}: {result['score']}% {marker}")
        lines.append(f"- Recommendation: {result['recommendation']}")
        for check in result["checks"]:
            lines.append(f"- {check}")
        if result["soft_fit_hits"]:
            lines.append("- Soft fit signals: " + ", ".join(result["soft_fit_hits"]))
        if result["unmet_hard_requirements"]:
            lines.append("- Shortfalls: " + "; ".join(result["unmet_hard_requirements"]))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze applicant-program fit.")
    parser.add_argument("requirements_json", help="Normalized requirements JSON")
    parser.add_argument("profile", help="Applicant CV/resume/profile text or PDF")
    parser.add_argument("--out-md", required=True, help="Markdown report output")
    parser.add_argument("--out-json", required=True, help="JSON report output")
    args = parser.parse_args()

    profile = parse_profile(read_profile(Path(args.profile)))
    results = [analyze(program, profile) for program in load_programs(Path(args.requirements_json))]
    Path(args.out_json).write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(results), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
