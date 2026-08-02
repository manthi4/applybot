# Profile

Manages the user's profile (structured data about skills, experiences, interests) and resume parsing/generation. This is the central source of truth that Discovery and Application components consult.

## Files

- **resume.py** — Parse resumes into structured data and generate tailored .docx files

## Public API

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

### CLI Bootstrap

```bash
# Import a resume and populate the database profile (.docx, .pdf, or .md)
applybot bootstrap-profile path/to/resume.docx
applybot bootstrap-profile resume.pdf --name "Jane Doe" --email jane@example.com
applybot bootstrap-profile resume.md
```

Parses the resume, extracts name/summary/skills/experiences/education sections, and stores them in the database via `UserProfile`.

## Boundaries

- **Depends on**: `models` (UserProfile + Firestore CRUD), `config` (GCP project)
- **Does not depend on**: Discovery, Application, or Tracking
- **Used by**: Discovery (query building, relevance ranking), Application (resume tailoring, Q&A), Dashboard (profile display/edit)
- `UserProfile` owns all DB access for the profile table (get/save/update/delete)
- Resume functions are pure file I/O — no database or LLM calls
- `parse_resume()` is called by the dashboard's `POST /profile/resume` endpoint to parse uploaded files and backfill profile fields (name, summary)
