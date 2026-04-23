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
    "research": [
        "research",
        "lab",
        "publication",
        "thesis",
        "paper",
        "科研",
        "研究",
        "实验室",
        "论文",
        "发表",
        "课题",
        "recherche",
        "investigacion",
        "investigación",
    ],
    "internship": [
        "intern",
        "internship",
        "work experience",
        "industry",
        "实习",
        "工作经历",
        "行业",
        "stage",
        "practicas",
        "prácticas",
    ],
    "project": ["project", "capstone", "portfolio", "项目", "作品集", "projet", "proyecto"],
    "leadership": [
        "leadership",
        "president",
        "founder",
        "organizer",
        "负责人",
        "主席",
        "创始",
        "组织",
        "社团",
        "领导力",
        "presidente",
        "fondateur",
    ],
    "quant": [
        "math",
        "statistics",
        "calculus",
        "linear algebra",
        "probability",
        "数学",
        "统计",
        "微积分",
        "线性代数",
        "概率",
        "matematicas",
        "matemáticas",
        "statistique",
    ],
    "cs": [
        "computer science",
        "programming",
        "python",
        "java",
        "algorithm",
        "machine learning",
        "计算机",
        "编程",
        "算法",
        "机器学习",
        "人工智能",
        "数据结构",
        "软件",
        "programacion",
        "programación",
        "informatique",
    ],
}


PROFILE_NUMBER_LABELS = {
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
    "cyrillic": "Cyrillic-script language",
    "arabic": "Arabic-script language",
    "mixed": "mixed language",
    "unknown": "unknown",
}


ZH_TEXT = {
    "title": "# 匹配度报告",
    "profile_language": "简历语言",
    "language_handling": "语言处理提示",
    "recommendation": "推荐判断",
    "soft_fit_signals": "软性匹配信号",
    "shortfalls": "短板",
    "ok": "通过",
    "check": "需核对",
    "not_specified": "项目未明确要求",
    "missing": "简历未找到",
    "required": "要求",
    "pass": "达标",
    "below": "低于要求",
    "recommendation_letters_unspecified": "推荐信：项目未明确要求",
    "recommendation_letters_required": "推荐信：要求 {threshold:g} 封；需人工确认推荐人安排",
}


EN_TEXT = {
    "title": "# Match Report",
    "profile_language": "Profile language",
    "language_handling": "Language handling",
    "recommendation": "Recommendation",
    "soft_fit_signals": "Soft fit signals",
    "shortfalls": "Shortfalls",
    "ok": "OK",
    "check": "CHECK",
    "not_specified": "not specified",
    "missing": "missing in profile",
    "required": "required",
    "pass": "pass",
    "below": "below requirement",
    "recommendation_letters_unspecified": "Recommendation letters: not specified",
    "recommendation_letters_required": (
        "Recommendation letters: required {threshold:g}; confirm recommender availability manually"
    ),
}


