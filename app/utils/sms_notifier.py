import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException # Import for specific Twilio errors

from app.config import AppConfig # Import AppConfig for settings
from app.utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.SmsNotifier")

class SmsNotifier:
    """
    A class to handle sending SMS notifications using Twilio.
    """
    def __init__(self):
        self.account_sid = AppConfig.TWILIO_ACCOUNT_SID
        self.auth_token = AppConfig.TWILIO_AUTH_TOKEN
        self.from_number = AppConfig.TWILIO_FROM_NUMBER
        self.to_number = AppConfig.TWILIO_TO_NUMBER

        if not AppConfig.SMS_NOTIFICATIONS_ENABLED:
            logger.info("SMS notifications are disabled by configuration (SMS_NOTIFICATIONS_ENABLED=False).")
            self.client = None
            return

        if not all([self.account_sid, self.auth_token, self.from_number, self.to_number]):
            logger.warning(
                "Twilio credentials or phone numbers are not fully configured in .env. "
                "SMS notifications will be disabled."
            )
            self.client = None
        else:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized successfully for SMS notifications.")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}", exc_info=True)
                self.client = None

    def send_sms(self, body: str) -> str | None:
        """
        Sends an SMS message.

        Args:
            body (str): The content of the SMS message.

        Returns:
            str | None: The message SID if successful, None otherwise.
        """
        if not self.client:
            logger.warning("Twilio client not initialized or SMS notifications are disabled. Cannot send SMS.")
            return None

        if not body:
            logger.warning("SMS body is empty. Cannot send SMS.")
            return None

        try:
            message = self.client.messages.create(
                from_=self.from_number,
                body=body,
                to=self.to_number
            )
            logger.info(f"SMS sent successfully to {self.to_number}. Message SID: {message.sid}")
            return message.sid
        except TwilioRestException as e: # Catch specific Twilio errors
            logger.error(f"Twilio API error while sending SMS to {self.to_number}: {e}", exc_info=True)
            return None
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error while sending SMS to {self.to_number}: {e}", exc_info=True)
            return None