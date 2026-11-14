"""Pydantic models shared across the pipeline."""

from pydantic import BaseModel, Field


class JobEvaluation(BaseModel):
    """Structured critical evaluation result for a single job listing."""

    is_relevant: bool = Field(
        description="True if role is a viable target (match_score >= 6) fitting candidate's profile; False if disqualified or irrelevant"
    )
    match_score: int = Field(
        description="Calibrated score 1-10 evaluated critically against candidate CV and career tracks (1-3 disqualified, 4-5 poor fit, 6 viable baseline, 7-8 strong match, 9-10 exceptional dream fit)"
    )
    role_category: str = Field(
        description="One of: R&D Lab, Cleantech, Analytical, Process/Industry, Pharma QA/Reg, Consulting/App"
    )
    degree_fit: str = Field(
        description="Degree & seniority badge: 'Ideal for MSc+Exp', 'MSc/BSc Suitable', 'PhD or Equiv Exp', 'Overqualified (PhD Req)', 'Vocational / Too Junior', or 'Non-scientific'"
    )
    language_req: str = Field(
        description="Language badge: 'English (C1)', 'EN + DE B1/B2 OK', or 'Fluent DE Required (C1/C2)'"
    )
    track_alignment: str = Field(
        default="General scientific role",
        description="Specific career direction: which of Envisioned Tracks 1-5 it advances, or if it deviates/tangential",
    )
    fit_strengths: str = Field(
        default="Matches chemistry degree background.",
        description="Concrete verified CV skills, techniques, or experience directly matching the vacancy duties (e.g. SPPS peptide synthesis, HPLC stationary phase development, ion-exchange resins, LCMS/MALDI, NMR)",
    )
    career_gaps: str = Field(
        default="No major disqualifiers noted.",
        description="Critical, honest assessment of what candidate lacks: scale differences (commercial GMP plant vs academic benchtop), missing domains (mammalian cell culture, formulation), formal PhD requirement, or language",
    )
    one_line_summary: str = Field(
        description="Structured critical assessment formatted exactly as: '🎯 Track: <track_alignment> | ✅ Fit: <fit_strengths> | ⚠️ Gaps: <career_gaps>'",
    )
    scorer: str = Field(
        default="gemini",
        description="Evaluator engine used: 'gemini' or 'heuristic'",
    )
