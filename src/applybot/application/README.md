# Application

Prepares job application materials for human review: tailors the resume per job, drafts answers to common questions, and generates cover letters. All content is sourced from the user profile — the honesty guardrail prohibits fabricating experience.

## Files

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

- **Depends on**: `models` (Job, Application ORM), `llm` (all content generation), `profile` (user profile + resume parsing/generation), `config`
- **Does not depend on**: Discovery, Tracking, or Dashboard
- **Used by**: CLI/scheduler entry points, Dashboard (via DB)
- The preparer writes Application records to the database; tailor and answerer are stateless
- Applications are created with status `READY_FOR_REVIEW` — human approval is required before submission
