
import os
from dotenv import load_dotenv

load_dotenv()

class AppConfig:
    # --- General Application Settings ---
    LOG_LEVEL_CONSOLE = os.getenv("LOG_LEVEL_CONSOLE", "INFO").upper()
    PROD_EXECUTION = os.getenv("PROD_EXECUTION", "False").lower() == "true"
    SENTRY_DSN = os.getenv('SENTRY_DSN')
    LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")
    LOGFIRE_ENVIRONMENT = os.getenv("LOGFIRE_ENVIRONMENT", "local")
    MODEL = os.getenv("MODEL", "groq:llama-3.3-70b-versatile")

    # --- Twilio SMS Notifications ---
    SMS_NOTIFICATIONS_ENABLED = os.getenv("SMS_NOTIFICATIONS_ENABLED", "False").lower() == "true"
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')
    TWILIO_TO_NUMBER = os.getenv('TWILIO_TO_NUMBER')

    # --- Bitfinex API Credentials & Trading Symbol ---
    BFX_API_KEY = os.getenv("BFX_API_KEY")
    BFX_API_SECRET = os.getenv("BFX_API_SECRET")
    TRADE_SYMBOL = os.getenv("TRADE_SYMBOL", "tBTCF0:USTF0")

    # --- FED Decision Specific Order Amounts ---
    ORDER_AMOUNT_FED_BUY_HIGH_CONF = float(os.getenv("ORDER_AMOUNT_FED_BUY_HIGH_CONF", "0.002"))
    ORDER_AMOUNT_FED_SHORT_HIGH_CONF = float(os.getenv("ORDER_AMOUNT_FED_SHORT_HIGH_CONF", "-0.002"))
    ORDER_AMOUNT_FED_BUY_MED_CONF = float(os.getenv("ORDER_AMOUNT_FED_BUY_MED_CONF", "0.001"))
    ORDER_AMOUNT_FED_SHORT_MED_CONF = float(os.getenv("ORDER_AMOUNT_FED_SHORT_MED_CONF", "-0.001"))

    # --- FED Decision Specific Leverage Settings ---
    LEVERAGE_FED_BUY_HIGH_CONF = int(os.getenv("LEVERAGE_FED_BUY_HIGH_CONF", "20"))
    LEVERAGE_FED_SHORT_HIGH_CONF = int(os.getenv("LEVERAGE_FED_SHORT_HIGH_CONF", "20"))
    LEVERAGE_FED_BUY_MED_CONF = int(os.getenv("LEVERAGE_FED_BUY_MED_CONF", "10"))
    LEVERAGE_FED_SHORT_MED_CONF = int(os.getenv("LEVERAGE_FED_SHORT_MED_CONF", "10"))
    
    # --- FED Decision Specific Confidence Thresholds for Trading ---
    CONFIDENCE_THRESHOLD_FED_HIGH = float(os.getenv("CONFIDENCE_THRESHOLD_FED_HIGH", "0.96"))
    CONFIDENCE_THRESHOLD_FED_MED = float(os.getenv("CONFIDENCE_THRESHOLD_FED_MED", "0.92"))

    # --- Truth Social Generic Order Amounts ---
    TS_ORDER_AMOUNT_BUY_HIGH_CONF = float(os.getenv("TS_ORDER_AMOUNT_BUY_HIGH_CONF", "0.001"))
    TS_ORDER_AMOUNT_SHORT_HIGH_CONF = float(os.getenv("TS_ORDER_AMOUNT_SHORT_HIGH_CONF", "-0.001"))
    TS_ORDER_AMOUNT_BUY_MED_CONF = float(os.getenv("TS_ORDER_AMOUNT_BUY_MED_CONF", "0.0005"))
    TS_ORDER_AMOUNT_SHORT_MED_CONF = float(os.getenv("TS_ORDER_AMOUNT_SHORT_MED_CONF", "-0.0005"))

    # --- Truth Social Generic Leverage Settings ---
    TS_LEVERAGE_BUY_HIGH_CONF = int(os.getenv("TS_LEVERAGE_BUY_HIGH_CONF", "10"))
    TS_LEVERAGE_SHORT_HIGH_CONF = int(os.getenv("TS_LEVERAGE_SHORT_HIGH_CONF", "10"))
    TS_LEVERAGE_BUY_MED_CONF = int(os.getenv("TS_LEVERAGE_BUY_MED_CONF", "5"))
    TS_LEVERAGE_SHORT_MED_CONF = int(os.getenv("TS_LEVERAGE_SHORT_MED_CONF", "5"))

    # --- Truth Social Bitcoin Specific Order Amounts ---
    TS_ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF = float(os.getenv("TS_ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF", "0.0015"))
    TS_ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF = float(os.getenv("TS_ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF", "-0.0015"))
    TS_ORDER_AMOUNT_BITCOIN_BUY_MED_CONF = float(os.getenv("TS_ORDER_AMOUNT_BITCOIN_BUY_MED_CONF", "0.00075"))
    TS_ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF = float(os.getenv("TS_ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF", "-0.00075"))

    # --- Truth Social Bitcoin Specific Leverage Settings ---
    TS_LEVERAGE_BITCOIN_BUY_HIGH_CONF = int(os.getenv("TS_LEVERAGE_BITCOIN_BUY_HIGH_CONF", "15"))
    TS_LEVERAGE_BITCOIN_SHORT_HIGH_CONF = int(os.getenv("TS_LEVERAGE_BITCOIN_SHORT_HIGH_CONF", "15"))
    TS_LEVERAGE_BITCOIN_BUY_MED_CONF = int(os.getenv("TS_LEVERAGE_BITCOIN_BUY_MED_CONF", "7"))
    TS_LEVERAGE_BITCOIN_SHORT_MED_CONF = int(os.getenv("TS_LEVERAGE_BITCOIN_SHORT_MED_CONF", "7"))

    # --- Truth Social Generic Confidence Thresholds ---
    TS_CONFIDENCE_THRESHOLD_HIGH = float(os.getenv("TS_CONFIDENCE_THRESHOLD_HIGH", "0.95"))
    TS_CONFIDENCE_THRESHOLD_MED = float(os.getenv("TS_CONFIDENCE_THRESHOLD_MED", "0.9"))

    # --- Truth Social Bitcoin Specific Confidence Thresholds ---
    TS_CONFIDENCE_THRESHOLD_BITCOIN_HIGH = float(os.getenv("TS_CONFIDENCE_THRESHOLD_BITCOIN_HIGH", "0.93"))
    TS_CONFIDENCE_THRESHOLD_BITCOIN_MED = float(os.getenv("TS_CONFIDENCE_THRESHOLD_BITCOIN_MED", "0.88"))

    # --- Generic Limit Offsets (can be shared) ---
    LIMIT_OFFSET_BUY = float(os.getenv("LIMIT_OFFSET_BUY", "0.005"))
    LIMIT_OFFSET_SHORT = float(os.getenv("LIMIT_OFFSET_SHORT", "0.005"))
