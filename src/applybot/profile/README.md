# Profile

Manages the user's profile (structured data about skills, experiences, interests) and resume parsing/generation. This is the central source of truth that Discovery and Application components consult.

## Files

- **manager.py** — `ProfileManager` for CRUD operations and JSON import/export
- **resume.py** — Parse resumes into structured data and generate tailored .docx files

## Public API

### ProfileManager

```python
from applybot.profile.manager import ProfileManager

pm = ProfileManager()

profile = pm.get_profile()                         # UserProfile | None
profile = pm.get_or_create_profile("Name", "email") # Create if missing
profile = pm.update_profile(summary="...", skills={...})
skills  = pm.get_skills()                          # dict[str, Any]

pm.export_profile_json(Path("profile.json"))       # Dump to file
pm.import_profile_json(Path("profile.json"))       # Load from file
```

### Resume

```python
from applybot.profile.resume import parse_resume, generate_resume, ResumeData

# Accepts .docx, .pdf, or .md files — dispatched by extension
data: ResumeData = parse_resume(Path("resume.docx"))
data: ResumeData = parse_resume(Path("resume.pdf"))
data: ResumeData = parse_resume(Path("resume.md"))

# ResumeData contains: name, contact_info, summary, sections: list[ResumeSection]
# ResumeSection contains: heading, items: list[str]

output: Path = generate_resume(data, template_path, output_path)
# Creates a .docx preserving template formatting with tailored content
```

#### Parsing approach (heuristic, no LLM)

Parsing is purely heuristic — no LLM is involved. Each format uses text extraction and keyword/heading matching:

| Format | Extractor | Heading detection |
|--------|-----------|-------------------|
| `.docx` | `python-docx` | Word heading styles or short bold paragraphs |
| `.pdf`  | `pypdf` layout extraction | ALL-CAPS lines or known section keywords (single- and multi-word) |
| `.md`   | Built-in text read | ATX headings (`#`, `##`, `###`) |

> ⚠️ PDF parsing only works on text-based PDFs. Scanned/image PDFs will yield poor results since there is no text layer to extract.

**PDF heading detection (`_is_pdf_heading`)** uses the following heuristics in order:
1. Normalise whitespace; reject lines longer than 60 characters.
2. Reject lines that begin with bullet markers (`●`, `•`, `-`, `*`).
3. Short ALL-CAPS lines (≥ 3 chars) are strong heading signals.
4. Lines that *equal* or *start with* a known section keyword — including
   multi-word variants like `"work experience"`, `"technical skills"`, and
   `"relevant coursework"` — followed by whitespace, a colon, or end-of-string.
5. Lines that *contain* a known multi-word phrase such as `"programming languages"`
   (handles headings like "Familiar Programming Languages and Software").

Sections are mapped to profile fields via `_map_resume_to_profile()` in `dashboard/pages/profile.py` by keyword matching: headings containing "skill/technologies/tools" → `skills`, "experience/employment/work history/career" → `experiences`, "education/academic/degree/university/school" → `education`. The raw contact line is also scanned with a regex to extract an email address into `contact_info.email`.

#### LLM enrichment (post-parse)

After the heuristic pass saves the profile, the upload handler fires an async background task that calls the LLM to review the existing profile + parsed resume and write back a more complete profile. The LLM also extracts and populates all four `contact_info` fields (email, linkedin, phone, github) from the resume text. See `enrichment.py`.

```python
from applybot.profile.enrichment import enrich_profile_with_llm, enrich_profile_with_llm_async

# Synchronous — blocks until LLM + Firestore write complete
updated: UserProfile = enrich_profile_with_llm(profile, resume_text)

# Async background task — use from an async context (e.g. a Starlette handler)
asyncio.create_task(enrich_profile_with_llm_async(profile, resume_text))
```

The LLM is instructed to preserve existing data and only add or improve. It calls `get_llm()` with `tier="smart"`, routing to the configured provider's smart model. If enrichment fails, the heuristic-parsed profile written earlier remains in Firestore, and a persistent `enrichment_warning` field is set on the profile so the dashboard can show the user an explicit warning.

### CLI Bootstrap

```bash
# Import a resume and populate the database profile (.docx, .pdf, or .md)
applybot bootstrap-profile path/to/resume.docx
applybot bootstrap-profile resume.pdf --name "Jane Doe" --email jane@example.com
applybot bootstrap-profile resume.md
```

Parses the resume, extracts name/summary/skills/experiences/education sections, and stores them in the database via ProfileManager.

## Boundaries

- **Depends on**: `models` (UserProfile + Firestore CRUD), `config` (GCP project), `llm` (LLM client, used only in `enrichment.py`)
- **Does not depend on**: Discovery, Application, or Tracking
- **Used by**: Discovery (query building, relevance ranking), Application (resume tailoring, Q&A), Dashboard (profile display/edit)
- ProfileManager owns all DB access for the UserProfile table
- Resume functions are pure file I/O — no database or LLM calls
- `parse_resume()` is called by the dashboard's `POST /profile/resume` endpoint to parse uploaded files and backfill profile fields (name, summary)
- `enrich_profile_with_llm_async()` is called as a background task by the same endpoint after the heuristic parse to let the LLM fill in any remaining gaps
