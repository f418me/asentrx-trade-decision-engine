from typing import Optional, Literal, Set, List, Dict, Union
from pydantic import BaseModel, Field
import uuid


# --- Web Monitor Payload Model (from asentrx-web-monitor) ---
class WebMonitorPayload(BaseModel):
    """
    Pydantic model for the data sent from the web-monitor client.
    """
    uuid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this payload instance."
    )
    type: Literal["web-monitor", "truthsocial", "twitter"] = Field(
        default="web-monitor",
        description="The type of monitor or source from which the data originates."
    )
    url: Optional[str] = Field(
        default=None,
        description="The URL of the monitored article or source."
    )
    username: Optional[str] = Field(
        default=None,
        description="Optional username associated with the content."
    )
    content_id: Optional[str] = Field(
        default="",
        alias="content-id",  # Important for JSON output
        description="Optional ID for the specific content (e.g., ID of a tweet or post, here article ID from URL)."
    )
    content: str = Field(
        description="The main content of the message or data point."
    )
    ip: str = Field(
        description="The IP address from which the data is sent (here, the public IP of the Fly.io container)."
    )

# --- AI Agent Input/Output Models (adapted from asentrx_agent.py and new for FED) ---

class TopicClassification(BaseModel):
    """Result of the first agent, classifying the topic."""
    classification: str  # Expected: "market", "bitcoin", "tariffs", "others", "fed_decision"
    confidence: float
    reasoning: str

class PriceDirectionPrediction(BaseModel):
    """Predicts the likely direction of price change for a specific topic."""
    direction: str  # Expected: "up", "down", "neutral"
    confidence: float
    reasoning: str

class Failed(BaseModel):
    """Unable to find a satisfactory choice for the current task."""

class AnalysisOutput(BaseModel):
    """
    Represents the final output of the ContentAnalyzer pipeline.
    Fields will be None if a corresponding step was not executed or did not produce a valid result.
    """
    topic_classification: Optional[str] = None
    topic_confidence: Optional[float] = None
    topic_reasoning: Optional[str] = None
    price_direction: Optional[str] = None
    price_confidence: Optional[float] = None
    price_reasoning: Optional[str] = None

# --- NEW: Models for FED Decision Agent ---

class FEDExpectation(BaseModel):
    """Model for expected FED decisions, loaded from a file."""
    expected_interest_rate_change_type: Literal["increase", "decrease", "hold", "uncertain"] = Field(
        description="Expected action on interest rates."
    )
    expected_interest_rate_change_amount: Optional[str] = Field(
        default=None,
        description="Expected amount of change, e.g., '0.25%'. Valid if type is not 'hold'."
    )
    expected_narrative: Literal["hawkish", "dovish", "neutral", "mixed"] = Field(
        description="Expected overall narrative tone (hawkish=tightening, dovish=easing)."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Any additional notes about the expectations."
    )

class FEDDecisionImpact(BaseModel):
    """Output model for the FED decision analysis agent."""
    impact_on_bitcoin: Literal["positive", "negative", "neutral"] = Field(
        description="Predicted impact on Bitcoin price based on actual vs. expected FED decision."
    )
    confidence: float = Field(
        description="Confidence level for the predicted impact (0.0-1.0)."
    )
    reasoning: str = Field(
        description="Explanation for the predicted impact."
    )
    actual_fed_decision_summary: str = Field(
        description="A summary of the actual FED decision identified in the content."
    )
    # Optional: Actual parsed details for debugging/logging
    actual_interest_rate_change_type: Optional[Literal["increase", "decrease", "hold"]] = None
    actual_interest_rate_change_amount: Optional[str] = None
    actual_narrative: Optional[Literal["hawkish", "dovish", "neutral", "mixed"]] = None
    fed_chair_event: Optional[str] = Field(
        default=None,
        description="Summary if the text indicates the Federal Reserve Chair was fired, resigned or replaced."
    )

class FailedFEDAnalysis(BaseModel):
    """Indicates that the FED decision analysis failed."""
    error_message: str

class IrrelevantFEDContent(BaseModel):
    """
    Indicates that the provided content was analyzed but is not relevant
    to a FED interest rate decision, so no action can be taken.
    This is a successful analysis outcome, not a failure.
    """
    reason: str = Field(
        description="Explanation why the content is not relevant to a FED decision."
    )