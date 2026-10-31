
import logging
from app.models import CPIReportImpact, FEDDecisionImpact, NFPReportImpact, SocialMediaMarketSignal, AnyAnalysisResult
from app.config import AppConfig
from app.trading.trader import Trader
from app.utils.slack_notifier import SlackNotifier
from app.utils.logger_config import APP_LOGGER_NAME
from app.utils.observability import logfire_error, logfire_info, trade_outcome

logger = logging.getLogger(f"{APP_LOGGER_NAME}.TradeDecisionManager")

class TradeDecisionManager:
    def __init__(self, trader: Trader, slack_notifier: SlackNotifier):
        self.trader = trader
        self.slack_notifier = slack_notifier
        self.PROD_EXECUTION = AppConfig.PROD_EXECUTION
        self.TRADE_SYMBOL = AppConfig.TRADE_SYMBOL

        if not self.PROD_EXECUTION:
            logger.warning("PROD_EXECUTION is DISABLED. No real trades will be executed.")
        else:
            logger.info("PROD_EXECUTION is ENABLED. Trades will be sent to Bitfinex.")
        logger.info("TradeDecisionManager initialized.")

    def _log_social_no_trade(self, content_id: str, signal: SocialMediaMarketSignal, veto_reason: str):
        self._outcome(signal, content_id, "no_trade", "social_gate_rejected", veto_reason)
        logfire_info(
            "trade_decision_no_trade",
            source="truthsocial",
            content_id=content_id,
            veto_reason=veto_reason,
            event_type=signal.event_type,
            asset=signal.asset,
            direction=signal.direction,
            confidence=signal.confidence,
            novelty_score=signal.novelty_score,
            time_sensitivity=signal.time_sensitivity,
            risk_level=signal.risk_level,
            agent_veto_reason=signal.trade_veto_reason,
        )

    def _get_social_media_trade_params(self, signal: SocialMediaMarketSignal, content_id: str) -> dict | None:
        if not signal.is_tradeable:
            veto_reason = signal.trade_veto_reason or signal.reasoning
            logger.info(f"Social signal vetoed as non-tradeable: {veto_reason}")
            self._log_social_no_trade(content_id, signal, f"non_tradeable: {veto_reason}")
            return None

        if signal.asset == "none" or signal.direction == "neutral":
            veto_reason = f"no actionable asset/direction: asset={signal.asset}, direction={signal.direction}"
            logger.info(
                f"Social signal has no actionable asset/direction. Asset='{signal.asset}', "
                f"Direction='{signal.direction}', Veto='{signal.trade_veto_reason}'"
            )
            self._log_social_no_trade(content_id, signal, veto_reason)
            return None

        if signal.novelty_score < AppConfig.TS_MIN_NOVELTY_SCORE:
            veto_reason = (
                f"novelty {signal.novelty_score:.2f} below threshold "
                f"{AppConfig.TS_MIN_NOVELTY_SCORE:.2f}"
            )
            logger.info(
                f"Social signal novelty {signal.novelty_score:.2f} is below threshold "
                f"{AppConfig.TS_MIN_NOVELTY_SCORE:.2f}. No action."
            )
            self._log_social_no_trade(content_id, signal, veto_reason)
            return None

        if signal.time_sensitivity not in AppConfig.TS_ALLOWED_TIME_SENSITIVITIES:
            veto_reason = (
                f"timing {signal.time_sensitivity} not allowed; allowed="
                f"{sorted(AppConfig.TS_ALLOWED_TIME_SENSITIVITIES)}"
            )
            logger.info(
                f"Social signal timing '{signal.time_sensitivity}' is not in allowed timings "
                f"{sorted(AppConfig.TS_ALLOWED_TIME_SENSITIVITIES)}. No action."
            )
            self._log_social_no_trade(content_id, signal, veto_reason)
            return None

        if signal.asset == "btc" or signal.event_type in {"crypto_policy_positive", "crypto_policy_negative"}:
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
        else:
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

        event_desc = signal.event_type.replace("_", " ").upper()
        if signal.direction == "up":
            if signal.confidence >= conf_high:
                return {"amount": amount_buy_high, "leverage": leverage_buy_high, "desc": f"High-Confidence {event_desc} UP"}
            if signal.confidence >= conf_med:
                return {"amount": amount_buy_med, "leverage": leverage_buy_med, "desc": f"Medium-Confidence {event_desc} UP"}
        elif signal.direction == "down":
            if signal.confidence >= conf_high:
                return {"amount": amount_short_high, "leverage": leverage_short_high, "desc": f"High-Confidence {event_desc} DOWN"}
            if signal.confidence >= conf_med:
                return {"amount": amount_short_med, "leverage": leverage_short_med, "desc": f"Medium-Confidence {event_desc} DOWN"}
        self._log_social_no_trade(
            content_id,
            signal,
            f"confidence {signal.confidence:.2f} below threshold {conf_med:.2f}",
        )
        return None

    def _get_fed_trade_params(self, direction: str, confidence: float) -> dict | None:
        conf_high = AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH
        conf_med = AppConfig.CONFIDENCE_THRESHOLD_FED_MED

        if direction == "positive":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "desc": "High-Confidence FED POSITIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_MED_CONF, "desc": "Medium-Confidence FED POSITIVE"}
        elif direction == "negative":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "desc": "High-Confidence FED NEGATIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "desc": "Medium-Confidence FED NEGATIVE"}
        return None

    def _get_nfp_trade_params(self, direction: str, confidence: float) -> dict | None:
        conf_high = AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH
        conf_med = AppConfig.CONFIDENCE_THRESHOLD_FED_MED

        if direction == "positive":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "desc": "High-Confidence NFP POSITIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_MED_CONF, "desc": "Medium-Confidence NFP POSITIVE"}
        elif direction == "negative":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "desc": "High-Confidence NFP NEGATIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "desc": "Medium-Confidence NFP NEGATIVE"}
        return None

    def _get_cpi_trade_params(self, direction: str, confidence: float) -> dict | None:
        conf_high = AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH
        conf_med = AppConfig.CONFIDENCE_THRESHOLD_FED_MED

        if direction == "positive":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "desc": "High-Confidence CPI POSITIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_BUY_MED_CONF, "desc": "Medium-Confidence CPI POSITIVE"}
        elif direction == "negative":
            if confidence >= conf_high:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "desc": "High-Confidence CPI NEGATIVE"}
            if confidence >= conf_med:
                return {"amount": AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, "leverage": AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "desc": "Medium-Confidence CPI NEGATIVE"}
        return None

    def _outcome(self, result, content_id, outcome, reason_code, reason, **extra):
        social = isinstance(result, SocialMediaMarketSignal)
        bitcoin = social and (result.asset == "btc" or result.event_type in
                              {"crypto_policy_positive", "crypto_policy_negative"})
        high = (AppConfig.TS_CONFIDENCE_THRESHOLD_BITCOIN_HIGH if bitcoin else
                AppConfig.TS_CONFIDENCE_THRESHOLD_HIGH) if social else AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH
        medium = (AppConfig.TS_CONFIDENCE_THRESHOLD_BITCOIN_MED if bitcoin else
                  AppConfig.TS_CONFIDENCE_THRESHOLD_MED) if social else AppConfig.CONFIDENCE_THRESHOLD_FED_MED
        source = ("truthsocial" if social else "fed" if isinstance(result, FEDDecisionImpact)
                  else "cpi" if isinstance(result, CPIReportImpact)
                  else "nfp" if isinstance(result, NFPReportImpact) else "unknown")
        trade_outcome(
            content_id=content_id, outcome=outcome, reason_code=reason_code, reason=reason,
            source=source, symbol=self.TRADE_SYMBOL, prod_execution=self.PROD_EXECUTION,
            confidence=getattr(result, "confidence", None),
            confidence_threshold_high=high, confidence_threshold_medium=medium,
            analysis_reasoning=getattr(result, "reasoning", None),
            direction=getattr(result, "direction", getattr(result, "impact_on_bitcoin", None)),
            order_attempted=self.PROD_EXECUTION and outcome in {"submitted", "submission_failed"},
            **extra,
        )

    def execute_trade_from_analysis(self, result: AnyAnalysisResult, content_id: str):
        log_prefix = f"Content ID [{content_id}]:"
        trade_params = None
        
        if isinstance(result, SocialMediaMarketSignal):
            trade_params = self._get_social_media_trade_params(result, content_id)

        elif isinstance(result, FEDDecisionImpact):
            trade_params = self._get_fed_trade_params(result.impact_on_bitcoin, result.confidence)
            logfire_info(
                "fed_trade_signal_evaluated",
                content_id=content_id,
                impact_on_bitcoin=result.impact_on_bitcoin,
                confidence=result.confidence,
                actual_interest_rate_change_type=result.actual_interest_rate_change_type,
                actual_interest_rate_change_amount=result.actual_interest_rate_change_amount,
                actual_narrative=result.actual_narrative,
            )

        elif isinstance(result, NFPReportImpact):
            trade_params = self._get_nfp_trade_params(result.impact_on_bitcoin, result.confidence)
            logfire_info(
                "nfp_trade_signal_evaluated",
                content_id=content_id,
                impact_on_bitcoin=result.impact_on_bitcoin,
                confidence=result.confidence,
                actual_nonfarm_payrolls_k=result.actual_nonfarm_payrolls_k,
                actual_unemployment_rate=result.actual_unemployment_rate,
                actual_average_hourly_earnings_mom=result.actual_average_hourly_earnings_mom,
                actual_average_hourly_earnings_yoy=result.actual_average_hourly_earnings_yoy,
            )

        elif isinstance(result, CPIReportImpact):
            trade_params = self._get_cpi_trade_params(result.impact_on_bitcoin, result.confidence)
            logfire_info(
                "cpi_trade_signal_evaluated",
                content_id=content_id,
                impact_on_bitcoin=result.impact_on_bitcoin,
                confidence=result.confidence,
                actual_headline_cpi_mom=result.actual_headline_cpi_mom,
                actual_headline_cpi_yoy=result.actual_headline_cpi_yoy,
                actual_core_cpi_mom=result.actual_core_cpi_mom,
                actual_core_cpi_yoy=result.actual_core_cpi_yoy,
            )

        else:
            logger.error(f"{log_prefix} Unsupported analysis result type: {type(result)}. Cannot execute trade.")
            self._outcome(result, content_id, "no_trade", "unsupported_result", "Unsupported analysis result type.")
            return

        if not trade_params:
            if not isinstance(result, SocialMediaMarketSignal):
                neutral = result.impact_on_bitcoin == "neutral"
                self._outcome(result, content_id, "no_trade",
                              "neutral_signal" if neutral else "confidence_below_threshold",
                              "No directional signal." if neutral else
                              f"Confidence {result.confidence} below minimum {AppConfig.CONFIDENCE_THRESHOLD_FED_MED}.")
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

        notification_body = (
            f"aSentrX: {order_to_execute['description']} for {self.TRADE_SYMBOL}. "
            f"Amt: {order_to_execute['amount']}, Lev: {order_to_execute['leverage']}"
        )

        logger.info(f"{log_prefix} ACTION: {order_to_execute['description']}. Preparing order.")
        logfire_info(
            "trade_decision_action",
            content_id=content_id,
            symbol=self.TRADE_SYMBOL,
            description=order_to_execute["description"],
            amount=order_to_execute["amount"],
            leverage=order_to_execute["leverage"],
            limit_offset_percentage=order_to_execute["limit_offset_percentage"],
            prod_execution=self.PROD_EXECUTION,
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
                logger.error(f"{log_prefix} EXCEPTION during order execution: {e}", exc_info=True)
                logfire_error(
                    "trade_execution_exception",
                    content_id=content_id,
                    symbol=self.TRADE_SYMBOL,
                    error_message=str(e),
                )
        else:
            logger.info(f"{log_prefix} PROD_EXECUTION is FALSE. Simulating order execution.")
            order_executed_successfully = True

        logfire_info(
            "trade_execution_result",
            content_id=content_id,
            symbol=self.TRADE_SYMBOL,
            description=order_to_execute["description"],
            prod_execution=self.PROD_EXECUTION,
            success=order_executed_successfully,
        )

        outcome = ("dry_run" if not self.PROD_EXECUTION else
                   "submitted" if order_executed_successfully else "submission_failed")
        self._outcome(
            result, content_id, outcome,
            "production_disabled" if not self.PROD_EXECUTION else
            "signal_accepted" if order_executed_successfully else "execution_failed",
            "Eligible signal simulated; production execution disabled." if not self.PROD_EXECUTION else
            "Directional signal passed gates; trader returned success (fill not verified)."
            if order_executed_successfully else
            "Directional signal passed gates, but trader failed or returned no successful result.",
            amount=order_to_execute["amount"], leverage=order_to_execute["leverage"],
            limit_offset_percentage=limit_offset,
        )

        if AppConfig.SLACK_NOTIFICATIONS_ENABLED and self.slack_notifier:
            status = "Submitted" if order_executed_successfully else "Failed"
            if not self.PROD_EXECUTION:
                status = "Simulated"
            mode = "LIVE" if self.PROD_EXECUTION else "DRY RUN"
            self.slack_notifier.send_message(
                f"[{mode}] {notification_body}. Status: {status}. "
                f"Confidence: {result.confidence:.2f}. Content ID: {content_id}",
                content_id=content_id,
            )
