# Application

Prepares job application materials for human review: tailors the resume per job, drafts answers to common questions, and generates cover letters. All content is sourced from the user profile — the honesty guardrail prohibits fabricating experience.

## Files

- **resume.py** — `parse_resume()`, `generate_resume()`, `ResumeData`/`ResumeSection` — heuristic resume parser (.docx/.pdf/.md) and .docx generator (pure file I/O, no LLM)
- **preparer.py** — `prepare_application()`, `prepare_all_approved()` — orchestrates the full preparation flow
- **resume_tailor.py** — `tailor_resume()` — Claude rephrases/reorders resume content to match a specific job
- **question_answerer.py** — `answer_questions()`, `generate_cover_letter()` — Claude drafts answers and cover letters

## Public API

### Preparer (main entry point)

```python
from applybot.application.preparer import prepare_application, prepare_all_approved

# Prepare a single job application
app, gaps = prepare_application(job, custom_questions=["Why this role?"])
# app: Application (status=READY_FOR_REVIEW)
# gaps: list[ProfileGap] — info missing from profile

# Prepare all approved jobs
results: list[tuple[Application, list[ProfileGap]]] = prepare_all_approved()
```

### Resume Tailor

```python
from applybot.application.resume_tailor import tailor_resume

path: Path = tailor_resume(job, profile, base_resume_path, output_dir)
# Output: data/tailored/resume_{job_id}_{company}.docx
```

### Resume parsing & generation

```python
from applybot.application.resume import parse_resume, generate_resume, ResumeData

# Accepts .docx, .pdf, or .md — dispatched by extension
data: ResumeData = parse_resume(Path("resume.docx"))
# ResumeData: name, contact_info, summary, sections: list[ResumeSection]

output: Path = generate_resume(data, template_path, output_path)
# Creates a .docx preserving template formatting with tailored content
```

Parsing is purely heuristic (no LLM): `.docx` via python-docx heading styles, `.pdf` via pypdf layout extraction + ALL-CAPS/keyword heading detection, `.md` via ATX headings. PDF parsing only works on text-based PDFs. Sections are mapped to profile fields by `_map_resume_to_profile()` in `dashboard/pages/profile.py` (the dashboard keeps its own self-contained copy of this parser in `dashboard/services/resume.py`).

The tailor asks Claude for a `TailoringPlan` (summary rewrite + section edits) then applies it. The LLM prompt enforces: **rephrase and reorder only, never fabricate**.

### Question Answerer

```python
from applybot.application.question_answerer import answer_questions, generate_cover_letter

answers, gaps = answer_questions(job, profile, custom_questions)
# answers: dict[str, str] — question → answer
# gaps: list[ProfileGap] — {question, context} for missing info

cover_letter: str = generate_cover_letter(job, profile)
```

Default questions are answered automatically (why this role, relevant experience, greatest strength, etc.). Custom questions can be added per job.

### ProfileGap

```python
@dataclass
class ProfileGap:
    question: str   # What info is missing
    context: str    # Why it's needed
```

## Boundaries

- **Depends on**: `models` (Job, Application, UserProfile), `llm` (all content generation), `config`
- **Does not depend on**: Discovery, Tracking, or Dashboard
- **Used by**: Dashboard — the **"Build Approved Applications"** button on the Jobs page calls `prepare_all_approved()` directly via an HTMX POST to `/jobs/build-approved`. There is no Cloud Scheduler or background job for this step; it is always triggered manually by the user.
- The preparer writes Application records to the database; tailor and answerer are stateless
- Applications are created with status `READY_FOR_REVIEW` — human approval is required before submission
