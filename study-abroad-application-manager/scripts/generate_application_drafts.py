#!/usr/bin/env python3
"""Generate first-pass application document drafts from match results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DOC_TYPES = {
    "cover_letter": ["cover letter", "covering letter"],
    "motivation_letter": ["motivation letter", "letter of motivation"],
    "statement_of_purpose": ["statement of purpose", "sop", "research proposal", "research statement", "statement of research interest"],
    "personal_statement": ["personal statement"],
    "essay": ["essay", "writing sample"],
}


RECOMMENDATION_TERMS = [
    "recommendation",
    "reference letter",
    "letter of reference",
    "推荐信",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_programs(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, dict) and "programs" in data:
        return list(data["programs"])
    if isinstance(data, list):
        return data
    return [data]


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s.-]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s._]+", "-", value.strip().lower())
    return value.strip("-") or "program"


def compact(value: Any) -> str:
    if value in (None, "", [], {}):
        return "not_found"
    if isinstance(value, list):
        return "; ".join(compact(item) for item in value if item not in (None, "", [], {})) or "not_found"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {compact(val)}" for key, val in value.items()) or "not_found"
    return re.sub(r"\s+", " ", str(value)).strip()


def program_name(program: dict[str, Any], index: int) -> str:
    return str(program.get("program_name") or program.get("school_name") or f"Program {index + 1}")


def program_key(program: dict[str, Any]) -> str:
    return f"{program.get('program_name', '')} {program.get('school_name', '')}".strip().lower()


def match_by_program(match_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = match_report.get("results") if isinstance(match_report, dict) else []
    matched: dict[str, dict[str, Any]] = {}
    for result in results or []:
        key = f"{result.get('program_name', '')} {result.get('school_name', '')}".strip().lower()
        if key:
            matched[key] = result
    return matched


def find_match(program: dict[str, Any], matches: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = program_key(program)
    if key in matches:
        return matches[key]
    for match_key, result in matches.items():
        if key and (key in match_key or match_key in key):
            return result
    return {}


def text_pool(program: dict[str, Any]) -> str:
    hard = program.get("hard_requirements") or {}
    parts = [
        program.get("program_name"),
        program.get("school_name"),
        program.get("required_documents"),
        hard.get("writing_requirements"),
        hard.get("recommendation_letters"),
        program.get("evidence"),
    ]
    return compact(parts).lower()


def required_doc_types(program: dict[str, Any]) -> list[str]:
    pool = text_pool(program)
    negative_patterns = [
        r"no application essays? found",
        r"no application writing found",
        r"no writing requirements? found",
    ]
    if any(re.search(pattern, pool, re.I) for pattern in negative_patterns):
        pool = re.sub(r"no application essays? found", "", pool, flags=re.I)
        pool = re.sub(r"no application writing found", "", pool, flags=re.I)
        pool = re.sub(r"no writing requirements? found", "", pool, flags=re.I)
    found: list[str] = []
    for doc_type, terms in DOC_TYPES.items():
        if any(term in pool for term in terms):
            found.append(doc_type)
    return found


def recommendation_required(program: dict[str, Any]) -> bool:
    pool = text_pool(program)
    hard = program.get("hard_requirements") or {}
    return bool(hard.get("recommendation_letters")) or any(term in pool for term in RECOMMENDATION_TERMS)


def evidence_lines(profile: dict[str, Any], match: dict[str, Any]) -> list[str]:
    chosen: list[str] = []
    for bucket in match.get("writing_evidence") or profile.get("writing_bank") or []:
        for item in bucket.get("evidence") or []:
            if item and item not in chosen:
                chosen.append(str(item))
            if len(chosen) >= 5:
                return chosen
    for items in (profile.get("evidence") or {}).values():
        for item in items:
            if isinstance(item, dict) and item.get("text") and item["text"] not in chosen:
                chosen.append(item["text"])
            if len(chosen) >= 5:
                return chosen
    return chosen


def applicant_name(profile: dict[str, Any]) -> str:
    return str((profile.get("applicant") or {}).get("name") or "needs_verification: applicant name")


def score_line(match: dict[str, Any]) -> str:
    if not match:
        return "Match score: needs_verification"
    return f"Match score: {match.get('score', 'needs_verification')}%; recommendation: {match.get('recommendation_label') or match.get('recommendation') or 'needs_verification'}"


def source_note(program: dict[str, Any]) -> str:
    source = program.get("source_file") or program.get("source_text_path") or "needs_verification"
    return f"Source used for requirements: {source}"


def doc_title(doc_type: str) -> str:
    return {
        "cover_letter": "Cover Letter Draft",
        "motivation_letter": "Motivation Letter Draft",
        "statement_of_purpose": "Statement of Purpose Draft",
        "personal_statement": "Personal Statement Draft",
        "essay": "Essay Draft",
    }.get(doc_type, "Application Document Draft")


def applicant_intro(profile: dict[str, Any]) -> str:
    scores = profile.get("scores") or {}
    score_parts: list[str] = []
    for key in ("gpa", "toefl", "ielts", "gre", "gmat"):
        value = scores.get(key)
        if isinstance(value, dict) and value.get("value") is not None:
            scale = f"/{value['scale']:g}" if value.get("scale") else ""
            score_parts.append(f"{key.upper()} {value['value']:g}{scale}")
    return ", ".join(score_parts) if score_parts else "academic metrics to be verified from the CV"


def drafting_paragraphs(
    doc_type: str,
    program: dict[str, Any],
    match: dict[str, Any],
    profile: dict[str, Any],
    draft_language: str,
) -> list[str]:
    name = program_name(program, 0)
    school = program.get("school_name") or "the host institution"
    evidence = evidence_lines(profile, match)
    feature = (match.get("program_features_for_drafting") or [name])[0]
    strategy = match.get("writing_strategy") or "Connect applicant evidence to verified program requirements."
    metrics = applicant_intro(profile)
    if draft_language == "zh":
        return [
            f"我申请 {school} 的 {name}，核心动机是希望把现有学习和项目经历进一步连接到该项目的训练重点。当前匹配判断为：{score_line(match)}。",
            f"从简历证据看，申请人的基础包括：{metrics}。可用于正文展开的经历包括：{'; '.join(evidence[:3]) if evidence else 'needs_verification: 需要从简历补充具体课程、项目或科研证据'}。",
            f"项目侧已核实或待核实的连接点是：{feature}。文书写作策略应为：{strategy}",
            "下一轮修改时，应把每个经历改写成“背景、行动、结果、与项目要求的连接”，并核对官方 prompt、字数和提交格式。",
        ]
    if doc_type == "statement_of_purpose":
        opening = "My purpose in applying is to develop a clearer academic and professional direction through a program that matches my preparation and next-stage goals."
    elif doc_type == "personal_statement":
        opening = "My interest in this program grows from the academic and practical experiences that have shaped my current direction."
    elif doc_type == "motivation_letter":
        opening = "I am motivated to apply because the program offers a focused setting to turn my current preparation into more advanced study."
    else:
        opening = f"I am writing to apply for {name} at {school}."
    return [
        f"{opening} {score_line(match)}",
        f"My current profile includes {metrics}. The most useful evidence to develop in this draft is: {('; '.join(evidence[:3]) if evidence else 'needs_verification: add concrete course, project, research, or internship evidence from the CV')}.",
        f"The strongest program connection currently available is {feature}. This should be revised against the official prompt so every program-specific claim is supported by the source material.",
        f"Drafting strategy: {strategy}",
    ]


def render_document_brief(program: dict[str, Any], match: dict[str, Any], doc_types: list[str]) -> str:
    hard = program.get("hard_requirements") or {}
    lines = [
        "# Application Document Brief",
        "",
        f"- Program: {program_name(program, 0)}",
        f"- School: {program.get('school_name') or 'not_found'}",
        f"- Deadline: {program.get('deadline') or 'not_found'}",
        f"- {score_line(match)}",
        f"- {source_note(program)}",
        f"- Required writing drafts generated: {', '.join(doc_types) if doc_types else 'none found'}",
        f"- Recommendation letters: {compact(hard.get('recommendation_letters'))}",
        "",
        "## Writing Requirements",
        compact(hard.get("writing_requirements")),
        "",
        "## Required Documents",
        compact(program.get("required_documents")),
        "",
        "## Match Risks",
    ]
    risks = match.get("unmet_hard_requirements") or []
    if risks:
        lines.extend(f"- {risk}" for risk in risks)
    else:
        lines.append("- No unmet numeric hard requirement found by the first-pass analyzer.")
    lines.extend(["", "## Drafting Notes", match.get("writing_strategy") or "needs_verification"])
    return "\n".join(lines).rstrip() + "\n"


def render_draft(doc_type: str, program: dict[str, Any], match: dict[str, Any], profile: dict[str, Any], draft_language: str) -> str:
    title = doc_title(doc_type)
    paragraphs = drafting_paragraphs(doc_type, program, match, profile, draft_language)
    lines = [
        f"# {title}",
        "",
        f"- Applicant: {applicant_name(profile)}",
        f"- Program: {program_name(program, 0)}",
        f"- {source_note(program)}",
        "- Status: first-pass draft; verify official prompt, word limit, and facts before submission.",
        "",
    ]
    if draft_language != "zh":
        lines.extend(["Dear Admissions Committee,", ""])
    for paragraph in paragraphs:
        lines.append(paragraph)
        lines.append("")
    if draft_language != "zh":
        lines.extend(["Sincerely,", "", applicant_name(profile)])
    return "\n".join(lines).rstrip() + "\n"


def render_recommender_brief(program: dict[str, Any], match: dict[str, Any], profile: dict[str, Any]) -> str:
    evidence = evidence_lines(profile, match)
    lines = [
        "# Recommender Brief",
        "",
        f"- Applicant: {applicant_name(profile)}",
        f"- Program: {program_name(program, 0)}",
        f"- School: {program.get('school_name') or 'not_found'}",
        f"- Deadline: {program.get('deadline') or 'needs_verification'}",
        f"- Recommendation requirement: {compact((program.get('hard_requirements') or {}).get('recommendation_letters'))}",
        f"- {source_note(program)}",
        "",
        "## Suggested Evidence For The Recommender",
    ]
    if evidence:
        lines.extend(f"- {item}" for item in evidence[:6])
    else:
        lines.append("- needs_verification: add concrete evidence from class, research, project, internship, or advising relationship.")
    lines.extend(
        [
            "",
            "## Ethical Boundary",
            "This file is a briefing aid. The recommender should write, revise, and approve the final letter in their own voice.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_recommendation_template(program: dict[str, Any], profile: dict[str, Any]) -> str:
    return f"""# Recommendation Letter Template

