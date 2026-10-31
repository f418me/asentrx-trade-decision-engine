import logging
import uvicorn
import os
import sys
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request
from typing import Set

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTATIONS_FILE_PATH = os.path.join(PROJECT_ROOT, "app", "expectations.json")
NFP_EXPECTATIONS_FILE_PATH = os.path.join(PROJECT_ROOT, "app", "nfp_expectations.json")
CPI_EXPECTATIONS_FILE_PATH = os.path.join(PROJECT_ROOT, "app", "cpi_expectations.json")

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.ai.agents.nfp_decision_agent import NFPDecisionAnalyzer
from app.ai.agents.cpi_decision_agent import CPIDecisionAnalyzer
from app.ai.agents.social_media_agent import SocialMediaPostAnalyzer
from app.models import (
    WebMonitorPayload, SocialMediaPayload,
    FailedFEDAnalysis, IrrelevantFEDContent, FEDDecisionImpact,
    FailedNFPAnalysis, IrrelevantNFPContent, NFPReportImpact,
    FailedCPIAnalysis, IrrelevantCPIContent, CPIReportImpact,
    FailedSocialMediaAnalysis, IrrelevantSocialMediaContent,
    AnyAnalysisResult, AnalysisAbstention
)
from app.utils.logger_config import configure_logging, APP_LOGGER_NAME
from app.utils.observability import logfire_error, logfire_info, logfire_warning, trade_outcome
from app.config import AppConfig
from app.security import require_notify_auth
from app.utils.slack_notifier import SlackNotifier
from app.trading.bitfinex_trader import BitfinexTrader
from app.trading.trader import Trader
from app.trading.trade_decision_manager import TradeDecisionManager

try:
    configure_logging()
except ValueError as e:
    print(f"CRITICAL: Failed to configure logging: {e}. Exiting.")
    exit(1)


logger = logging.getLogger(f"{APP_LOGGER_NAME}.main_app")


def _get_web_monitor_dedup_key(payload: WebMonitorPayload) -> str:
    return payload.content_id or payload.url


def _detect_web_monitor_source(payload: WebMonitorPayload) -> str:
    url_lower = payload.url.lower()
    content_id_lower = (payload.content_id or "").lower()
    content_lower = payload.content.lower()

    if (
        "/cpi" in url_lower
        or content_id_lower.startswith("bls-cpi-")
        or "consumer price index" in content_lower
        or "cpi for all urban consumers" in content_lower
        or "cpi-u" in content_lower
    ):
        return "cpi"

    if (
        "empsit" in url_lower
        or content_id_lower.startswith("bls-empsit-")
        or "employment situation" in content_lower
        or "nonfarm payroll" in content_lower
    ):
        return "nfp"

    return "fed"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"aSentrX Trade Decision Engine ({APP_LOGGER_NAME}) is starting up...")
    app.state.slack_notifier = SlackNotifier()
    app.state.processed_content_ids: Set[str] = set()
    logger.info("Initialized in-memory store for tracking processed content IDs.")

    # Initialize Bitfinex Trader
    try:
        bitfinex_trader = BitfinexTrader()
        app.state.trading_client = Trader(bfx_trader=bitfinex_trader) if bitfinex_trader.bfx_client else None
        if app.state.trading_client:
            logger.info("Bitfinex Trader client initialized successfully.")
        else:
            logger.warning("Bitfinex client could not be initialized. Trading will be skipped.")
    except Exception as e:
        logger.critical(f"Fatal error initializing BitfinexTrader: {e}", exc_info=True)
        app.state.trading_client = None

    # Initialize the source-specific Jev analyzers.
    try:
        app.state.fed_decision_analyzer = FEDDecisionAnalyzer(expectations_path=EXPECTATIONS_FILE_PATH)
        logger.info(f"FEDDecisionAnalyzer initialized.")
    except Exception as e:
        logger.critical(f"Fatal error initializing FEDDecisionAnalyzer: {e}", exc_info=True)
        app.state.fed_decision_analyzer = None

    try:
        app.state.nfp_decision_analyzer = NFPDecisionAnalyzer(expectations_path=NFP_EXPECTATIONS_FILE_PATH)
        logger.info("NFPDecisionAnalyzer initialized.")
    except Exception as e:
        logger.critical(f"Fatal error initializing NFPDecisionAnalyzer: {e}", exc_info=True)
        app.state.nfp_decision_analyzer = None

    try:
        app.state.cpi_decision_analyzer = CPIDecisionAnalyzer(expectations_path=CPI_EXPECTATIONS_FILE_PATH)
        logger.info("CPIDecisionAnalyzer initialized.")
    except Exception as e:
        logger.critical(f"Fatal error initializing CPIDecisionAnalyzer: {e}", exc_info=True)
        app.state.cpi_decision_analyzer = None

    try:
        app.state.social_media_analyzer = SocialMediaPostAnalyzer()
        logger.info("SocialMediaPostAnalyzer initialized.")
    except Exception as e:
        logger.critical(f"Fatal error initializing SocialMediaPostAnalyzer: {e}", exc_info=True)
        app.state.social_media_analyzer = None

    # Initialize Trade Decision Manager
    if app.state.trading_client:
        app.state.trade_decision_manager = TradeDecisionManager(
            trader=app.state.trading_client,
            slack_notifier=app.state.slack_notifier
        )
        logger.info("TradeDecisionManager initialized.")
    else:
        app.state.trade_decision_manager = None
        logger.warning("Trader client not available. TradeDecisionManager will not be functional.")

    try:
        yield
    finally:
        for name in ("fed_decision_analyzer", "nfp_decision_analyzer", "cpi_decision_analyzer", "social_media_analyzer"):
            analyzer = getattr(app.state, name, None)
            if analyzer is not None:
                await analyzer.aclose()
        logger.info(f"aSentrX Trade Decision Engine ({APP_LOGGER_NAME}) has shut down.")


