"""Pydantic models shared across the pipeline."""

from pydantic import BaseModel, Field


class JobEvaluation(BaseModel):
    """Structured evaluation result for a single job listing."""

    is_relevant: bool = Field(description="True if role fits MSc Chemist with 3.5 yrs research/cleantech exp")
    match_score: int = Field(description="Score 1-10 for candidate profile fit")
    role_category: str = Field(
        description="One of: R&D Lab, Cleantech, Analytical, Process/Industry, Pharma QA/Reg, Consulting/App"
    )
    degree_fit: str = Field(
        description="Short badge: 'Ideal for MSc+Exp', 'MSc/BSc', 'PhD or Equiv Exp', or 'Strict PhD Only'"
    )
    language_req: str = Field(
        description="Short badge: 'English', 'EN + DE B1/B2 OK', or 'Fluent DE Required'"
    )
    one_line_summary: str = Field(
        description="Concise 1-sentence reason why this job fits or what to watch out for"
    )
