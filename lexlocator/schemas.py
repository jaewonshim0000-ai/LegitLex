"""Pydantic models for the API and the Claude tool-use schema.

The same `Verdict` shape is:
  - returned from the /ask endpoint
  - what Claude is forced to produce via tool_use
  - what the frontend renders
This keeps the contract tight from LLM -> server -> client.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

class Location(BaseModel):
    city: str = ""
    county: str = ""
    state: str = ""
    country: str = "US"
    lat: Optional[float] = None
    lng: Optional[float] = None


# ---------------------------------------------------------------------------
# Verdict (the structured legal answer)
# ---------------------------------------------------------------------------

VerdictType = Literal["yes", "no", "warning", "unknown"]


class Citation(BaseModel):
    level: Literal["city", "county", "state", "federal", "unknown"] = "unknown"
    jurisdiction: str = ""
    section_id: str
    section_name: str = ""
    paraphrase: str
    source_url: str = ""
    page_start: int = 0
    last_amended: str = ""   # year of most recent amendment, from the history note


class Verdict(BaseModel):
    verdict: VerdictType = Field(
        description=(
            "'yes' = the activity is clearly allowed by the retrieved law. "
            "'no' = clearly prohibited. "
            "'warning' = conditionally allowed with restrictions. "
            "'unknown' = retrieved law does NOT answer the question."
        )
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="0.0-1.0. How confident you are that the retrieved sections "
                    "actually settle this question. Low if you had to extrapolate."
    )
    answer: str = Field(
        description="Plain-English answer, 1-3 sentences. No legal jargon."
    )
    citations: list[Citation] = Field(
        description="Every law section you relied on. Empty if verdict=unknown."
    )
    caveats: str = Field(
        default="",
        description="What's NOT covered: e.g. state/federal rules that may also "
                    "apply but were not in the retrieved sections."
    )
    penalty: str = Field(
        default="",
        description="The fine or punishment for doing this, taken ONLY from the "
                    "retrieved law. Plain English, e.g. 'Infraction: fine up to "
                    "$250 for a first offense.' Empty / 'Not specified in the "
                    "retrieved law' if the sections don't state a penalty."
    )
    penalty_severity: Literal[
        "none", "infraction", "civil", "misdemeanor", "felony", "unknown"
    ] = Field(
        default="unknown",
        description="Severity tier of the penalty, for UI coloring. 'none' if the "
                    "action is allowed. 'unknown' if not stated in retrieved law."
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Where the jurisdiction layers DISAGREE — e.g. 'California "
                    "permits Class 3 e-bikes on paths, but Irvine prohibits them; "
                    "the stricter local rule governs here.' Empty if all layers "
                    "agree or only one applies. State which level governs."
    )


# ---------------------------------------------------------------------------
# Retrieval debug payload (returned alongside the Verdict for transparency)
# ---------------------------------------------------------------------------

class RetrievedSection(BaseModel):
    section_id: str
    section_name: str
    level: str
    jurisdiction: str
    breadcrumb: str
    page_start: int
    distance: float
    text_preview: str


# ---------------------------------------------------------------------------
# API request/response envelopes
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    location: Location
    speed_kmh: Optional[float] = None  # CAG: real-time sensor context
    activity: Optional[str] = None     # CAG: optional structured context


class CompareRequest(BaseModel):
    question: str
    location_a: Location
    location_b: Location


class AskResponse(BaseModel):
    verdict: Verdict
    location: Location
    retrieved: list[RetrievedSection]
    snapshot_id: str               # for evidence collection
    timestamp_utc: str
    disclaimer: str = (
        "This is legal information, not legal advice. Laws change; verify "
        "against the official municipal code before acting."
    )


class SignScanResponse(BaseModel):
    sign_text: str = Field(description="Text extracted from the sign")
    extracted_rule: str = Field(description="What the sign says you may/may not do")
    verified_against_code: bool = Field(
        description="True if a matching official ordinance was found"
    )
    matching_citations: list[Citation] = []
    note: str = ""
    location: Location
    timestamp_utc: str
    disclaimer: str = (
        "Signs can be unofficial, outdated, or privately posted. Verified status "
        "means a similar rule exists in the scraped official code only."
    )


class JurisdictionResponse(BaseModel):
    location: Location
    covered_levels: list[str]      # which levels we have data for
    section_count_by_level: dict[str, int]


# ---------------------------------------------------------------------------
# Complaint analysis
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "medium", "high", "critical", "unknown"]


class Allegation(BaseModel):
    claim: str = Field(description="One allegation/issue raised, in plain English.")
    law_area: str = Field(default="", description="Topic, e.g. 'noise', 'zoning'.")


class ComplaintAnalysis(BaseModel):
    summary: str = Field(description="Plain-English summary of the complaint, 2-4 sentences.")
    complaint_type: str = Field(
        default="",
        description="e.g. 'Code enforcement notice', 'Civil lawsuit', "
                    "'Traffic citation', 'HOA violation', 'Unknown'."
    )
    allegations: list[Allegation] = Field(
        default_factory=list,
        description="The specific things the complaint accuses the person of."
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Laws from the retrieved dataset that apply. Empty if none match."
    )
    risk_level: RiskLevel = Field(
        default="unknown",
        description="Overall exposure: low / medium / high / critical."
    )
    risk_rationale: str = Field(
        default="", description="Why that risk level — grounded in the laws + allegations."
    )
    potential_penalties: str = Field(
        default="", description="Fines/punishment exposure, from the retrieved law only."
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="General, practical next steps (e.g. respond by deadline, "
                    "gather evidence, consult an attorney). Not legal advice."
    )
    deadline: str = Field(
        default="", description="Any response deadline stated in the complaint, else ''."
    )
    caveats: str = Field(default="", description="Limits of this analysis.")


class ComplaintResponse(BaseModel):
    analysis: ComplaintAnalysis
    location: Location
    extracted_text_preview: str
    retrieved: list[RetrievedSection]
    snapshot_id: str
    timestamp_utc: str
    disclaimer: str = (
        "This is an automated, plain-language summary for information only — NOT "
        "legal advice. It reflects only the laws in this app's dataset and may "
        "miss claims or deadlines. Consult a licensed attorney about any real "
        "complaint, and do not miss any response deadline."
    )
