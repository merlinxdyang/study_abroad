---
name: study-abroad-application-manager
description: End-to-end study abroad and summer school application management. Use when Codex needs to parse admissions brochures or program PDFs, extract hard requirements and deadlines, compare programs against a CV/resume/profile, draft tailored cover letters or statements, and generate application checklists or calendar files for international applications.
---

# Study Abroad Application Manager

Use this skill to turn admissions brochures, program pages, and applicant materials into a traceable application package. Treat the brochure or official page as the source of truth.

## Operating Rules

- Base every requirement, deadline, fee, and document list on cited brochure text or an official page. Mark missing or ambiguous items as `not_found` or `needs_verification`.
- Never invent professor names, courses, requirements, fees, or deadlines. If live program details may have changed, verify against official sources before finalizing.
- Preserve original deadline dates and state the timezone. If the timezone is absent, write `timezone: not specified by source` and ask or infer only with a clear note.
- Separate hard requirements from soft fit signals. Do not let strong soft fit hide an unmet hard requirement.
- Treat the applicant material language separately from the final deliverable language. CVs/resumes may be Chinese or another language; extract evidence from the original text, preserve original names/titles, and translate/adapt evidence only for the target application document.
- If a CV/resume is not in the target application language, mark uncertain translations of school names, course names, awards, projects, and role titles as `needs_verification` instead of inventing polished wording.
- For Chinese users, write the analysis in Chinese unless they ask otherwise; keep document titles and official requirement names in their original language.
- Deliver artifacts in a workspace folder named for the applicant or program batch when files are requested.

## Workflow

1. Parse brochures or PDFs with `scripts/parse_pdf.py`.
2. Extract and normalize hard requirements with `scripts/extract_requirements.py`.
3. Compare requirements against the applicant profile/CV with `scripts/match_analyzer.py`.
4. Draft tailored letters from `templates/cover_letter_template.md`; read `references/academic_writing_guide.md` before writing final prose.
5. Generate deadline checklists and `.ics` calendar files with `scripts/generate_checklist.py`.

Run only the steps needed for the user request. For example, if the user only asks for a requirement table, stop after step 2.

## Script Guide

### Parse Brochures

```bash
python3 scripts/parse_pdf.py brochure1.pdf brochure2.pdf \
  --out parsed_programs.json \
  --text-dir extracted_text
```

The parser extracts text using available local PDF libraries, then emits structured JSON with:

- `school_name`
- `program_name`
- `deadline`
- `required_documents`
- `hard_requirements`
- `application_fee`
- `contact_info`
- `evidence`
- `source_text_path`

If extraction is empty or the file is scanned, report that OCR or a text version is needed.

### Extract Requirements

```bash
python3 scripts/extract_requirements.py parsed_programs.json \
  --json-out requirements.json \
  --md-out requirements_table.md
```

Use the Markdown table for human review. If a field is uncertain, keep the script output conservative and add a note for manual verification.

### Analyze Match

```bash
python3 scripts/match_analyzer.py requirements.json applicant_cv.pdf \
  --profile-language auto \
  --report-language auto \
  --out-md match_report.md \
  --out-json match_report.json
```

Scoring formula:

```text
match_score = hard_requirement_pass_rate * 60 + soft_fit_score * 40
```

Use script output as a first pass. The analyzer detects common profile languages, supports common Chinese labels such as `绩点`, `托福`, and `雅思`, and adds language-handling notes to the report. Manually inspect any non-English profile, borderline program, unusual grading scale, or requirement that depends on interpretation.

### Generate Deadline Tracker

```bash
python3 scripts/generate_checklist.py requirements.json \
  --timezone Asia/Shanghai \
  --out-md deadline_checklist.md \
  --out-ics application_deadlines.ics
```

Use official deadline timezone when available. If a deadline has only a date, create all-day calendar entries.

## Writing Letters

- Use `templates/cover_letter_template.md` as structure, not as final wording.
- Read `references/academic_writing_guide.md` before drafting polished English letters.
- If the resume/CV is Chinese or another non-English language, translate the applicant's evidence into natural application English only after preserving the original facts. Keep official names in their original language unless an official English translation is known.
- Personalize each letter with verified program features, courses, faculty, labs, or research directions.
- Avoid generic claims such as "world-class program" unless supported by a specific reason.
- If the user requests `.docx`, draft in Markdown first, then convert with an available document tool or Python `python-docx`; keep the Markdown source beside the generated document.

## Outputs

For a complete application package, provide:

- `parsed_programs.json`: structured brochure extraction.
- `requirements_table.md`: side-by-side hard requirement table.
- `match_report.md` and optionally `match_report.json`: score, rationale, risks, and recommendations.
- One tailored letter per program, preferably both `.md` source and `.docx` final if requested.
- `deadline_checklist.md` and `application_deadlines.ics`.

## Quality Gate

Before final response:

- Confirm all deadlines include source text or are marked for verification.
- Confirm unmet hard requirements are visible in the match report.
- Confirm the resume/CV language was handled explicitly, and any uncertain translated applicant evidence is marked `needs_verification`.
- Confirm letters do not contain placeholders such as `[Program]`, `[Professor]`, or unsupported claims.
- Confirm generated `.ics` files contain one event per checklist task plus the final deadline.