To the Admissions Committee,

I am writing in support of {applicant_name(profile)}'s application to {program_name(program, 0)}.

I know the applicant through needs_verification: recommender relationship, course, research supervision, advising, or project context. In that setting, the applicant demonstrated needs_verification: one or two specific abilities relevant to the program.

One concrete example is needs_verification: specific episode, action, result, and what it shows about the applicant. This example is important for the application because it connects to needs_verification: verified program requirement or learning goal.

Based on this experience, I believe the applicant is prepared to contribute to and benefit from the program. I recommend them for admission.

Sincerely,

needs_verification: recommender name, title, institution, contact
"""


def render_request_email(program: dict[str, Any], profile: dict[str, Any]) -> str:
    return f"""# Recommendation Request Email Draft

Subject: Recommendation request for {program_name(program, 0)}

Dear Professor needs_verification,

I hope you are well. I am applying to {program_name(program, 0)} at {program.get('school_name') or 'needs_verification: school name'}, and the application requires {compact((program.get('hard_requirements') or {}).get('recommendation_letters'))} recommendation letter(s).

Would you be willing to support my application with a recommendation letter? I can provide my CV, the program information, a short summary of my relevant work, and any submission instructions.

The deadline is {program.get('deadline') or 'needs_verification'}, and the official submission method is needs_verification.

