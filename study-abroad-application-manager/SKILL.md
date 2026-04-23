---
name: study-abroad-application-manager
description: End-to-end study abroad and summer school application management. Use when Codex needs to parse admissions brochures or program PDFs, extract hard requirements and deadlines, compare programs against a CV/resume/profile, draft tailored cover letters or statements, and generate application checklists or calendar files for international applications.
---

# Study Abroad Application Manager

Use this skill to turn admissions brochures, program pages, and one applicant CV/resume into a traceable application package. Treat the brochure or official page as the source of truth, and treat the resume as evidence to be extracted, verified, and reused in drafts.

## Operating Rules

- Base every requirement, deadline, fee, and document list on cited brochure text or an official page. Mark missing or ambiguous items as `not_found` or `needs_verification`.
- Never invent professor names, courses, requirements, fees, or deadlines. If live program details may have changed, verify against official sources before finalizing.
- Preserve original deadline dates and state the timezone. If the timezone is absent, write `timezone: not specified by source` and ask or infer only with a clear note.
- Separate hard requirements from soft fit signals. Do not let strong soft fit hide an unmet hard requirement.
- Treat the applicant material language separately from the final deliverable language. CVs/resumes may be Chinese or another language; extract evidence from the original text, preserve original names/titles, and translate/adapt evidence only for the target application document.
- If a CV/resume is not in the target application language, mark uncertain translations of school names, course names, awards, projects, and role titles as `needs_verification` instead of inventing polished wording.
- For Chinese users, write the analysis in Chinese unless they ask otherwise; keep document titles and official requirement names in their original language.
- Deliver artifacts in a workspace folder named for the applicant or program batch when files are requested.
- If the user provides only one resume plus target programs, produce a complete first-pass package: applicant profile, requirement table, match report, required writing drafts, recommendation materials when needed, and checklist.
- If a program requires a cover letter, motivation letter, SOP, personal statement, essay, or recommendation letters, do not stop at matching. Generate the corresponding first-pass draft or recommender packet, clearly marking facts or prompts that need verification.
- Recommendation letters are recommender-authored documents. You may draft a recommender brief, request email, and editable template, but do not pretend to be the recommender or create a final letter for submission without recommender review.

## Workflow

1. Parse brochures or PDFs with `scripts/parse_pdf.py`.
2. Extract and normalize hard requirements with `scripts/extract_requirements.py`.
3. Extract the resume into a reviewable applicant profile with `scripts/extract_applicant_profile.py`.
4. Compare requirements against `applicant_profile.json` with `scripts/match_analyzer.py`.
5. Generate required writing drafts and recommendation materials with `scripts/generate_application_drafts.py`; read `references/academic_writing_guide.md` before polishing final prose.
6. Generate deadline checklists and `.ics` calendar files with `scripts/generate_checklist.py`.

Run only the steps needed for the user request. For example, if the user only asks for a requirement table, stop after step 2.

For the common user request "I only have one resume; help me choose programs and draft whatever the application needs", run steps 1-6 and return the package paths.

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
python3 scripts/extract_applicant_profile.py applicant_cv.pdf \
  --profile-language auto \
  --json-out applicant_profile.json \
  --md-out applicant_profile.md
```

Use `applicant_profile.md` for human review. It should expose extracted evidence, missing facts, and `needs_verification` items before any writing draft relies on them.

```bash
python3 scripts/match_analyzer.py requirements.json applicant_profile.json \
  --profile-language auto \
  --report-language auto \
  --out-md match_report.md \
  --out-json match_report.json
```

Scoring formula:

```text
match_score = hard_requirement_pass_rate * 60 + soft_fit_score * 40
```

Use script output as a first pass. The analyzer detects common profile languages, supports common Chinese labels such as `绩点`, `托福`, and `雅思`, and adds language-handling notes, drafting evidence, and writing strategy to the report. Manually inspect any non-English profile, borderline program, unusual grading scale, or requirement that depends on interpretation.

### Generate Application Drafts

```bash
python3 scripts/generate_application_drafts.py requirements.json match_report.json applicant_profile.json \
  --out-dir application_package \
  --draft-language en
```

The generator creates one folder per program. It generates:

- `document_brief.md`: required documents, writing prompts found, match risks, and drafting strategy.
- `cover_letter_draft.md`, `motivation_letter_draft.md`, `statement_of_purpose_draft.md`, `personal_statement_draft.md`, or `essay_draft.md` when the requirement text asks for them.
- `recommender_brief.md`, `recommendation_letter_template.md`, and `recommendation_request_email.md` when recommendation letters are required.

If the official source does not clearly state a writing requirement, do not invent one. Use `--draft-if-unspecified` only when the user explicitly asks for a general draft despite missing official requirements.

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
- Use `templates/recommender_brief_template.md`, `templates/recommendation_letter_template.md`, and `templates/recommendation_request_email.md` when recommendation letters are required.
- Read `references/academic_writing_guide.md` before drafting polished English letters.
- If the resume/CV is Chinese or another non-English language, translate the applicant's evidence into natural application English only after preserving the original facts. Keep official names in their original language unless an official English translation is known.
- Personalize each letter with verified program features, courses, faculty, labs, or research directions.
- Avoid generic claims such as "world-class program" unless supported by a specific reason.
- If the user requests `.docx`, draft in Markdown first, then convert with an available document tool or Python `python-docx`; keep the Markdown source beside the generated document.
- When the deterministic draft generator produces a rough draft, revise it manually for natural prose, prompt fit, and specificity before presenting it as application-ready.

## Outputs

For a complete application package, provide:

- `parsed_programs.json`: structured brochure extraction.
- `requirements_table.md`: side-by-side hard requirement table.
- `applicant_profile.md` and `applicant_profile.json`: reviewable resume extraction and reusable evidence bank.
- `match_report.md` and optionally `match_report.json`: score, rationale, risks, and recommendations.
- `application_package/<program>/`: document brief, required writing drafts, and recommendation packet when applicable.
- `deadline_checklist.md` and `application_deadlines.ics`.

## Quality Gate

Before final response:

- Confirm all deadlines include source text or are marked for verification.
- Confirm unmet hard requirements are visible in the match report.
- Confirm the applicant profile has been reviewed for obvious extraction misses before drafting.
- Confirm the resume/CV language was handled explicitly, and any uncertain translated applicant evidence is marked `needs_verification`.
- Confirm letters do not contain placeholders such as `[Program]`, `[Professor]`, or unsupported claims.
- Confirm every required writing document found in `writing_requirements` or `required_documents` has a draft, or is explicitly marked `needs_verification`.
- Confirm recommendation materials are clearly framed as recommender aids, not final recommender-authored submissions.
- Confirm generated `.ics` files contain one event per checklist task plus the final deadline.
