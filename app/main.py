# --- START OF FILE main.py ---

import logging
import uvicorn
# Fügen Sie os und sys am Anfang hinzu, um sie globaler zu nutzen
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request

# --- ÄNDERUNG 1: Pfade oben definieren ---
# Definieren Sie den Projekt-Stammordner und wichtige Dateipfade hier.
# Dies macht sie im gesamten Skript verfügbar und robust gegenüber dem CWD.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTATIONS_FILE_PATH = os.path.join(PROJECT_ROOT, "app", "expectations.json")


from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.models import WebMonitorPayload, FailedFEDAnalysis
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
        # --- ÄNDERUNG 2: Den neuen, absoluten Pfad verwenden ---
        app.state.fed_decision_analyzer = FEDDecisionAnalyzer(expectations_path=EXPECTATIONS_FILE_PATH)
        logger.info(f"FEDDecisionAnalyzer initialized using expectations from: {EXPECTATIONS_FILE_PATH}")
    except Exception as e:
        # Die Fehlermeldung wird jetzt den vollen, korrekten Pfad anzeigen, was das Debugging erleichtert.
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


# ... (der Rest Ihres Codes für die Endpunkte bleibt unverändert) ...
@app.get("/", tags=["Health Check"])
async def read_root():
    return {"message": "aSentrX Trade Decision Engine is running!"}


@app.post("/notify/web-monitor", tags=["Notifications"])
async def handle_web_monitor_notification(request: Request, payload: WebMonitorPayload):
    logger.info(f"Received web-monitor notification (UUID: {payload.uuid}, URL: {payload.url}).")

    if payload.type != "web-monitor":
        logger.warning(f"Unsupported payload type '{payload.type}' received. Skipping.")
        return {"status": "skipped", "message": f"Unsupported payload type: {payload.type}"}

    fed_decision_analyzer = request.app.state.fed_decision_analyzer
    trade_decision_manager = request.app.state.trade_decision_manager

    if not fed_decision_analyzer:
        error_msg = "FED Decision Analyzer is not available. Cannot process notification."
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)

    if not trade_decision_manager:
        error_msg = "Trade Decision Manager is not available. Cannot process for trading."
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)

    logger.info(f"Handing off content from UUID {payload.uuid} to FEDDecisionAnalyzer.")

    fed_analysis_result = await fed_decision_analyzer.analyze_content(
        content=payload.content,
        content_id_for_logging=payload.content_id or payload.uuid
    )

    if isinstance(fed_analysis_result, FailedFEDAnalysis):
        logger.error(f"FED decision analysis failed for UUID {payload.uuid}: {fed_analysis_result.error_message}")
        raise HTTPException(status_code=500, detail=f"FED analysis failed: {fed_analysis_result.error_message}")

    logger.info(f"Handing off analysis result for UUID {payload.uuid} to TradeDecisionManager.")
    try:
        trade_decision_manager.execute_trade_from_analysis(
            analysis_result=fed_analysis_result,
            content_id_for_log=payload.content_id or payload.uuid
        )
        return {"status": "success", "message": "Notification processed and trade logic triggered."}
    except Exception as e:
        logger.critical(f"Unhandled error during trade execution for UUID {payload.uuid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error during trade processing: {str(e)}")


if __name__ == "__main__":

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    logger.info("Starting server directly from main.py")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)