app = FastAPI(
    title="aSentrX Trade Decision Engine",
    description="Receives notifications, classifies content with Jev, and applies Python policies before trade execution.",
    version="1.1.0",
    lifespan=lifespan
)


@app.get("/", tags=["Health Check"])
async def read_root():
    return {"message": "aSentrX Trade Decision Engine is running!"}


@app.post("/notify/web-monitor", tags=["Notifications"], dependencies=[Depends(require_notify_auth)])
async def handle_web_monitor_notification(request: Request, payload: WebMonitorPayload):
    """
    Handles notifications from the web monitor client (e.g., FED announcements).
    """
    logger.info(f"Received web-monitor notification (UUID: {payload.uuid}).")
    logfire_info(
        "notification_received",
        source="web-monitor",
        uuid=payload.uuid,
        content_id=payload.content_id,
        url=payload.url,
    )

    # --- 1. Deduplication ---
    processed_ids: Set[str] = request.app.state.processed_content_ids
    dedup_key = _get_web_monitor_dedup_key(payload)
    if dedup_key in processed_ids:
        trade_outcome(content_id=dedup_key, uuid=payload.uuid, outcome="no_trade",
                      reason_code="duplicate", reason="Content already received; not reprocessed.",
                      source="web-monitor", order_attempted=False)
        logger.warning(f"Skipping already processed web-monitor key: {dedup_key}")
        logfire_warning(
            "notification_duplicate",
            source="web-monitor",
            uuid=payload.uuid,
            content_id=payload.content_id,
            url=payload.url,
        )
        raise HTTPException(status_code=409, detail=f"Content key '{dedup_key}' already processed.")

    processed_ids.add(dedup_key)
    logger.debug(f"Added web-monitor key to processed set: {dedup_key}")

    # --- 2. Routing to the appropriate macro analyzer ---
    source_kind = _detect_web_monitor_source(payload)
    if source_kind == "nfp":
        analyzer = request.app.state.nfp_decision_analyzer
        analyzer_name = "NFPDecisionAnalyzer"
        unavailable_detail = "NFP Decision Analyzer is not available."
    elif source_kind == "cpi":
        analyzer = request.app.state.cpi_decision_analyzer
        analyzer_name = "CPIDecisionAnalyzer"
        unavailable_detail = "CPI Decision Analyzer is not available."
    else:
        analyzer = request.app.state.fed_decision_analyzer
        analyzer_name = "FEDDecisionAnalyzer"
        unavailable_detail = "FED Decision Analyzer is not available."

    if not analyzer:
        trade_outcome(content_id=dedup_key, uuid=payload.uuid, outcome="no_trade",
                      reason_code="analyzer_unavailable", reason=unavailable_detail,
                      source=source_kind, order_attempted=False)
        raise HTTPException(status_code=503, detail=unavailable_detail)

    logger.info(f"Routing UUID {payload.uuid} to {analyzer_name}.")
    analysis_result = await analyzer.analyze_content(payload.content, payload.content_id or payload.uuid)

    # --- 3. Process analysis result ---
    return await _process_analysis_result(request, analysis_result, payload.uuid, payload.content_id or payload.url)


