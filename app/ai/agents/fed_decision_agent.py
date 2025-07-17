import logging
import json
from typing import Union

from pydantic_ai import Agent
from app.models import FEDDecisionImpact, FailedFEDAnalysis, FEDExpectation, IrrelevantFEDContent
from app.config import AppConfig
from app.utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.FEDDecisionAgent")

class FEDDecisionAnalyzer:
    def __init__(self, expectations_path: str = "app/expectations.json"):
        self.expectations_path = expectations_path
        self.expectations = self._load_expectations()
        self.agent = self._initialize_agent()
        logger.info("FEDDecisionAnalyzer initialized.")
        logger.debug(f"Loaded FED expectations: {self.expectations.model_dump_json(indent=2)}")

    def _load_expectations(self) -> FEDExpectation:
        try:
            with open(self.expectations_path, 'r') as f:
                data = json.load(f)
            return FEDExpectation(**data)
        except FileNotFoundError:
            logger.error(f"Expectations file not found: {self.expectations_path}")
            raise FileNotFoundError(f"FED expectations file not found at {self.expectations_path}")
        except Exception as e:
            logger.error(f"Unexpected error loading expectations from {self.expectations_path}: {e}")
            raise

    def _initialize_agent(self):
        """Initializes the pydantic-ai agent for FED decision analysis."""
        return Agent[None, Union[FEDDecisionImpact, IrrelevantFEDContent, FailedFEDAnalysis]](
            AppConfig.MODEL,
            output_type=Union[FEDDecisionImpact, IrrelevantFEDContent, FailedFEDAnalysis],
            system_prompt=(
                'Analyze the provided text regarding the Federal Reserve\'s latest interest rate decision '
                'and accompanying statement from the Federal Open Market Committee (FOMC).\n'
                '1. **Identify the Actual Decision:** Extract the actual interest rate change (e.g., "hold", "increase", "decrease" by "X%"), '
                'and determine the overall narrative tone (e.g., "hawkish", "dovish", "neutral", "mixed"). '
                'Summarize this as `actual_fed_decision_summary`.\n'
                '2. **Compare with Expectations:** Compare the actual decision and narrative with the following provided expectations:\n'
                f'{self.expectations.model_dump_json(indent=2)}\n'
                '3. **Predict Bitcoin Impact:** Based on this comparison, predict the likely impact on Bitcoin\'s price:\n'
                '- "positive": The actual decision is more dovish/less hawkish than expected, or a surprise easing/more accommodative stance.\n'
                '- "negative": The actual decision is more hawkish/less dovish than expected, or a surprise tightening/more restrictive stance.\n'
                '- "neutral": The actual decision is broadly in line with expectations or has no clear dominant sentiment for Bitcoin.\n'
                '4. **Provide confidence and reasoning:** Output the `impact_on_bitcoin`, a `confidence` level (float 0.0-1.0), and a brief `reasoning`.'
                'Also, if possible, parse and return specific `actual_interest_rate_change_type`, `actual_interest_rate_change_amount`, and `actual_narrative`.\n'
                # --- ÄNDERUNG 3: Neue Anweisung im Prompt hinzufügen ---
                '5. **Handle Irrelevant Content:** If the text is clearly NOT about a Federal Reserve interest rate decision (e.g., it is about a different topic like a census, a report on banking supervision, etc.), '
                'you MUST output an `IrrelevantFEDContent` object with a brief `reason` explaining why the text is not an FOMC decision statement.'
                '\n6. **Detect FED Chair Changes:** If the text mentions that the Federal Reserve Chair has been fired, resigned, or replaced, set `fed_chair_event` to a short description of that change.'
            ),
        )

    async def analyze_content(self, content: str, content_id_for_logging: str = "N/A") -> Union[FEDDecisionImpact, IrrelevantFEDContent, FailedFEDAnalysis]:
        """
        Asynchronously analyzes the FED decision content and predicts its impact on Bitcoin.
        This uses the native async `.run()` method of the agent.

        Args:
            content (str): The text content of the FED announcement.
            content_id_for_logging (str): An ID for logging purposes.

        Returns:
            Union[FEDDecisionImpact, IrrelevantFEDContent, FailedFEDAnalysis]: The analysis result, an irrelevance object, or a failure object.
        """
        logger.info(f"Content ID [{content_id_for_logging}]: Starting FED decision analysis for: '{content[:100]}...'")
        try:
            result = await self.agent.run(content)

            if isinstance(result.output, FEDDecisionImpact):
                logger.info(
                    f"Content ID [{content_id_for_logging}]: FED analysis result: "
                    f"Impact='{result.output.impact_on_bitcoin}', Confidence={result.output.confidence:.2f}, "
                    f"Summary='{result.output.actual_fed_decision_summary}', Reasoning='{result.output.reasoning}'"
                )
                if result.output.fed_chair_event:
                    logger.info(
                        f"Content ID [{content_id_for_logging}]: Detected FED chair event: {result.output.fed_chair_event}"
                    )
                return result.output
            elif isinstance(result.output, IrrelevantFEDContent):
                logger.info(
                    f"Content ID [{content_id_for_logging}]: Content analyzed as irrelevant. Reason: {result.output.reason}"
                )
                return result.output
            elif isinstance(result.output, FailedFEDAnalysis):
                logger.warning(
                    f"Content ID [{content_id_for_logging}]: FED decision agent failed. Result: {result.output.error_message}")
                return FailedFEDAnalysis(error_message=f"FED decision agent failed: {result.output.error_message}")
            else:
                error_msg = f"Content ID [{content_id_for_logging}]: FED decision agent returned an unexpected Pydantic model type: {type(result.output)}"
                logger.error(error_msg)
                return FailedFEDAnalysis(error_message=error_msg)

        except Exception as e:
            logger.error(
                f"Content ID [{content_id_for_logging}]: An unexpected error occurred during FED decision analysis: {e}",
                exc_info=True
            )
            return FailedFEDAnalysis(error_message=f"Unhandled exception during FED analysis: {e}")