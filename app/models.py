
from typing import Optional, Literal, Union
from pydantic import BaseModel, Field
import uuid


# --- Incoming Payload Models ---
class WebMonitorPayload(BaseModel):
    """
    Pydantic model for data from the web monitor client (e.g., macro announcements).
    """
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["web-monitor"] = "web-monitor"
    url: str
    content_id: Optional[str] = Field(default=None, alias="content-id")
    content: str
    ip: str


class SocialMediaPayload(BaseModel):
    """
    Pydantic model for data from social media clients (e.g., Truth Social).
    """
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["truthsocial"] = "truthsocial"
    url: str
    username: Optional[str] = None
    content_id: str = Field(alias="content-id")
    content: str
    ip: str




# --- Social Media Analysis Models ---
class SocialMediaMarketSignal(BaseModel):
    """
    Represents a strict short-term market signal derived from a social media post.
    """
    is_tradeable: bool
    event_type: Literal[
        "tariff_escalation",
        "tariff_deescalation",
        "china_trade_conflict",
        "fed_pressure",
        "fiscal_policy",
        "crypto_policy_positive",
        "crypto_policy_negative",
        "geopolitical_risk",
        "company_specific",
        "non_tradeable",
    ]
    asset: Literal["btc", "broad_market", "usd", "none"]
    direction: Literal["up", "down", "neutral"]
    confidence: float
    novelty_score: float
    time_sensitivity: Literal["immediate", "same_day", "slow", "none"]
    risk_level: Literal["low", "medium", "high"]
    reasoning: str
    trade_veto_reason: Optional[str] = None

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





# --- NFP / Employment Situation Analysis Models ---
class NFPExpectation(BaseModel):
    """Model for expected U.S. labor-market data, loaded from a file."""
    expected_nonfarm_payrolls_k: int
    expected_unemployment_rate: float
    expected_average_hourly_earnings_mom: float
    expected_average_hourly_earnings_yoy: Optional[float] = None
    expected_participation_rate: Optional[float] = None
    expected_average_weekly_hours: Optional[float] = None
    notes: Optional[str] = None

class NFPReportImpact(BaseModel):
    """Output model for the Employment Situation / NFP analysis agent."""
    impact_on_bitcoin: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str
    actual_report_summary: str
    actual_nonfarm_payrolls_k: Optional[int] = None
    actual_unemployment_rate: Optional[float] = None
    actual_average_hourly_earnings_mom: Optional[float] = None
    actual_average_hourly_earnings_yoy: Optional[float] = None
    actual_participation_rate: Optional[float] = None
    actual_average_weekly_hours: Optional[float] = None

class FailedNFPAnalysis(BaseModel):
    """Indicates that the Employment Situation / NFP analysis failed."""
    error_message: str

class IrrelevantNFPContent(BaseModel):
    """
    Indicates that the provided content is not relevant to a newly released U.S. jobs report.
    """
    reason: str


# --- CPI / Consumer Price Index Analysis Models ---
class CPIExpectation(BaseModel):
    """Model for expected U.S. CPI data, loaded from a file."""
    expected_headline_cpi_mom: float
    expected_headline_cpi_yoy: float
    expected_core_cpi_mom: float
    expected_core_cpi_yoy: float
    notes: Optional[str] = None

class CPIReportImpact(BaseModel):
    """Output model for the Consumer Price Index analysis agent."""
    impact_on_bitcoin: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str
    actual_report_summary: str
    actual_headline_cpi_mom: Optional[float] = None
    actual_headline_cpi_yoy: Optional[float] = None
    actual_core_cpi_mom: Optional[float] = None
    actual_core_cpi_yoy: Optional[float] = None

class FailedCPIAnalysis(BaseModel):
    """Indicates that the CPI analysis failed."""
    error_message: str

class IrrelevantCPIContent(BaseModel):
    """
    Indicates that the provided content is not relevant to a newly released U.S. CPI report.
    """
    reason: str


# --- Union Types for Analysis Results ---
class AnalysisAbstention(BaseModel):
    """An analysis that cannot safely produce a trading signal."""
    source: Literal["fed", "cpi", "nfp", "social"]
    reason: str

FEDAnalysisResult = Union[FEDDecisionImpact, FailedFEDAnalysis, IrrelevantFEDContent]
NFPAnalysisResult = Union[NFPReportImpact, FailedNFPAnalysis, IrrelevantNFPContent]
CPIAnalysisResult = Union[CPIReportImpact, FailedCPIAnalysis, IrrelevantCPIContent]
SocialMediaAnalysisResult = Union[SocialMediaMarketSignal, FailedSocialMediaAnalysis, IrrelevantSocialMediaContent]

# A general type for any possible analysis outcome
AnyAnalysisResult = Union[FEDAnalysisResult, NFPAnalysisResult, CPIAnalysisResult, SocialMediaAnalysisResult, AnalysisAbstention]
