import logging
import logfire
from typing import Union

from app.models import AnalysisOutput, FEDDecisionImpact, FailedFEDAnalysis
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

    def _determine_trade_params(self, topic: str, direction: str, confidence: float) -> dict | None:
        """
        Determines the trade parameters (amount, leverage, limit offset) based on
        topic, direction, and confidence.
        """
        topic_lower = topic.lower()
        direction_lower = direction.lower()

        # Initialize current settings with generic defaults
        amount_buy_high = AppConfig.ORDER_AMOUNT_BUY_HIGH_CONF
        amount_short_high = AppConfig.ORDER_AMOUNT_SHORT_HIGH_CONF
        amount_buy_med = AppConfig.ORDER_AMOUNT_BUY_MED_CONF
        amount_short_med = AppConfig.ORDER_AMOUNT_SHORT_MED_CONF
        leverage_buy_high = AppConfig.LEVERAGE_BUY_HIGH_CONF
        leverage_short_high = AppConfig.LEVERAGE_SHORT_HIGH_CONF
        leverage_buy_med = AppConfig.LEVERAGE_BUY_MED_CONF
        leverage_short_med = AppConfig.LEVERAGE_SHORT_MED_CONF
        confidence_threshold_high_current = AppConfig.CONFIDENCE_THRESHOLD_HIGH
        confidence_threshold_med_current = AppConfig.CONFIDENCE_THRESHOLD_MED

        # Apply topic-specific overrides
        if topic_lower == "bitcoin":
            amount_buy_high = AppConfig.ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF
            amount_short_high = AppConfig.ORDER_AMOUNT_BITCOIN_SHORT_HIGH_CONF
            amount_buy_med = AppConfig.ORDER_AMOUNT_BITCOIN_BUY_MED_CONF
            amount_short_med = AppConfig.ORDER_AMOUNT_BITCOIN_SHORT_MED_CONF
            leverage_buy_high = AppConfig.LEVERAGE_BITCOIN_BUY_HIGH_CONF
            leverage_short_high = AppConfig.LEVERAGE_BITCOIN_SHORT_HIGH_CONF
            leverage_buy_med = AppConfig.LEVERAGE_BITCOIN_BUY_MED_CONF
            leverage_short_med = AppConfig.LEVERAGE_BITCOIN_SHORT_MED_CONF
            confidence_threshold_high_current = AppConfig.CONFIDENCE_THRESHOLD_BITCOIN_HIGH
            confidence_threshold_med_current = AppConfig.CONFIDENCE_THRESHOLD_BITCOIN_MED
        elif topic_lower == "fed_decision":
            amount_buy_high = AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF
            amount_short_high = AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF
            amount_buy_med = AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF
            amount_short_med = AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF
            leverage_buy_high = AppConfig.LEVERAGE_FED_BUY_HIGH_CONF
            leverage_short_high = AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF
            leverage_buy_med = AppConfig.LEVERAGE_FED_BUY_MED_CONF
            leverage_short_med = AppConfig.LEVERAGE_FED_SHORT_MED_CONF
            confidence_threshold_high_current = AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH
            confidence_threshold_med_current = AppConfig.CONFIDENCE_THRESHOLD_FED_MED

        order_to_execute = None
        full_desc = ""
        current_amount = None
        current_leverage = None
        limit_offset = None

        if direction_lower == "up" or direction_lower == "positive": # "positive" for FED agent
            trade_action_desc_prefix = "BUY/LONG"
            limit_offset = AppConfig.LIMIT_OFFSET_BUY
            if confidence >= confidence_threshold_high_current:
                desc_suffix = "High-Confidence UP"
                current_amount = amount_buy_high
                current_leverage = leverage_buy_high
            elif confidence >= confidence_threshold_med_current:
                desc_suffix = "Medium-Confidence UP"
                current_amount = amount_buy_med
                current_leverage = leverage_buy_med
            else:
                logger.info(
                    f"Predicted UP, but confidence ({confidence:.2f}) is below {confidence_threshold_med_current} for a BUY. No action.")
                return None

        elif direction_lower == "down" or direction_lower == "negative": # "negative" for FED agent
            trade_action_desc_prefix = "SHORT"
            limit_offset = AppConfig.LIMIT_OFFSET_SHORT
            if confidence >= confidence_threshold_high_current:
                desc_suffix = "High-Confidence DOWN"
                current_amount = amount_short_high
                current_leverage = leverage_short_high
            elif confidence >= confidence_threshold_med_current:
                desc_suffix = "Medium-Confidence DOWN"
                current_amount = amount_short_med
                current_leverage = leverage_short_med
            else:
                logger.info(
                    f"Predicted DOWN, but confidence ({confidence:.2f}) is below {confidence_threshold_med_current} for a SHORT. No action.")
                return None
        else: # "neutral" from social media agent or FED agent
            logger.info(f"Predicted NEUTRAL or no clear direction ('{direction_lower}'). No action.")
            return None

        if current_amount is not None and current_leverage is not None and limit_offset is not None:
            full_desc = f"{trade_action_desc_prefix} ({desc_suffix})"
            order_to_execute = {
                "amount": current_amount,
                "limit_offset_percentage": limit_offset,
                "leverage": current_leverage,
                "description": full_desc
            }
            return order_to_execute
        return None

    def execute_trade_from_analysis(self,
                                    analysis_result: Union[AnalysisOutput, FEDDecisionImpact],
                                    content_id_for_log: str):
        """
        Processes an AI analysis result and executes a trade if conditions are met.

        Args:
            analysis_result (Union[AnalysisOutput, FEDDecisionImpact]): The result from an AI agent.
            content_id_for_log (str): An ID for logging purposes.
        """
        log_prefix = f"Content ID [{content_id_for_log}]:"

        if isinstance(analysis_result, AnalysisOutput): # From social_media_agent
            topic = analysis_result.topic_classification
            direction = analysis_result.price_direction
            confidence = analysis_result.price_confidence
        elif isinstance(analysis_result, FEDDecisionImpact): # From fed_decision_agent
            topic = "fed_decision" # Assign a specific topic for FED outcomes
            direction = analysis_result.impact_on_bitcoin # Maps to "positive", "negative", "neutral"
            confidence = analysis_result.confidence
        else:
            logger.error(f"{log_prefix} Unsupported analysis result type: {type(analysis_result)}. Cannot execute trade.")
            logfire.error(f"{log_prefix} Unsupported analysis result type: {type(analysis_result)}. Cannot execute trade.")
            return

        if not topic or not direction or confidence is None:
            topic_str = topic if topic is not None else "N/A"
            direction_str = direction if direction is not None else "N/A"
            confidence_str = f"{confidence:.2f}" if confidence is not None else "N/A"
            logger.info(
                f"{log_prefix} Incomplete analysis data for trading. "
                f"Topic='{topic_str}', Direction='{direction_str}' (Conf: {confidence_str}). No trading action."
            )
            logfire.info(
                f"{log_prefix} Incomplete analysis data for trading. "
                f"Topic='{topic_str}', Direction='{direction_str}' (Conf: {confidence_str}). No trading action."
            )
            return

        trade_params = self._determine_trade_params(topic, direction, confidence)

        if not trade_params:
            logger.info(f"{log_prefix} No trade parameters determined based on analysis. No action.")
            return

        order_to_execute = trade_params
        sms_message_body = (
            f"aSentrX: {order_to_execute['description']} for {self.TRADE_SYMBOL}. "
            f"Amt: {order_to_execute['amount']}, Lev: {order_to_execute['leverage']}"
        )

        logger.info(
            f"{log_prefix} ACTION: {order_to_execute['description']}. Preparing order. "
            f"Amount: {order_to_execute['amount']}, Leverage: {order_to_execute['leverage']}, "
            f"Limit Offset: {order_to_execute['limit_offset_percentage'] * 100:.2f}%"
        )
        logfire.info(
            f"{log_prefix} ACTION: {order_to_execute['description']}. Preparing order. "
            f"Amount: {order_to_execute['amount']}, Leverage: {order_to_execute['leverage']}, "
            f"Limit Offset: {order_to_execute['limit_offset_percentage'] * 100:.2f}%"
        )

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
                logger.error(
                    f"{log_prefix} EXCEPTION during order execution for {order_to_execute['description']}: {e}",
                    exc_info=True)
        else:
            logger.info(f"{log_prefix} PROD_EXECUTION is FALSE. Simulating order execution for {order_to_execute['description']}.")
            order_executed_successfully = True # Simulate success in dev mode

        if AppConfig.SMS_NOTIFICATIONS_ENABLED and self.sms_notifier:
            final_sms_body = f"{sms_message_body}. Status: {'Succeeded' if order_executed_successfully else 'Failed/Aborted'}."
            self.sms_notifier.send_sms(final_sms_body)
        elif sms_message_body and not self.sms_notifier:
            logger.debug(
                f"{log_prefix} SMS notification for '{sms_message_body}' was prepared, but SmsNotifier is not active.")