@app.post("/notify/truth-social", tags=["Notifications"], dependencies=[Depends(require_notify_auth)])
async def handle_truth_social_notification(request: Request, payload: SocialMediaPayload):
    """
    Handles notifications from the Truth Social client.
    """
    logger.info(f"Received truth-social notification (UUID: {payload.uuid}).")
    logfire_info(
        "notification_received",
        source="truthsocial",
        uuid=payload.uuid,
        content_id=payload.content_id,
        url=payload.url,
        username=payload.username,
    )

    # --- 1. Deduplication ---
    processed_ids: Set[str] = request.app.state.processed_content_ids
    if payload.content_id in processed_ids:
        trade_outcome(content_id=payload.content_id, uuid=payload.uuid, outcome="no_trade",
                      reason_code="duplicate", reason="Content already received; not reprocessed.",
                      source="truthsocial", order_attempted=False)
        logger.warning(f"Skipping already processed content_id: {payload.content_id}")
        logfire_warning(
            "notification_duplicate",
            source="truthsocial",
            uuid=payload.uuid,
            content_id=payload.content_id,
            url=payload.url,
            username=payload.username,
        )
        raise HTTPException(status_code=409, detail=f"Content ID '{payload.content_id}' already processed.")

    processed_ids.add(payload.content_id)
    logger.debug(f"Added content_id to processed set: {payload.content_id}")

    # --- 2. Routing to Social Media Analyzer ---
    analyzer = request.app.state.social_media_analyzer
    if not analyzer:
        trade_outcome(content_id=payload.content_id, uuid=payload.uuid, outcome="no_trade",
                      reason_code="analyzer_unavailable", reason="Social Media Analyzer is unavailable.",
                      source="truthsocial", order_attempted=False)
        raise HTTPException(status_code=503, detail="Social Media Analyzer is not available.")

    logger.info(f"Routing UUID {payload.uuid} to SocialMediaPostAnalyzer.")
    analysis_result = await analyzer.analyze_content(payload.content, payload.content_id)

    # --- 3. Process analysis result ---
    return await _process_analysis_result(request, analysis_result, payload.uuid, payload.content_id)


async def _process_analysis_result(request: Request, analysis_result: AnyAnalysisResult, uuid: str, content_id: str | None = None):
    """
    Shared logic to handle the result from any Jev analyzer and its local policy.
    """
    content_id = content_id or uuid
    def no_trade(code, reason):
        trade_outcome(content_id=content_id, uuid=uuid, outcome="no_trade",
                      reason_code=code, reason=reason,
                      result_type=type(analysis_result).__name__,
                      source=getattr(analysis_result, "source", None),
                      jev_confidence_threshold=AppConfig.JEV_CONFIDENCE_THRESHOLD,
                      confidence_by_field=getattr(analysis_result, "confidence_by_field", {}),
                      order_attempted=False)

    if isinstance(analysis_result, AnalysisAbstention):
        no_trade("analysis_abstained", analysis_result.reason)
        logfire_info("analysis_abstained", uuid=uuid, **analysis_result.model_dump())
        logger.info("Analysis abstained for %s: %s", uuid, analysis_result.reason)
        return {"status": "success_no_action", "message": analysis_result.reason}

    if isinstance(analysis_result, (FailedFEDAnalysis, FailedNFPAnalysis, FailedCPIAnalysis, FailedSocialMediaAnalysis)):
        no_trade("analysis_failed", analysis_result.error_message)
        logger.error(f"Analysis failed for UUID {uuid}: {analysis_result.error_message}")
        logfire_error(
            "analysis_failed",
            uuid=uuid,
            result_type=type(analysis_result).__name__,
            error_message=analysis_result.error_message,
        )
        # Still return 200 OK as the notification was successfully received and processed.
        return {"status": "success_analysis_failed", "message": f"Analysis failed: {analysis_result.error_message}"}

    if isinstance(analysis_result, (IrrelevantFEDContent, IrrelevantNFPContent, IrrelevantCPIContent, IrrelevantSocialMediaContent)):
        no_trade("irrelevant_content", analysis_result.reason)
        logger.info(f"Content from UUID {uuid} analyzed as irrelevant. Reason: {analysis_result.reason}")
        logfire_info(
            "analysis_irrelevant",
            uuid=uuid,
            result_type=type(analysis_result).__name__,
            reason=analysis_result.reason,
        )
        return {"status": "success_no_action", "message": "Content analyzed as irrelevant."}

    # --- Triggering Trade Logic for Actionable Events ---
    trade_decision_manager = request.app.state.trade_decision_manager
    if not trade_decision_manager:
        no_trade("trade_manager_unavailable", "Trading client or decision manager is unavailable.")
        logger.error(f"Trade Decision Manager not available for actionable event from UUID {uuid}.")
        logfire_error(
            "trade_manager_unavailable",
            uuid=uuid,
            result_type=type(analysis_result).__name__,
        )
        # Return a 200 but indicate that the trade could not be processed.
        return {"status": "success_trade_manager_unavailable",
                "message": "Actionable event found, but Trade Manager is unavailable."}

    logger.info(f"Handing off actionable analysis result for UUID {uuid} to TradeDecisionManager.")
    logfire_info(
        "analysis_actionable",
        uuid=uuid,
        result_type=type(analysis_result).__name__,
    )
    trade_decision_manager.execute_trade_from_analysis(analysis_result, content_id)

    return {"status": "success", "message": "Notification processed and trade logic triggered."}



if __name__ == "__main__":
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    logger.info("Starting server directly from main.py")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