RECOMMENDATION_LABELS = {
    "en": {
        "core target": "core target",
        "recommended": "recommended",
        "cautious reach": "cautious reach",
        "high risk": "high risk",
    },
    "zh": {
        "core target": "核心目标",
        "recommended": "推荐申请",
        "cautious reach": "谨慎冲刺",
        "high risk": "高风险",
    },
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


def number_after(labels: list[str], text: str) -> float | None:
    for label in labels:
        match = re.search(label + r"[^\d]{0,30}(\d+(?:\.\d+)?)", text, re.I)
        if match:
            return float(match.group(1))
    return None


def detect_profile_language(text: str) -> str:
    counts = {
        "zh": len(re.findall(r"[\u4e00-\u9fff]", text)),
        "ja": len(re.findall(r"[\u3040-\u30ff]", text)),
        "ko": len(re.findall(r"[\uac00-\ud7af]", text)),
        "cyrillic": len(re.findall(r"[\u0400-\u04ff]", text)),
        "arabic": len(re.findall(r"[\u0600-\u06ff]", text)),
        "en": len(re.findall(r"[A-Za-z]", text)),
    }
    total = sum(counts.values())
    if total == 0:
        return "unknown"
    dominant, dominant_count = max(counts.items(), key=lambda item: item[1])
    if dominant_count / total < 0.55 and counts["en"] and any(counts[key] for key in counts if key != "en"):
        return "mixed"
    return dominant


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def resolve_report_language(requested: str, profile_language: str) -> str:
    if requested != "auto":
        return requested
    return "zh" if profile_language == "zh" else "en"


def ui_text(language: str) -> dict[str, str]:
    return ZH_TEXT if language == "zh" else EN_TEXT


def language_notes(profile_language: str, report_language: str) -> list[str]:
    if profile_language in ("en", "unknown"):
        return []
    if report_language == "zh":
        return [
            "简历不是英文或包含多语言内容；用于英文申请材料时，需要把经历证据翻译并改写为目标申请语言。",
            "人名、学校名、课程名、奖项名和项目名应保留原文或采用官方英文译名；无法确认的译名标记为 needs_verification。",
            "非英文关键词匹配只作为第一轮筛查，软性匹配分数需要人工复核。",
        ]
    return [
        "The profile is not primarily English or contains multiple languages; translate and adapt applicant evidence into the target application language before drafting application materials.",
        "Keep names, institutions, courses, awards, and projects in the original wording or use official translations; mark uncertain translations as needs_verification.",
        "Non-English keyword matching is a first-pass signal only; manually review the soft-fit score.",
    ]


def parse_profile(text: str, requested_language: str) -> dict[str, Any]:
    profile_language = detect_profile_language(text) if requested_language == "auto" else requested_language
    return {
        "gpa": number_after(PROFILE_NUMBER_LABELS["gpa"], text),
        "toefl": number_after(PROFILE_NUMBER_LABELS["toefl"], text),
        "ielts": number_after(PROFILE_NUMBER_LABELS["ielts"], text),
        "gre": number_after(PROFILE_NUMBER_LABELS["gre"], text),
        "gmat": number_after(PROFILE_NUMBER_LABELS["gmat"], text),
        "language": profile_language,
        "language_name": language_name(profile_language),
        "language_detection": requested_language,
        "text": text,
        "lower": text.lower(),
    }


def parse_threshold(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None
    text = " ".join(str(v) for v in value) if isinstance(value, list) else str(value)
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def check_numeric(
    profile: dict[str, Any], reqs: dict[str, Any], key: str, label: str, report_language: str
) -> tuple[bool | None, str]:
    text = ui_text(report_language)
    threshold = parse_threshold(reqs.get(key))
    if threshold is None:
        return None, f"{label}: {text['not_specified']}"
    actual = profile.get(key)
    if actual is None:
        return False, f"{label}: {text['missing']} / {text['required']} {threshold:g}"
    ok = actual >= threshold
    return ok, f"{label}: {actual:g}/{threshold:g} {text['pass'] if ok else text['below']}"


def check_recommendations(reqs: dict[str, Any], report_language: str) -> tuple[bool | None, str]:
    text = ui_text(report_language)
    threshold = parse_threshold(reqs.get("recommendation_letters"))
    if threshold is None:
        return None, text["recommendation_letters_unspecified"]
    return None, text["recommendation_letters_required"].format(threshold=threshold)


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


def analyze(program: dict[str, Any], profile: dict[str, Any], report_language: str) -> dict[str, Any]:
    reqs = program.get("hard_requirements") or {}
    checks: list[tuple[bool | None, str]] = [
        check_numeric(profile, reqs, "gpa", "GPA", report_language),
        check_numeric(profile, reqs, "toefl", "TOEFL", report_language),
        check_numeric(profile, reqs, "ielts", "IELTS", report_language),
        check_numeric(profile, reqs, "gre", "GRE", report_language),
        check_numeric(profile, reqs, "gmat", "GMAT", report_language),
        check_recommendations(reqs, report_language),
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
    recommendation_label = RECOMMENDATION_LABELS.get(report_language, RECOMMENDATION_LABELS["en"])[recommendation]
    return {
        "program_name": program.get("program_name", ""),
        "school_name": program.get("school_name", ""),
        "score": score,
        "recommendation": recommendation,
        "recommendation_label": recommendation_label,
        "hard_pass_rate": round(hard_rate, 3),
        "soft_fit_score": round(soft_score, 3),
        "checks": [detail for _, detail in checks],
        "soft_fit_hits": soft_hits,
        "unmet_hard_requirements": unmet,
        "notes": language_notes(profile["language"], report_language)
        + (
            ["Manually verify non-numeric prerequisites and writing prompts before submission."]
            if report_language != "zh"
            else ["提交前需人工核对非数字类先修要求和文书题目。"]
        ),
    }


def render_markdown(results: list[dict[str, Any]], profile: dict[str, Any], report_language: str) -> str:
    text = ui_text(report_language)
    lines = [text["title"], ""]
    lines.append(f"- {text['profile_language']}: {profile['language_name']} ({profile['language_detection']})")
    notes = language_notes(profile["language"], report_language)
    if notes:
        lines.append(f"- {text['language_handling']}: " + " ".join(notes))
    lines.append("")
    for result in sorted(results, key=lambda item: item["score"], reverse=True):
        marker = text["ok"] if result["score"] >= 75 and not result["unmet_hard_requirements"] else text["check"]
        lines.append(f"## {result['program_name'] or result['school_name']}: {result['score']}% {marker}")
        lines.append(f"- {text['recommendation']}: {result['recommendation_label']}")
        for check in result["checks"]:
            lines.append(f"- {check}")
        if result["soft_fit_hits"]:
            lines.append(f"- {text['soft_fit_signals']}: " + ", ".join(result["soft_fit_hits"]))
        if result["unmet_hard_requirements"]:
            lines.append(f"- {text['shortfalls']}: " + "; ".join(result["unmet_hard_requirements"]))
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze applicant-program fit.")
    parser.add_argument("requirements_json", help="Normalized requirements JSON")
    parser.add_argument("profile", help="Applicant CV/resume/profile text or PDF")
    parser.add_argument("--out-md", required=True, help="Markdown report output")
    parser.add_argument("--out-json", required=True, help="JSON report output")
    parser.add_argument(
        "--profile-language",
        default="auto",
        help="Profile language code, or auto to detect from the extracted text. Examples: auto, en, zh.",
    )
    parser.add_argument(
        "--report-language",
        choices=("auto", "en", "zh"),
        default="auto",
        help="Markdown report language. auto uses Chinese for Chinese profiles and English otherwise.",
    )
    args = parser.parse_args()

    profile = parse_profile(read_profile(Path(args.profile)), args.profile_language)
    report_language = resolve_report_language(args.report_language, profile["language"])
    results = [analyze(program, profile, report_language) for program in load_programs(Path(args.requirements_json))]
    metadata = {
        "profile_language": profile["language"],
        "profile_language_name": profile["language_name"],
        "profile_language_detection": profile["language_detection"],
        "report_language": report_language,
        "language_notes": language_notes(profile["language"], report_language),
    }
    Path(args.out_json).write_text(json.dumps({"profile": metadata, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(results, profile, report_language), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