Thank you very much for considering my request.

Best regards,

{applicant_name(profile)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate program-specific application document drafts.")
    parser.add_argument("requirements_json", help="Normalized requirements JSON")
    parser.add_argument("match_report_json", help="Match report JSON")
    parser.add_argument("applicant_profile_json", help="Applicant profile JSON from extract_applicant_profile.py")
    parser.add_argument("--out-dir", required=True, help="Output directory for generated draft packages")
    parser.add_argument("--draft-language", choices=("auto", "en", "zh"), default="en", help="Draft language")
    parser.add_argument(
        "--draft-if-unspecified",
        action="store_true",
        help="Generate a cover letter draft even when no official writing requirement is found.",
    )
    args = parser.parse_args()

    programs = load_programs(Path(args.requirements_json))
    match_report = load_json(Path(args.match_report_json))
    profile = load_json(Path(args.applicant_profile_json))
    matches = match_by_program(match_report)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_language = profile.get("language") if args.draft_language == "auto" else args.draft_language
    if draft_language not in ("en", "zh"):
        draft_language = "en"

    summary: list[dict[str, Any]] = []
    for index, program in enumerate(programs):
        name = program_name(program, index)
        program_dir = out_dir / slugify(name)
        program_dir.mkdir(parents=True, exist_ok=True)
        match = find_match(program, matches)
        doc_types = required_doc_types(program)
        if not doc_types and args.draft_if_unspecified:
            doc_types = ["cover_letter"]
        (program_dir / "document_brief.md").write_text(render_document_brief(program, match, doc_types), encoding="utf-8")
        for doc_type in doc_types:
            filename = f"{doc_type}_draft.md"
            (program_dir / filename).write_text(render_draft(doc_type, program, match, profile, draft_language), encoding="utf-8")
        if recommendation_required(program):
            (program_dir / "recommender_brief.md").write_text(render_recommender_brief(program, match, profile), encoding="utf-8")
            (program_dir / "recommendation_letter_template.md").write_text(
                render_recommendation_template(program, profile), encoding="utf-8"
            )
            (program_dir / "recommendation_request_email.md").write_text(
                render_request_email(program, profile), encoding="utf-8"
            )
        summary.append(
            {
                "program": name,
                "directory": str(program_dir),
                "drafts": doc_types,
                "recommendation_materials": recommendation_required(program),
            }
        )
    (out_dir / "draft_generation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
