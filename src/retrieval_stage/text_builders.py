from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from docx import Document


_WHITESPACE_RE = re.compile(r"\s+")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return _WHITESPACE_RE.sub(" ", text)


def _join_parts(parts: Iterable[str]) -> str:
    return "\n".join(part for part in (_clean(p) for p in parts) if part)


class CandidateTextBuilder:
    """Build E5 passage text from allowed candidate profile fields only."""

    def build(self, candidate: dict[str, Any]) -> str:
        profile = candidate.get("profile") or {}
        parts: list[str] = []

        parts.extend(
            [
                self._line("Headline", profile.get("headline")),
                self._line("Summary", profile.get("summary")),
                self._line("Current title", profile.get("current_title")),
                self._line("Current industry", profile.get("current_industry")),
                self._line("Years of experience", profile.get("years_of_experience")),
            ]
        )

        career_parts = []
        for role in candidate.get("career_history") or []:
            career_parts.append(
                _join_parts(
                    [
                        self._line("Title", role.get("title")),
                        self._line("Industry", role.get("industry")),
                        self._line("Description", role.get("description")),
                    ]
                )
            )
        if career_parts:
            parts.append("Career history:\n" + "\n".join(career_parts))

        skill_parts = []
        for skill in candidate.get("skills") or []:
            skill_parts.append(
                _join_parts(
                    [
                        self._line("Skill", skill.get("name")),
                        self._line("Proficiency", skill.get("proficiency")),
                        self._duration_line(skill.get("duration_months")),
                    ]
                )
            )
        if skill_parts:
            parts.append("Skills:\n" + "\n".join(skill_parts))

        education_parts = []
        for education in candidate.get("education") or []:
            education_parts.append(
                _join_parts(
                    [
                        self._line("Degree", education.get("degree")),
                        self._line("Field of study", education.get("field_of_study")),
                    ]
                )
            )
        if education_parts:
            parts.append("Education:\n" + "\n".join(education_parts))

        certification_parts = []
        for certification in candidate.get("certifications") or []:
            certification_parts.append(
                _join_parts(
                    [
                        self._line("Certification", certification.get("name")),
                        self._line("Issuer", certification.get("issuer")),
                    ]
                )
            )
        if certification_parts:
            parts.append("Certifications:\n" + "\n".join(certification_parts))

        return _join_parts(parts)

    @staticmethod
    def _line(label: str, value: Any) -> str:
        cleaned = _clean(value)
        return f"{label}: {cleaned}" if cleaned else ""

    @staticmethod
    def _duration_line(value: Any) -> str:
        if value is None or value == "":
            return ""
        return f"Duration months: {_clean(value)}"


class JDTextBuilder:
    """Build E5 query text from structured job-description files."""

    json_priority_keys = (
        "title",
        "job_title",
        "role",
        "company",
        "location",
        "employment_type",
        "experience",
        "experience_required",
        "responsibilities",
        "requirements",
        "must_have",
        "good_to_have",
        "skills",
        "preferred_skills",
        "qualifications",
        "disqualifiers",
        "ideal_candidate",
        "logistics",
    )

    docx_priority_headings = (
        "job description",
        "company",
        "location",
        "employment type",
        "experience required",
        "what you'd actually be doing",
        "what we mean by",
        "the skills inventory",
        "things you absolutely need",
        "things we'd like you to have",
        "things we explicitly do not want",
        "on location",
        "how to read between the lines",
    )

    def build_from_file(self, path: str | Path) -> str:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self.build_from_json(json.loads(path.read_text(encoding="utf-8")))
        if suffix == ".docx":
            return self.build_from_docx(path)
        if suffix in {".txt", ".md"}:
            return _clean(path.read_text(encoding="utf-8"))
        raise ValueError(f"Unsupported JD file type: {path.suffix}")

    def build_from_json(self, jd: dict[str, Any]) -> str:
        parts: list[str] = []
        seen: set[str] = set()

        for key in self.json_priority_keys:
            if key in jd:
                parts.append(self._render_json_value(key, jd[key]))
                seen.add(key)

        for key, value in jd.items():
            if key not in seen:
                parts.append(self._render_json_value(key, value))

        return _join_parts(parts)

    def build_from_docx(self, path: str | Path) -> str:
        document = Document(str(path))
        blocks: list[str] = []
        current_heading = ""

        for paragraph in document.paragraphs:
            text = _clean(paragraph.text)
            if not text:
                continue

            style_name = (paragraph.style.name if paragraph.style else "").lower()
            is_heading = style_name.startswith("heading") or style_name == "title"
            is_list = "list" in style_name

            if is_heading:
                current_heading = text
                blocks.append(text)
                continue

            lowered_heading = current_heading.lower()
            text_lower = text.lower()
            is_priority = any(
                heading in lowered_heading or text_lower.startswith(heading)
                for heading in self.docx_priority_headings
            )

            if is_priority or is_list or self._looks_like_key_value(text):
                prefix = "Requirement" if is_list else "Detail"
                blocks.append(f"{prefix}: {text}")
            else:
                blocks.append(text)

        return _join_parts(blocks)

    def _render_json_value(self, key: str, value: Any) -> str:
        label = key.replace("_", " ").title()
        if isinstance(value, dict):
            rendered = [
                self._render_json_value(str(child_key), child_value)
                for child_key, child_value in value.items()
            ]
            return _join_parts([f"{label}:", *rendered])
        if isinstance(value, list):
            rendered_items = []
            for item in value:
                if isinstance(item, dict):
                    rendered_items.append(self._render_json_value("item", item))
                else:
                    rendered_items.append(_clean(item))
            return _join_parts([f"{label}:", *rendered_items])
        cleaned = _clean(value)
        return f"{label}: {cleaned}" if cleaned else ""

    @staticmethod
    def _looks_like_key_value(text: str) -> bool:
        return ":" in text and len(text.split(":", 1)[0]) <= 40
