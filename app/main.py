import logging
import uvicorn
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from typing import Set

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTATIONS_FILE_PATH = os.path.join(PROJECT_ROOT, "app", "expectations.json")

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.ai.agents.social_media_agent import SocialMediaPostAnalyzer
from app.models import (
    WebMonitorPayload,
    FailedFEDAnalysis, IrrelevantFEDContent, FEDDecisionImpact,
    FailedSocialMediaAnalysis, IrrelevantSocialMediaContent, SocialMediaAnalysisOutput,
    AnyAnalysisResult
)
from app.utils.logger_config import configure_logging, APP_LOGGER_NAME
from app.utils.sms_notifier import SmsNotifier
from app.trading.bitfinex_trader import BitfinexTrader
from app.trading.trader import Trader
from app.trading.trade_decision_manager import TradeDecisionManager

try:
    configure_logging()
except ValueError as e:
    print(f"CRITICAL: Failed to configure logging: {e}. Exiting.")
    exit(1)

logger = logging.getLogger(f"{APP_LOGGER_NAME}.main_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"aSentrX Trade Decision Engine ({APP_LOGGER_NAME}) is starting up...")
    app.state.sms_notifier = SmsNotifier()
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

    # Initialize AI Agents
    try:
        app.state.fed_decision_analyzer = FEDDecisionAnalyzer(expectations_path=EXPECTATIONS_FILE_PATH)
        logger.info(f"FEDDecisionAnalyzer initialized.")
    except Exception as e:
        logger.critical(f"Fatal error initializing FEDDecisionAnalyzer: {e}", exc_info=True)
        app.state.fed_decision_analyzer = None

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
            sms_notifier=app.state.sms_notifier
        )
        logger.info("TradeDecisionManager initialized.")
    else:
        app.state.trade_decision_manager = None
        logger.warning("Trader client not available. TradeDecisionManager will not be functional.")

    yield
    logger.info(f"aSentrX Trade Decision Engine ({APP_LOGGER_NAME}) has shut down.")


app = FastAPI(
    title="aSentrX Trade Decision Engine",
    description="Receives external notifications, analyzes content with AI, and executes trades.",
    version="1.1.0",
    lifespan=lifespan
)


@app.get("/", tags=["Health Check"])
async def read_root():
    return {"message": "aSentrX Trade Decision Engine is running!"}


@app.post("/notify", tags=["Notifications"])
async def handle_notification(request: Request, payload: WebMonitorPayload):
    logger.info(f"Received notification (Type: {payload.type}, UUID: {payload.uuid}).")

    # --- 1. Deduplication ---
    processed_ids: Set[str] = request.app.state.processed_content_ids
    id_to_process = payload.url if payload.type == "web-monitor" else payload.content_id
    
    if not id_to_process:
        raise HTTPException(status_code=400, detail=f"Missing 'url' for web-monitor or 'content-id' for {payload.type}.")

    if id_to_process in processed_ids:
        logger.warning(f"Skipping already processed ID: {id_to_process}")
        raise HTTPException(status_code=409, detail=f"ID '{id_to_process}' already processed.")
    
    processed_ids.add(id_to_process)
    logger.debug(f"Added ID to processed set: {id_to_process}")

    # --- 2. Routing to correct AI Analyzer ---
    analysis_result: AnyAnalysisResult = None
    content_id_for_log = payload.content_id or payload.uuid

    try:
        if payload.type == "web-monitor":
            analyzer = request.app.state.fed_decision_analyzer
            if not analyzer:
                raise HTTPException(status_code=503, detail="FED Decision Analyzer is not available.")
            logger.info(f"Routing UUID {payload.uuid} to FEDDecisionAnalyzer.")
            analysis_result = await analyzer.analyze_content(payload.content, content_id_for_log)

        elif payload.type == "truthsocial":
            analyzer = request.app.state.social_media_analyzer
            if not analyzer:
                raise HTTPException(status_code=503, detail="Social Media Analyzer is not available.")
            logger.info(f"Routing UUID {payload.uuid} to SocialMediaPostAnalyzer.")
            analysis_result = await analyzer.analyze_content(payload.content, content_id_for_log)
            
        else:
            logger.warning(f"Received notification for unhandled type: {payload.type}")
            raise HTTPException(status_code=400, detail=f"Unhandled notification type: {payload.type}")

        # --- 3. Handling Analysis Results ---
        if isinstance(analysis_result, (FailedFEDAnalysis, FailedSocialMediaAnalysis)):
            logger.error(f"Analysis failed for UUID {payload.uuid}: {analysis_result.error_message}")
            return {"status": "success_analysis_failed", "message": f"Analysis failed: {analysis_result.error_message}"}

        if isinstance(analysis_result, (IrrelevantFEDContent, IrrelevantSocialMediaContent)):
            logger.info(f"Content from UUID {payload.uuid} analyzed as irrelevant. Reason: {analysis_result.reason}")
            return {"status": "success_no_action", "message": "Content analyzed as irrelevant."}

        # --- 4. Triggering Trade Logic for Actionable Events ---
        trade_decision_manager = request.app.state.trade_decision_manager
        if not trade_decision_manager:
            logger.error("Trade Decision Manager not available for actionable event.")
            return {"status": "success_trade_manager_unavailable", "message": "Actionable event found, but Trade Manager is unavailable."}

        logger.info(f"Handing off actionable analysis result for UUID {payload.uuid} to TradeDecisionManager.")
        trade_decision_manager.execute_trade_from_analysis(analysis_result, content_id_for_log)
        
        return {"status": "success", "message": "Notification processed and trade logic triggered."}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f"Critical unhandled error for UUID {payload.uuid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    logger.info("Starting server directly from main.py")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)