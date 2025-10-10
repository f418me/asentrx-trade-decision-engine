
import logging
import logfire
from app.models import FEDDecisionImpact, SocialMediaAnalysisOutput, AnyAnalysisResult
from app.config import AppConfig
from app.trading.trader import Trader
from app.utils.sms_notifier import SmsNotifier
from app.utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.TradeDecisionManager")

class TradeDecisionManager:
    def __init__(self, trader: Trader, sms_notifier: SmsNotifier):
        self.trader = trader
        self.sms_notifier = sms_notifier
        self.PROD_EXECUTION = AppConfig.PROD_EXECUTION
        self.TRADE_SYMBOL = AppConfig.TRADE_SYMBOL

        if not self.PROD_EXECUTION:
            logger.warning("PROD_EXECUTION is DISABLED. No real trades will be executed.")
        else:
            logger.info("PROD_EXECUTION is ENABLED. Trades will be sent to Bitfinex.")
        logger.info("TradeDecisionManager initialized.")

    def _get_social_media_trade_params(self, topic: str, direction: str, confidence: float) -> dict | None:
        topic_lower = topic.lower()
        
        # Determine which set of TS parameters to use
        if topic_lower == "bitcoin":
            amount_buy_high = AppConfig.TS_ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF
            amount_short_high = AppConfig.TS_ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF
            amount_buy_med = AppConfig.TS_ORDER_AMOUNT_BITCOIN_BUY_MED_CONF
            amount_short_med = AppConfig.TS_ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF
            leverage_buy_high = AppConfig.TS_LEVERAGE_BITCOIN_BUY_HIGH_CONF
            leverage_short_high = AppConfig.TS_LEVERAGE_BITCOIN_SHORT_HIGH_CONF
            leverage_buy_med = AppConfig.TS_LEVERAGE_BITCOIN_BUY_MED_CONF
            leverage_short_med = AppConfig.TS_LEVERAGE_BITCOIN_SHORT_MED_CONF
            conf_high = AppConfig.TS_CONFIDENCE_THRESHOLD_BITCOIN_HIGH
            conf_med = AppConfig.TS_CONFIDENCE_THRESHOLD_BITCOIN_MED
        else: # "market", "tariffs"
            amount_buy_high = AppConfig.TS_ORDER_AMOUNT_BUY_HIGH_CONF
            amount_short_high = AppConfig.TS_ORDER_AMOUNT_SHORT_HIGH_CONF
            amount_buy_med = AppConfig.TS_ORDER_AMOUNT_BUY_MED_CONF
            amount_short_med = AppConfig.TS_ORDER_AMOUNT_SHORT_MED_CONF
            leverage_buy_high = AppConfig.TS_LEVERAGE_BUY_HIGH_CONF
            leverage_short_high = AppConfig.TS_LEVERAGE_SHORT_HIGH_CONF
            leverage_buy_med = AppConfig.TS_LEVERAGE_BUY_MED_CONF
            leverage_short_med = AppConfig.TS_LEVERAGE_SHORT_MED_CONF
            conf_high = AppConfig.TS_CONFIDENCE_THRESHOLD_HIGH
            conf_med = AppConfig.TS_CONFIDENCE_THRESHOLD_MED

        if direction == "up":
            if confidence >= conf_high:
                return {"amount": amount_buy_high, "leverage": leverage_buy_high, "desc": "High-Confidence UP"}
            if confidence >= conf_med:
                return {"amount": amount_buy_med, "leverage": leverage_buy_med, "desc": "Medium-Confidence UP"}
        elif direction == "down":
            if confidence >= conf_high:
                return {"amount": amount_short_high, "leverage": leverage_short_high, "desc": "High-Confidence DOWN"}
            if confidence >= conf_med:
                return {"amount": amount_short_med, "leverage": leverage_short_med, "desc": "Medium-Confidence DOWN"}
        return None

    def _get_fed_trade_params(self, direction: str, confidence: float) -> dict | None:
        conf_high = AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH
        conf_med = AppConfig.CONFIDENCE_THRESHOLD_FED_MED

        if direction == "positive":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "desc": "High-Confidence POSITIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_MED_CONF, "desc": "Medium-Confidence POSITIVE"}
        elif direction == "negative":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "desc": "High-Confidence NEGATIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "desc": "Medium-Confidence NEGATIVE"}
        return None

    def execute_trade_from_analysis(self, result: AnyAnalysisResult, content_id: str):
        log_prefix = f"Content ID [{content_id}]:"
        trade_params = None
        
        if isinstance(result, SocialMediaAnalysisOutput):
            if result.topic_classification in ["market", "bitcoin", "tariffs"] and result.price_direction and result.price_confidence:
                trade_params = self._get_social_media_trade_params(result.topic_classification, result.price_direction, result.price_confidence)
            else:
                logger.info(f"{log_prefix} Social media post topic '{result.topic_classification}' is not actionable.")
                return

        elif isinstance(result, FEDDecisionImpact):
            trade_params = self._get_fed_trade_params(result.impact_on_bitcoin, result.confidence)

        else:
            logger.error(f"{log_prefix} Unsupported analysis result type: {type(result)}. Cannot execute trade.")
            return

        if not trade_params:
            logger.info(f"{log_prefix} Analysis did not meet confidence thresholds for a trade. No action.")
            return

        # Determine limit offset based on trade direction
        limit_offset = AppConfig.LIMIT_OFFSET_BUY if trade_params["amount"] > 0 else AppConfig.LIMIT_OFFSET_SHORT
        
        order_to_execute = {
            "amount": trade_params["amount"],
            "leverage": trade_params["leverage"],
            "description": trade_params["desc"],
            "limit_offset_percentage": limit_offset
        }

        sms_message_body = (
            f"aSentrX: {order_to_execute['description']} for {self.TRADE_SYMBOL}. "
            f"Amt: {order_to_execute['amount']}, Lev: {order_to_execute['leverage']}"
        )

        logger.info(f"{log_prefix} ACTION: {order_to_execute['description']}. Preparing order.")
        logfire.info(f"{log_prefix} ACTION: {order_to_execute['description']}. Preparing order.")

        order_executed_successfully = False
        if self.PROD_EXECUTION:
            try:
                order_result = self.trader.execute_order(
                    symbol=self.TRADE_SYMBOL,
                    amount=order_to_execute["amount"],
                    leverage=order_to_execute["leverage"],
                    limit_offset_percentage=order_to_execute["limit_offset_percentage"]
                )
                if order_result:
                    order_executed_successfully = True
            except Exception as e:
                logger.error(f"{log_prefix} EXCEPTION during order execution: {e}", exc_info=True)
        else:
            logger.info(f"{log_prefix} PROD_EXECUTION is FALSE. Simulating order execution.")
            order_executed_successfully = True

        if AppConfig.SMS_NOTIFICATIONS_ENABLED and self.sms_notifier:
            status = "Succeeded" if order_executed_successfully else "Failed"
            self.sms_notifier.send_sms(f"{sms_message_body}. Status: {status}.")
