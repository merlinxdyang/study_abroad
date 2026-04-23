# Study Abroad Application Manager

一个面向暑校、交换项目、留学申请的 Codex Skill，用于把招生简章、个人简历和申请截止日期整理成可追踪、可复核的申请包。

## 能做什么

- 解析招生简章 PDF，提取学校、项目、截止日期、申请材料、费用和联系方式。
- 提取硬性条件：GPA、TOEFL/IELTS、GRE/GMAT、先修课程、推荐信数量、文书要求。
- 将项目要求与申请人 CV/Resume 做交叉比对，输出匹配度评分、短板和推荐优先级。
- 先把单份简历抽取成可复核的申请人画像，再根据匹配度生成所需的 Cover Letter / Motivation Letter / SOP / Personal Statement / Essay 草稿。
- 当项目需要推荐信时，生成推荐人 brief、推荐信模板和推荐信请求邮件。
- 生成倒计时申请清单和可导入日历的 `.ics` 文件。

## 核心原则

- 严格基于招生简章或官方页面，不编造要求、教授、课程、费用或截止日期。
- 不确定信息标记为 `not_found` 或 `needs_verification`。
- 所有 deadline 必须保留原始日期，并标注时区；来源没有时区时明确说明。
- 硬性条件和软性背景分开分析，不用软性亮点掩盖硬性不达标。
- 简历语言和最终交付语言分开处理。用户上传的 CV/Resume 可能是中文或其他语言，需要先从原文提取事实，再按申请材料目标语言翻译和改写。
- 对学校名、课程名、奖项名、项目名、职位名等没有官方译名的信息，不臆造译名，标记为 `needs_verification`。

## 仓库结构

```text
study-abroad-application-manager/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── parse_pdf.py
│   ├── extract_applicant_profile.py
│   ├── extract_requirements.py
│   ├── match_analyzer.py
│   ├── generate_application_drafts.py
│   └── generate_checklist.py
├── templates/
│   ├── cover_letter_template.md
│   ├── recommendation_letter_template.md
│   ├── recommender_brief_template.md
│   ├── recommendation_request_email.md
│   ├── comparison_table.md
│   └── checklist_template.md
└── references/
    └── academic_writing_guide.md
```

## 安装方式

把 `study-abroad-application-manager/` 目录复制到 Codex skills 目录：

```bash
cp -R study-abroad-application-manager ~/.codex/skills/
```

之后即可在 Codex 中使用：

```text
$study-abroad-application-manager 帮我分析这 3 个 CS 暑校项目，我的简历在附件。
```

## 脚本用法

解析招生简章：

```bash
python3 study-abroad-application-manager/scripts/parse_pdf.py brochure.pdf \
  --out parsed_programs.json \
  --text-dir extracted_text
```

生成条件对比表：

```bash
python3 study-abroad-application-manager/scripts/extract_requirements.py parsed_programs.json \
  --json-out requirements.json \
  --md-out requirements_table.md
```

匹配分析：

```bash
python3 study-abroad-application-manager/scripts/extract_applicant_profile.py applicant_cv.pdf \
  --profile-language auto \
  --json-out applicant_profile.json \
  --md-out applicant_profile.md
```

```bash
python3 study-abroad-application-manager/scripts/match_analyzer.py requirements.json applicant_profile.json \
  --profile-language auto \
  --report-language auto \
  --out-md match_report.md \
  --out-json match_report.json
```

生成文书和推荐信材料：

```bash
python3 study-abroad-application-manager/scripts/generate_application_drafts.py requirements.json match_report.json applicant_profile.json \
  --out-dir application_package \
  --draft-language en
```

生成倒计时清单和日历文件：

```bash
python3 study-abroad-application-manager/scripts/generate_checklist.py requirements.json \
  --timezone Asia/Shanghai \
  --out-md deadline_checklist.md \
  --out-ics application_deadlines.ics
```

## 输出文件

- `parsed_programs.json`：简章结构化提取结果。
- `requirements_table.md`：项目硬性条件对比表。
- `applicant_profile.md` / `applicant_profile.json`：简历信息抽取、证据库和待核对项。
- `match_report.md` / `match_report.json`：匹配度、短板、推荐级别。
- `application_package/<program>/`：项目文书 brief、所需文书草稿、推荐信 brief/模板/请求邮件。
- `deadline_checklist.md`：按 T-60/T-45/T-30/T-14/T-7/T-1 组织的申请清单。
- `application_deadlines.ics`：可导入日历的申请任务。

## 注意事项

PDF 如果是扫描版，脚本可能无法直接提取文字，需要先 OCR 或提供文字版简章。`match_analyzer.py` 会自动识别常见简历语言，并支持中文字段如“绩点”“托福”“雅思”的初步解析；非英文简历的软性匹配和翻译后的申请表述仍需要人工复核。最终提交申请前，必须人工复核官方页面中的 deadline、材料清单、费用和文书题目。
