# Profile

Manages the user's profile (structured data about skills, experiences, interests) and .docx resume parsing/generation. This is the central source of truth that Discovery and Application components consult.

## Files

- **manager.py** — `ProfileManager` for CRUD operations and JSON import/export
- **resume.py** — Parse .docx resumes into structured data and generate tailored .docx files

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

data: ResumeData = parse_resume(Path("resume.docx"))
# ResumeData contains: name, contact_info, sections: list[ResumeSection]
# ResumeSection contains: title, content: list[str]

output: Path = generate_resume(data, template_path, output_path)
# Creates a .docx preserving template formatting with tailored content
```

### CLI Bootstrap

```bash
# Import a .docx resume and populate the database profile
applybot bootstrap-profile path/to/resume.docx
applybot bootstrap-profile resume.docx --name "Jane Doe" --email jane@example.com
```

Parses the resume, extracts name/summary/skills/experiences/education sections, and stores them in the database via ProfileManager.

## Boundaries

- **Depends on**: `models` (UserProfile + Firestore CRUD), `config` (GCP project)
- **Does not depend on**: LLM, Discovery, Application, or Tracking
- **Used by**: Discovery (query building, relevance ranking), Application (resume tailoring, Q&A), Dashboard (profile display/edit)
- ProfileManager owns all DB access for the UserProfile table
- Resume functions are pure file I/O — no database or LLM calls
- `parse_resume()` is called by the dashboard's `POST /profile/resume` endpoint to parse uploaded .docx files and backfill profile fields (name, summary)
