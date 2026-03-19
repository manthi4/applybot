"""Resume manager — parse and generate .docx resumes."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)


@dataclass
class ResumeSection:
    """A logical section of the resume (e.g., Experience, Skills)."""

    heading: str
    items: list[str] = field(default_factory=list)


@dataclass
class ResumeData:
    """Structured representation of a parsed resume."""

    name: str = ""
    contact_info: str = ""
    summary: str = ""
    sections: list[ResumeSection] = field(default_factory=list)

    def get_section(self, heading: str) -> ResumeSection | None:
        """Find a section by heading (case-insensitive)."""
        for section in self.sections:
            if section.heading.lower() == heading.lower():
                return section
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "contact_info": self.contact_info,
            "summary": self.summary,
            "sections": [
                {"heading": s.heading, "items": s.items} for s in self.sections
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResumeData:
        sections = [
            ResumeSection(heading=s["heading"], items=s["items"])
            for s in data.get("sections", [])
        ]
        return cls(
            name=data.get("name", ""),
            contact_info=data.get("contact_info", ""),
            summary=data.get("summary", ""),
            sections=sections,
        )


def _is_heading(paragraph: Paragraph) -> bool:
    """Check if a paragraph is a heading (by style or bold formatting)."""
    style_name = (paragraph.style.name or "").lower()
    if "heading" in style_name:
        return True
    # Check if entire paragraph is bold and short (likely a section header)
    if paragraph.runs and all(r.bold for r in paragraph.runs if r.text.strip()):
        text = paragraph.text.strip()
        if text and len(text) < 80:
            return True
    return False


def parse_resume(path: Path) -> ResumeData:
    """Parse a .docx resume into structured ResumeData.

    Heuristic approach:
    - First non-empty paragraph = name
    - Heading-style paragraphs start new sections
    - Everything else is items within the current section
    """
    doc = Document(str(path))
    data = ResumeData()
    current_section: ResumeSection | None = None
    found_name = False

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # First non-empty text is the name
        if not found_name:
            data.name = text
            found_name = True
            continue

        # Second before any heading is contact info
        if not data.contact_info and current_section is None and not _is_heading(para):
            data.contact_info = text
            continue

        if _is_heading(para):
            current_section = ResumeSection(heading=text)
            data.sections.append(current_section)
        elif current_section is not None:
            current_section.items.append(text)
        else:
            # Text before any section heading — treat as summary
            if data.summary:
                data.summary += "\n" + text
            else:
                data.summary = text

    logger.info("Parsed resume: %s, %d sections", data.name, len(data.sections))
    return data


def generate_resume(data: ResumeData, template_path: Path, output_path: Path) -> Path:
    """Generate a tailored .docx resume from ResumeData using an existing .docx as template.

    Strategy: copy the template, then replace content while preserving formatting.
    For MVP, we create a clean document based on the template's styles.
    """
    # Copy the template to preserve styles and formatting
    template_doc = Document(str(template_path))
    doc = Document(str(template_path))

    # Clear all content from the copy
    for para in doc.paragraphs[:]:
        p_element = para._element
        p_element.getparent().remove(p_element)

    # Also clear tables if any
    for table in doc.tables[:]:
        t_element = table._element
        t_element.getparent().remove(t_element)

    # Get the heading style from the template
    heading_style = None
    normal_style = None
    for style in template_doc.styles:
        if style.name and "heading" in style.name.lower() and "1" in style.name:
            heading_style = style.name
        if style.name == "Normal":
            normal_style = style.name
    heading_style = heading_style or "Heading 1"
    normal_style = normal_style or "Normal"

    # Build the new document
    # Name
    name_para = doc.add_paragraph(data.name)
    _apply_safe_style(name_para, "Title", doc)

    # Contact info
    if data.contact_info:
        doc.add_paragraph(data.contact_info)

    # Summary
    if data.summary:
        doc.add_paragraph(data.summary)

    # Sections
    for section in data.sections:
        _apply_safe_style(doc.add_paragraph(section.heading), heading_style, doc)
        for item in section.items:
            # Use bullet style if available
            p = doc.add_paragraph(item)
            _apply_safe_style(p, "List Bullet", doc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    logger.info("Generated resume at %s", output_path)
    return output_path


def _apply_safe_style(paragraph: Paragraph, style_name: str, doc: Document) -> None:
    """Apply a style if it exists, otherwise fall back to Normal."""
    try:
        paragraph.style = doc.styles[style_name]
    except KeyError:
        pass  # Keep default style
