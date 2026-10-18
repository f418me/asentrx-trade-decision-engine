import pytest

from app.ai.jev_policy import decide, baseline_change
from app.ai.jev_schemas import FEDJudgments, CPIJudgments, NFPJudgments, SocialJudgments
from app.models import FEDExpectation, AnalysisAbstention

pytestmark = pytest.mark.unit


@pytest.fixture
def baseline():
    return FEDExpectation(
        expected_interest_rate_change_type="increase",
        expected_interest_rate_change_amount="+25bp",
        expected_narrative="hawkish",
    )


def confidence(answers, **overrides):
    return {
        "confidence": {**dict.fromkeys(type(answers).model_fields, 0.99), **overrides}
    }


@pytest.mark.parametrize(
    "change,guidance,expected",
    [
        (25, "in_line", "neutral"),
        (0, "more_dovish", "positive"),
        (50, "more_hawkish", "negative"),
        (25, "more_dovish", "positive"),
        (25, "more_hawkish", "negative"),
        (25, "mixed", "neutral"),
        (-25, "more_hawkish", "positive"),
        (50, "unknown", "negative"),
    ],
)
def test_fed_direction(baseline, change, guidance, expected):
    answers = FEDJudgments(
        is_fresh_release=True,
        actual_change_bp=change,
        actual_narrative="mixed",
        guidance_vs_baseline=guidance,
    )
    result = decide("fed", answers, baseline, confidence(answers), 0.85)
    assert result.impact_on_bitcoin == expected
    assert result.confidence == 0.99


@pytest.mark.parametrize(
    "invalid", [None, True, "0.99", -0.1, 1.1, float("nan"), float("inf"), 0.84]
)
def test_invalid_required_confidence_abstains(baseline, invalid):
    answers = FEDJudgments(
        is_fresh_release=True,
        actual_change_bp=0,
        actual_narrative="dovish",
        guidance_vs_baseline="in_line",
    )
    assert isinstance(
        decide(
            "fed",
            answers,
            baseline,
            confidence(answers, actual_change_bp=invalid),
            0.85,
        ),
        AnalysisAbstention,
    )


@pytest.mark.parametrize(
    "details", [None, {}, {"confidence": None}, {"confidence": []}]
)
def test_missing_provider_confidence_abstains(baseline, details):
    answers = FEDJudgments(
        is_fresh_release=True,
        actual_change_bp=0,
        actual_narrative="dovish",
        guidance_vs_baseline="in_line",
    )
    assert isinstance(
        decide("fed", answers, baseline, details, 0.85), AnalysisAbstention
    )


def test_rate_surprise_does_not_require_guidance_confidence(baseline):
    answers = FEDJudgments(
        is_fresh_release=True,
        actual_change_bp=0,
        actual_narrative="mixed",
        guidance_vs_baseline="unknown",
    )
    details = {"confidence": {"is_fresh_release": 0.99, "actual_change_bp": 0.85}}
    assert decide("fed", answers, baseline, details, 0.85).confidence == 0.85
    answers.actual_change_bp = 25
    assert isinstance(
        decide("fed", answers, baseline, details, 0.85), AnalysisAbstention
    )


@pytest.mark.parametrize(
    "fresh,change,guidance",
    [(False, 25, "in_line"), (True, None, "in_line"), (True, 25, "unknown")],
)
def test_preview_unknown_rate_or_guidance_abstains(baseline, fresh, change, guidance):
    answers = FEDJudgments(
        is_fresh_release=fresh,
        actual_change_bp=change,
        actual_narrative="neutral",
        guidance_vs_baseline=guidance,
    )
    assert isinstance(
        decide("fed", answers, baseline, confidence(answers), 0.85), AnalysisAbstention
    )


@pytest.mark.parametrize(
    "amount,direction",
    [
        (None, "increase"),
        ("25", "increase"),
        ("-25bp", "increase"),
        ("0bp", "uncertain"),
    ],
)
def test_invalid_baseline_rejected(baseline, amount, direction):
    baseline.expected_interest_rate_change_amount = amount
    baseline.expected_interest_rate_change_type = direction
    with pytest.raises(ValueError):
        baseline_change(baseline)


@pytest.mark.parametrize(
    "headline,core,expected",
    [
        ("below", "below", "positive"),
        ("above", "above", "negative"),
        ("in_line", "below", "positive"),
        ("above", "below", "neutral"),
        ("below", "in_line", "neutral"),
        ("in_line", "in_line", "neutral"),
    ],
)
def test_cpi_requires_core_surprise_without_conflict(headline, core, expected):
    answers = CPIJudgments(
        is_fresh_release=True,
        headline_mom=headline,
        headline_yoy=headline,
        core_mom=core,
        core_yoy=core,
    )
    result = decide("cpi", answers, None, confidence(answers), 0.85)
    assert result.impact_on_bitcoin == expected
    assert result.actual_core_cpi_mom is None


@pytest.mark.parametrize(
    "payrolls,unemployment,wages,scare,expected",
    [
        ("below", "above", "below", "no", "positive"),
        ("above", "below", "above", "no", "negative"),
        ("below", "above", "below", "yes", "neutral"),
        ("below", "below", "below", "no", "neutral"),
        ("above", "in_line", "below", "no", "neutral"),
    ],
)
def test_nfp_consensus_and_growth_scare(payrolls, unemployment, wages, scare, expected):
    answers = NFPJudgments(
        is_fresh_release=True,
        payrolls=payrolls,
        unemployment=unemployment,
        wages_mom=wages,
        growth_scare=scare,
    )
    assert (
        decide("nfp", answers, None, confidence(answers), 0.85).impact_on_bitcoin
        == expected
    )


@pytest.fixture
def social():
    return SocialJudgments(
        event_type="crypto_policy_positive",
        asset="btc",
        concrete_new_action=True,
        transmission="risk_on",
        time_sensitivity="immediate",
        risk_level="medium",
    )


def test_social_direction_and_confidence(social):
    result = decide("social", social, None, confidence(social, transmission=0.94), 0.85)
    assert result.is_tradeable and result.direction == "up"
    assert result.confidence == 0.94
    assert result.novelty_score == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("concrete_new_action", False),
        ("time_sensitivity", "slow"),
        ("event_type", "company_specific"),
        ("asset", "none"),
        ("transmission", "mixed"),
        ("transmission", "risk_off"),
    ],
)
def test_social_vetoes(social, field, value):
    setattr(social, field, value)
    result = decide("social", social, None, confidence(social), 0.85)
    assert not result.is_tradeable
    assert result.direction == "neutral" and result.trade_veto_reason


def test_social_missing_novelty_confidence_abstains(social):
    assert isinstance(
        decide(
            "social", social, None, confidence(social, concrete_new_action=None), 0.85
        ),
        AnalysisAbstention,
    )
