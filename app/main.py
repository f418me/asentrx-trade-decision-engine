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
from app.models import WebMonitorPayload, FailedFEDAnalysis, IrrelevantFEDContent, FEDDecisionImpact
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

    # Ein Set für alles, was in dieser Sitzung verarbeitet wird.
    app.state.processed_urls: Set[str] = set()
    logger.info("Initialized in-memory store for tracking processed URLs this session.")

    try:
        bitfinex_trader = BitfinexTrader()
        if bitfinex_trader.bfx_client:
            app.state.trading_client = Trader(bfx_trader=bitfinex_trader)
            logger.info("Bitfinex Trader client initialized successfully.")
        else:
            logger.warning("Bitfinex client could not be initialized (missing API keys?). Trading will be skipped.")
            app.state.trading_client = None
    except Exception as e:
        logger.critical(f"Fatal error initializing BitfinexTrader or Trader: {e}", exc_info=True)
        app.state.trading_client = None

    if app.state.trading_client:
        app.state.trade_decision_manager = TradeDecisionManager(
            trader=app.state.trading_client,
            sms_notifier=app.state.sms_notifier
        )
        logger.info("TradeDecisionManager initialized.")
    else:
        logger.warning("Trader client not available. TradeDecisionManager will not be functional.")
        app.state.trade_decision_manager = None

    try:
        app.state.fed_decision_analyzer = FEDDecisionAnalyzer(expectations_path=EXPECTATIONS_FILE_PATH)
        logger.info(f"FEDDecisionAnalyzer initialized using expectations from: {EXPECTATIONS_FILE_PATH}")
    except Exception as e:
        logger.critical(f"Fatal error initializing FEDDecisionAnalyzer: {e}", exc_info=True)
        app.state.fed_decision_analyzer = None

    yield
    logger.info(f"aSentrX Trade Decision Engine ({APP_LOGGER_NAME}) has shut down.")


app = FastAPI(
    title="aSentrX Trade Decision Engine",
    description="Receives external notifications, analyzes content with AI, and executes trades.",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/", tags=["Health Check"])
async def read_root():
    return {"message": "aSentrX Trade Decision Engine is running!"}


@app.post("/notify/web-monitor", tags=["Notifications"])
async def handle_web_monitor_notification(request: Request, payload: WebMonitorPayload):
    logger.info(f"Received web-monitor notification (UUID: {payload.uuid}, URL: {payload.url}).")

    processed_urls: Set[str] = request.app.state.processed_urls
    url_to_process = payload.url

    # Prüfe, ob die URL bereits in unserem Set ist.
    if url_to_process in processed_urls:
        logger.warning(
            f"Skipping request for URL that is already processed or being processed in this session: {url_to_process}"
        )
        raise HTTPException(
            status_code=409,
            detail=f"URL '{url_to_process}' is already being processed or has been processed in this session."
        )

    # Füge die URL SOFORT zum Set hinzu.
    processed_urls.add(url_to_process)
    logger.debug(f"Added URL to processed set for this session: {url_to_process}")

    try:
        fed_decision_analyzer = request.app.state.fed_decision_analyzer
        if not fed_decision_analyzer:
            raise HTTPException(status_code=503, detail="FED Decision Analyzer is not available.")

        logger.info(f"Handing off content from UUID {payload.uuid} to FEDDecisionAnalyzer.")
        fed_analysis_result = await fed_decision_analyzer.analyze_content(
            content=payload.content,
            content_id_for_logging=payload.content_id or payload.uuid
        )

        if isinstance(fed_analysis_result, FailedFEDAnalysis):
            logger.error(f"FED decision analysis failed for UUID {payload.uuid}: {fed_analysis_result.error_message}")
            return {"status": "success_analysis_failed", "message": f"URL processed; analysis failed: {fed_analysis_result.error_message}"}

        if isinstance(fed_analysis_result, IrrelevantFEDContent):
            logger.info(f"Content from UUID {payload.uuid} analyzed as irrelevant. Reason: {fed_analysis_result.reason}")
            return {"status": "success_no_action", "message": "URL processed; content analyzed as irrelevant."}

        trade_decision_manager = request.app.state.trade_decision_manager
        if not trade_decision_manager:
            logger.error("Trade Decision Manager not available for actionable event.")
            return {"status": "success_trade_manager_unavailable", "message": "URL processed; actionable event found, but Trade Manager is unavailable."}

        logger.info(f"Handing off actionable analysis result for UUID {payload.uuid} to TradeDecisionManager.")
        trade_decision_manager.execute_trade_from_analysis(
            analysis_result=fed_analysis_result,
            content_id_for_log=payload.content_id or payload.uuid
        )
        return {"status": "success", "message": "Notification processed and trade logic triggered."}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f"Critical unhandled error during processing for UUID {payload.uuid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- HIER IST DER FEHLENDE TEIL ---
if __name__ == "__main__":
    # Füge das Projektverzeichnis zum sys.path hinzu, um sicherzustellen,
    # dass 'app' als Modul gefunden wird, wenn man die Datei direkt ausführt.
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    logger.info("Starting server directly from main.py")
    # Der `reload=True` Parameter ist nützlich für die Entwicklung.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)