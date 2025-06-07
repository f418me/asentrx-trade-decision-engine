import logging
from app.trading.bitfinex_trader import BitfinexTrader
from app.utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.Trader")


class Trader:
    """
    A higher-level trading class that uses BitfinexTrader to execute orders
    based on derivative status and calculated limit prices.
    """
    # Constants for derivative status array indices (based on your example output)
    # [['tBTCF0:USTF0', MTS, None, LAST_PRICE, BID, ..., MARK_PRICE, ...]]
    # Index 0: SYMBOL
    # Index 3: LAST_PRICE
    # Index 15: MARK_PRICE (in your provided example output structure)
    # Note: Standard Bitfinex API doc for /status/deriv might list MARK_PRICE at index 9.
    # We'll use 15 based on your data, but add a check.
    DERIV_STATUS_SYMBOL_IDX = 0
    DERIV_STATUS_LAST_PRICE_IDX = 3
    DERIV_STATUS_MARK_PRICE_IDX = 15

    def __init__(self, bfx_trader: BitfinexTrader):
        """
        Initializes the Trader.

        Args:
            bfx_trader (BitfinexTrader): An instance of the BitfinexTrader class.
        """
        if not isinstance(bfx_trader, BitfinexTrader):
            raise TypeError("bfx_trader must be an instance of BitfinexTrader")
        self.bfx_trader = bfx_trader
        logger.info("Trader initialized.")

    def execute_order(self, symbol: str, amount: float, leverage: int, limit_offset_percentage: float):
        """
        Executes a trading order.

        It first fetches the derivative status to get the current market price,
        then calculates a limit price based on the offset percentage, and finally
        submits a LIMIT order.

        Args:
            symbol (str): The trading symbol (e.g., "tBTCF0:USTF0").
            amount (float): Order amount. Positive for buy, negative for sell.
            leverage (int): The leverage for the order (e.g., 10 for 10x).
            limit_offset_percentage (float): The percentage above/below the current market price
                                             at which to set the limit.
                                             Example: 0.01 means 1% above/below market price.
                                             A positive value for offset means the limit price
                                             will be higher for buy and lower for sell, generally.

        Returns:
            The result of the order submission from BitfinexTrader, or None if an error occurs
            before submission.
        """
        logger.info(
            f"Attempting to execute order for {symbol}: amount={amount}, lev={leverage}, offset={limit_offset_percentage * 100}%.")

        status_data_list = self.bfx_trader.get_derivative_status(symbol=symbol)

        if not status_data_list:
            logger.error(f"Could not retrieve derivative status for {symbol}. Aborting order.")
            return None

        if not isinstance(status_data_list, list) or not status_data_list:
            logger.error(
                f"Derivative status for {symbol} is empty or not in expected list format. Aborting order. Received: {status_data_list}")
            return None

        # The response is a list containing one list with the actual data
        status_data = status_data_list[0]

        if not isinstance(status_data, list) or len(status_data) <= max(self.DERIV_STATUS_MARK_PRICE_IDX,
                                                                        self.DERIV_STATUS_LAST_PRICE_IDX):
            logger.error(
                f"Derivative status data for {symbol} is malformed or too short. Aborting order. Received inner list: {status_data}")
            return None

        mark_price_val = status_data[self.DERIV_STATUS_MARK_PRICE_IDX]
        last_price_val = status_data[self.DERIV_STATUS_LAST_PRICE_IDX]

        current_price = None
        if mark_price_val is not None:
            try:
                current_price = float(mark_price_val)
                logger.debug(f"Using MARK_PRICE: {current_price} for {symbol}.")
            except (ValueError, TypeError):
                logger.warning(f"MARK_PRICE '{mark_price_val}' for {symbol} is not a valid number. Trying LAST_PRICE.")

        if current_price is None and last_price_val is not None:
            try:
                current_price = float(last_price_val)
                logger.debug(f"Using LAST_PRICE: {current_price} for {symbol} (MARK_PRICE was invalid or None).")
            except (ValueError, TypeError):
                logger.warning(f"LAST_PRICE '{last_price_val}' for {symbol} is not a valid number.")

        if current_price is None:
            logger.error(
                f"Could not determine current price (both MARK_PRICE and LAST_PRICE are invalid or None) for {symbol}. Aborting order.")
            return None

        # calculate limit price
        # 0.01 means limit is 1% higher/lower than the current price
        # For a LONG order, limit_price = current_price * (1 + offset)
        # For a SHORT order, limit_price = current_price * (1 - offset)
        if amount > 0:  # Buy/Long
            limit_price = current_price * (1 + limit_offset_percentage)
        else:  # Sell/Short
            limit_price = current_price * (1 - limit_offset_percentage)

        logger.info(
            f"Calculated limit price for {symbol}: {limit_price:.5f} (from current: {current_price:.5f} with offset: {limit_offset_percentage * 100:.2f}%)")

        order_result = self.bfx_trader.submit_order(
            symbol=symbol,
            amount=str(amount),
            price=str(limit_price),  # API requires string
            lev=leverage,
            type="LIMIT"  # Explicitly set type to LIMIT
        )

        if order_result:
            logger.info(f"Order submission successful for {symbol}: {order_result}")
        else:
            logger.error(f"Order submission failed for {symbol}.")

        return order_result