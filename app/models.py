
from typing import Optional, Literal, Union
from pydantic import BaseModel, Field
import uuid


# --- Incoming Payload Model ---
class WebMonitorPayload(BaseModel):
    """
    Pydantic model for the data sent from any monitor client.
    The `type` field is used to route the payload to the correct analyzer.
    """
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["web-monitor", "truthsocial", "twitter"]
    url: Optional[str] = None
    username: Optional[str] = None
    content_id: Optional[str] = Field(default=None, alias="content-id")
    content: str
    ip: str


# --- Social Media Analysis Models ---
class SocialMediaAnalysisOutput(BaseModel):
    """
    Represents the final output of the SocialMediaPostAnalyzer pipeline.
    """
    topic_classification: Optional[str] = None
    topic_confidence: Optional[float] = None
    topic_reasoning: Optional[str] = None
    price_direction: Optional[str] = None
    price_confidence: Optional[float] = None
    price_reasoning: Optional[str] = None

class IrrelevantSocialMediaContent(BaseModel):
    """
    Indicates that the social media post is not relevant for trading.
    """
    reason: str

class FailedSocialMediaAnalysis(BaseModel):
    """Indicates that the social media analysis failed."""
    error_message: str


# --- FED Decision Analysis Models ---
class FEDExpectation(BaseModel):
    """Model for expected FED decisions, loaded from a file."""
    expected_interest_rate_change_type: Literal["increase", "decrease", "hold", "uncertain"]
    expected_interest_rate_change_amount: Optional[str] = None
    expected_narrative: Literal["hawkish", "dovish", "neutral", "mixed"]
    notes: Optional[str] = None

class FEDDecisionImpact(BaseModel):
    """Output model for the FED decision analysis agent."""
    impact_on_bitcoin: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str
    actual_fed_decision_summary: str
    actual_interest_rate_change_type: Optional[Literal["increase", "decrease", "hold"]] = None
    actual_interest_rate_change_amount: Optional[str] = None
    actual_narrative: Optional[Literal["hawkish", "dovish", "neutral", "mixed"]] = None

class FailedFEDAnalysis(BaseModel):
    """Indicates that the FED decision analysis failed."""
    error_message: str

class IrrelevantFEDContent(BaseModel):
    """
    Indicates that the provided content is not relevant to a FED interest rate decision.
    """
    reason: str


# --- Union Types for Analysis Results ---
FEDAnalysisResult = Union[FEDDecisionImpact, FailedFEDAnalysis, IrrelevantFEDContent]
SocialMediaAnalysisResult = Union[SocialMediaAnalysisOutput, FailedSocialMediaAnalysis, IrrelevantSocialMediaContent]

# A general type for any possible analysis outcome
AnyAnalysisResult = Union[FEDAnalysisResult, SocialMediaAnalysisResult]
