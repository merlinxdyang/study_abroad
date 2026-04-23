#!/usr/bin/env python3
"""Extract a conservative, reviewable applicant profile from a CV/resume."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SECTION_PATTERNS = {
    "education": [
        r"education",
        r"academic background",
        r"教育背景",
        r"教育经历",
        r"学历",
    ],
    "courses": [
        r"coursework",
        r"courses",
        r"relevant courses",
        r"核心课程",
        r"相关课程",
        r"主修课程",
    ],
    "research": [
        r"research",
        r"publication",
        r"thesis",
        r"科研",
        r"研究经历",
        r"论文",
    ],
    "projects": [
        r"projects?",
        r"portfolio",
        r"项目经历",
        r"项目",
    ],
    "internships": [
        r"experience",
        r"employment",
        r"internship",
        r"work experience",
        r"实习",
        r"工作经历",
        r"实践经历",
    ],
    "awards": [
        r"awards?",
        r"honou?rs?",
        r"scholarships?",
        r"获奖",
        r"荣誉",
        r"奖学金",
    ],
    "skills": [
        r"skills?",
        r"technical skills",
        r"languages?",
        r"技能",
        r"语言能力",
        r"专业技能",
    ],
    "activities": [
        r"activities",
        r"leadership",
        r"volunteer",
        r"extracurricular",
        r"社团",
        r"学生工作",
        r"志愿",
    ],
    "goals": [
        r"objective",
        r"summary",
        r"interests?",
        r"research interests?",
        r"职业目标",
        r"申请目标",
        r"研究兴趣",
        r"个人简介",
    ],
}


NUMBER_LABELS = {
    "gpa": [r"\bGPA\b", r"平均绩点", r"学分绩点", r"绩点"],
    "toefl": [r"\bTOEFL\b", r"\bTOEFL\s*iBT\b", r"托福"],
    "ielts": [r"\bIELTS\b", r"雅思"],
    "gre": [r"\bGRE\b"],
    "gmat": [r"\bGMAT\b"],
}


LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "mixed": "mixed language",
    "unknown": "unknown",
}


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pdf(path: Path) -> str:
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if text.strip():
            return text
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
    except Exception:
        return ""


def read_docx(path: Path) -> str:
    try:
        import docx  # type: ignore

        document = docx.Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception:
        pass
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        parts = [node.text or "" for node in root.findall(".//w:t", namespace)]
        return "\n".join(parts)
    except Exception:
        return ""


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return normalize_text(read_pdf(path))
    if suffix == ".docx":
        return normalize_text(read_docx(path))
    return normalize_text(path.read_text(encoding="utf-8", errors="replace"))


def detect_language(text: str) -> str:
    counts = {
        "zh": len(re.findall(r"[\u4e00-\u9fff]", text)),
        "ja": len(re.findall(r"[\u3040-\u30ff]", text)),
        "ko": len(re.findall(r"[\uac00-\ud7af]", text)),
        "en": len(re.findall(r"[A-Za-z]", text)),
    }
    total = sum(counts.values())
    if total == 0:
        return "unknown"
    dominant, count = max(counts.items(), key=lambda item: item[1])
    if count / total < 0.55 and counts["en"] and any(counts[key] for key in counts if key != "en"):
        return "mixed"
    return dominant


def number_after(labels: list[str], text: str) -> dict[str, Any] | None:
    for label in labels:
        pattern = label + r"[^\d]{0,35}(\d+(?:\.\d+)?)(?:\s*/\s*(\d+(?:\.\d+)?))?"
        match = re.search(pattern, text, re.I)
        if match:
            value = float(match.group(1))
            scale = float(match.group(2)) if match.group(2) else None
            raw_start = text.rfind("\n", 0, match.start()) + 1
            raw_end = text.find("\n", match.end())
            if raw_end == -1:
                raw_end = len(text)
            return {
                "value": value,
                "scale": scale,
                "raw": re.sub(r"\s+", " ", text[raw_start:raw_end]).strip(),
            }
    return None


def first_contact(text: str) -> dict[str, str]:
    email_match = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, re.I)
    phone_match = re.search(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = ""
    for line in lines[:8]:
        if "@" in line or re.search(r"\d{4,}", line):
            continue
        if len(line) <= 60:
            name = line
            break
    return {
        "name": name,
        "email": email_match.group(1) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
    }


def is_heading(line: str) -> str | None:
    candidate = line.strip().strip(":：")
    if not candidate or len(candidate) > 80:
        return None
    for section, patterns in SECTION_PATTERNS.items():
        if any(re.fullmatch(pattern, candidate, re.I) for pattern in patterns):
            return section
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {key: [] for key in SECTION_PATTERNS}
    sections["other"] = []
    current = "other"
    buffer: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = is_heading(line)
        if heading:
            if buffer:
                sections[current].append("\n".join(buffer).strip())
            current = heading
            buffer = []
            continue
        buffer.append(line)
    if buffer:
        sections[current].append("\n".join(buffer).strip())
    return sections


def line_hits(text: str, patterns: list[str], limit: int = 8) -> list[str]:
    hits: list[str] = []
    for line in [item.strip(" -•\t") for item in text.splitlines()]:
        if len(line) < 4:
            continue
        if any(re.search(pattern, line, re.I) for pattern in patterns) and line not in hits:
            hits.append(line)
        if len(hits) >= limit:
            break
    return hits


def compact_items(blocks: list[str], fallback_text: str, patterns: list[str]) -> list[dict[str, Any]]:
    raw_items: list[str] = []
    for block in blocks:
        for line in block.splitlines():
            line = line.strip(" -•\t")
            if len(line) >= 4:
                raw_items.append(line)
    if not raw_items:
        raw_items = line_hits(fallback_text, patterns)
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for item in raw_items:
        normalized = re.sub(r"\s+", " ", item).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            items.append({"text": normalized, "needs_verification": False})
        if len(items) >= 12:
            break
    return items


def extract_evidence(text: str, sections: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    evidence: dict[str, list[dict[str, Any]]] = {}
    for section, patterns in SECTION_PATTERNS.items():
        evidence[section] = compact_items(sections.get(section, []), text, patterns)
    return evidence


def writing_bank(evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    mapping = [
        ("academic_readiness", ["education", "courses", "research"]),
        ("research_fit", ["research", "projects"]),
        ("practical_experience", ["internships", "projects"]),
        ("leadership_and_initiative", ["activities", "awards"]),
        ("technical_or_language_skills", ["skills"]),
        ("goals", ["goals"]),
    ]
    bank: list[dict[str, Any]] = []
    for theme, sections in mapping:
        items: list[str] = []
        for section in sections:
            items.extend(item["text"] for item in evidence.get(section, [])[:3])
        if items:
            bank.append(
                {
                    "theme": theme,
                    "evidence": items[:5],
                    "confidence": "medium",
                }
            )
    return bank


def render_markdown(profile: dict[str, Any]) -> str:
    applicant = profile["applicant"]
    lines = [
        "# Applicant Profile",
        "",
        f"- Source: {profile['source_file']}",
        f"- Detected language: {profile['language_name']} ({profile['language']})",
        f"- Name: {applicant.get('name') or 'needs_verification'}",
        f"- Email: {applicant.get('email') or 'not_found'}",
        "",
        "## Scores",
    ]
    for key, value in profile["scores"].items():
        if value:
            scale = f"/{value['scale']:g}" if value.get("scale") else ""
            lines.append(f"- {key.upper()}: {value['value']:g}{scale} ({value['raw']})")
        else:
            lines.append(f"- {key.upper()}: not_found")
    lines.append("")
    lines.append("## Evidence")
    for section, items in profile["evidence"].items():
        lines.append(f"### {section.replace('_', ' ').title()}")
        if not items:
            lines.append("- not_found")
        else:
            for item in items:
                suffix = " needs_verification" if item.get("needs_verification") else ""
                lines.append(f"- {item['text']}{suffix}")
        lines.append("")
    if profile["verification_notes"]:
        lines.append("## Verification Notes")
        for note in profile["verification_notes"]:
            lines.append(f"- {note}")
    return "\n".join(lines).rstrip() + "\n"


def build_profile(path: Path, requested_language: str) -> dict[str, Any]:
    text = read_document(path)
    language = detect_language(text) if requested_language == "auto" else requested_language
    sections = split_sections(text)
    evidence = extract_evidence(text, sections)
    scores = {key: number_after(labels, text) for key, labels in NUMBER_LABELS.items()}
    notes: list[str] = []
    if not text:
        notes.append("No extractable resume text found; OCR or a text copy is required.")
    if language not in ("en", "unknown"):
        notes.append(
            "Applicant evidence may need translation for English application documents; preserve official names and mark uncertain translations."
        )
    if not scores["gpa"]:
        notes.append("GPA was not found automatically; verify manually if required by a program.")
    return {
        "source_file": str(path),
        "language": language,
        "language_name": LANGUAGE_NAMES.get(language, language),
        "applicant": first_contact(text),
        "scores": scores,
        "evidence": evidence,
        "writing_bank": writing_bank(evidence),
        "verification_notes": notes,
        "raw_text": text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a structured applicant profile from a CV/resume.")
    parser.add_argument("resume", help="Applicant resume/CV/profile file: PDF, DOCX, TXT, or Markdown")
    parser.add_argument("--json-out", required=True, help="Structured applicant profile JSON output")
    parser.add_argument("--md-out", required=True, help="Human-reviewable applicant profile Markdown output")
    parser.add_argument(
        "--profile-language",
        default="auto",
        help="Profile language code, or auto to detect from the extracted text. Examples: auto, en, zh.",
    )
    args = parser.parse_args()

    profile = build_profile(Path(args.resume), args.profile_language)
    Path(args.json_out).write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.md_out).write_text(render_markdown(profile), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
