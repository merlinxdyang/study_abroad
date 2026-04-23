#!/usr/bin/env python3
"""Extract admissions brochure text and conservative structured fields."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATE_RE = re.compile(
    r"(?i)\b("
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4}|"
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r")\b"
)


DOC_KEYWORDS = [
    "transcript",
    "cv",
    "resume",
    "personal statement",
    "statement of purpose",
    "motivation letter",
    "letter of motivation",
    "sop",
    "cover letter",
    "essay",
    "recommendation",
    "reference letter",
    "letter of reference",
    "passport",
    "language score",
    "toefl",
    "ielts",
    "gre",
    "gmat",
    "writing sample",
    "portfolio",
    "application form",
]


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_with_pdfplumber(path: Path) -> str | None:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return None
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def extract_with_pypdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return None
    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def extract_with_pdftotext(path: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def extract_text(path: Path) -> tuple[str, str]:
    for name, extractor in (
        ("pdfplumber", extract_with_pdfplumber),
        ("pypdf", extract_with_pypdf),
        ("pdftotext", extract_with_pdftotext),
    ):
        try:
            text = extractor(path)
        except Exception:
            text = None
        if text and text.strip():
            return normalize_text(text), name
    return "", "none"


def first_match(pattern: str, text: str, flags: int = re.I) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1).strip(" :-\n\t") if match else ""


def find_snippets(text: str, patterns: list[str], window: int = 220) -> list[str]:
    snippets: list[str] = []
    lowered = text.lower()
    for pattern in patterns:
        for match in re.finditer(pattern.lower(), lowered):
            start = max(match.start() - window // 2, 0)
            end = min(match.end() + window // 2, len(text))
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= 8:
                return snippets
    return snippets


def infer_school_and_program(path: Path, text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if 5 <= len(line.strip()) <= 120]
    header = "\n".join(lines[:20])
    school = first_match(r"(?:University|College|School) of ([A-Z][A-Za-z &.-]+)", header)
    if school:
        school = "University of " + school
    else:
        school = first_match(r"([A-Z][A-Za-z &.-]+(?:University|College|Institute|School))", header)
    program = first_match(
        r"((?:Summer|Visiting|Exchange|Study Abroad|Master|MSc|MS|MA|PhD|Undergraduate)[^\n]{0,80}(?:Program|School|Session|Course|Degree))",
        header,
    )
    if not program and lines:
        program = lines[0]
    return school, program or path.stem.replace("_", " ").replace("-", " ")


def extract_deadline(text: str) -> str:
    deadline_patterns = [
        r"(?i)(?:application|submission|program)?\s*deadline[^\n]{0,120}",
        r"(?i)apply by[^\n]{0,120}",
        r"(?i)applications? (?:are )?due[^\n]{0,120}",
    ]
    for snippet in find_snippets(text, deadline_patterns, window=260):
        date = DATE_RE.search(snippet)
        if date:
            return date.group(1)
    return ""


def extract_documents(text: str) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for keyword in DOC_KEYWORDS:
        if keyword in lowered:
            found.append(keyword)
    return found


def extract_hard_requirements(text: str) -> dict[str, Any]:
    req: dict[str, Any] = {}
    gpa = first_match(r"(?i)\bGPA\b[^\n]{0,40}?([0-4](?:\.\d{1,2})?\s*/\s*4(?:\.0)?|[0-4](?:\.\d{1,2})?)", text)
    if gpa:
        req["gpa"] = gpa
    toefl = first_match(r"(?i)\bTOEFL\b[^\n]{0,40}?(\d{2,3})", text)
    if toefl:
        req["toefl"] = toefl
    ielts = first_match(r"(?i)\bIELTS\b[^\n]{0,40}?([0-9](?:\.[05])?)", text)
    if ielts:
        req["ielts"] = ielts
    gre = first_match(r"(?i)\bGRE\b[^\n]{0,60}?(\d{3,4})", text)
    if gre:
        req["gre"] = gre
    gmat = first_match(r"(?i)\bGMAT\b[^\n]{0,60}?(\d{3,4})", text)
    if gmat:
        req["gmat"] = gmat
    rec = first_match(
        r"(?i)(\d+|one|two|three)\s+(?:(?:letters?\s+of\s+)?recommendation|reference letters?|letters?\s+of\s+reference)",
        text,
    )
    if rec:
        req["recommendation_letters"] = rec
    prereq_snippets = find_snippets(text, [r"prerequisite", r"prior coursework", r"background in"], window=280)
    if prereq_snippets:
        req["prerequisites"] = prereq_snippets[:3]
    essay_snippets = find_snippets(
        text,
        [r"statement of purpose", r"personal statement", r"motivation letter", r"letter of motivation", r"essay", r"cover letter"],
        window=280,
    )
    if essay_snippets:
        req["writing_requirements"] = essay_snippets[:3]
    return req


def extract_fee(text: str) -> str:
    return first_match(r"(?i)(?:application fee|fee)[^\n$]{0,40}(\$?\s?\d{2,5}(?:\.\d{2})?)", text)


def extract_contact(text: str) -> str:
    email = first_match(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text)
    if email:
        return email
    return first_match(r"(?i)(?:contact|email|inquiries)[^\n]{0,140}", text)


def parse_program(path: Path, text_dir: Path | None, include_text: bool) -> dict[str, Any]:
    text, method = extract_text(path)
    school, program = infer_school_and_program(path, text) if text else ("", path.stem)
    source_text_path = ""
    if text_dir:
        text_dir.mkdir(parents=True, exist_ok=True)
        out_path = text_dir / f"{path.stem}.txt"
        out_path.write_text(text, encoding="utf-8")
        source_text_path = str(out_path)
    result: dict[str, Any] = {
        "source_file": str(path),
        "extraction_method": method,
        "school_name": school,
        "program_name": program,
        "deadline": extract_deadline(text) if text else "",
        "required_documents": extract_documents(text) if text else [],
        "hard_requirements": extract_hard_requirements(text) if text else {},
        "application_fee": extract_fee(text) if text else "",
        "contact_info": extract_contact(text) if text else "",
        "source_text_path": source_text_path,
        "evidence": {
            "deadline": find_snippets(text, [r"deadline", r"apply by", r"due"], window=240) if text else [],
            "documents": find_snippets(text, DOC_KEYWORDS, window=240) if text else [],
            "requirements": find_snippets(text, [r"GPA", r"TOEFL", r"IELTS", r"GRE", r"GMAT", r"prerequisite"], window=240) if text else [],
        },
        "warnings": [],
    }
    if not text:
        result["warnings"].append("No extractable text found; OCR or a text copy is required.")
    if include_text:
        result["text"] = text
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse admissions brochure PDFs into conservative JSON.")
    parser.add_argument("pdfs", nargs="+", help="PDF files to parse")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--text-dir", help="Optional directory for extracted text files")
    parser.add_argument("--include-text", action="store_true", help="Embed full extracted text in JSON")
    args = parser.parse_args()

    text_dir = Path(args.text_dir) if args.text_dir else None
    programs = [parse_program(Path(pdf), text_dir, args.include_text) for pdf in args.pdfs]
    Path(args.out).write_text(json.dumps(programs, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
