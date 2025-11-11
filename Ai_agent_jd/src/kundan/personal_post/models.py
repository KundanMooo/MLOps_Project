"""Pydantic validation models using Annotated (pydantic v2)."""

from typing import Annotated
from pydantic import BaseModel, Field, HttpUrl, field_validator


class JobPostRequest(BaseModel):
    """Job posting validation model - simple and clean for API users"""

    job_text: Annotated[
        str,
        Field(
            min_length=10,
            description="Job description text (minimum 10 characters)",
            examples=["We're hiring a Python Developer! Join our amazing team."]
        )
    ]

    form_link: Annotated[
        HttpUrl,
        Field(
            description="Google Form URL for job applications",
            examples=["https://forms.gle/abc123", "https://docs.google.com/forms/d/e/xyz/viewform"]
        )
    ]

    @field_validator("job_text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Validate job text is not empty and meets minimum length"""
        text = v.strip()
        if len(text) < 10:
            raise ValueError("Job description must be at least 10 characters")
        return text

    @field_validator("form_link")
    @classmethod
    def validate_form_link(cls, v: HttpUrl) -> HttpUrl:
        """Validate that the link is a Google Form URL"""
        url_str = str(v)
        if "forms.gle" not in url_str and "docs.google.com/forms" not in url_str:
            raise ValueError("Must be a Google Form URL (forms.gle or docs.google.com/forms)")
        return v