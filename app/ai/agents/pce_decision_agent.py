from datetime import datetime, timezone

from app.ai.jev_analyzer import JevAnalyzer
from app.ai.jev_schemas import PCEJudgments
from app.models import AnalysisAbstention, FailedPCEAnalysis, PCEExpectation


class PCEDecisionAnalyzer(JevAnalyzer):
    source = "pce"
    schema = PCEJudgments
    expectation_type = PCEExpectation
    failure_type = FailedPCEAnalysis

    def __init__(self, expectations_path="app/pce_expectations.json"):
        super().__init__(expectations_path)

    def in_release_window(self):
        elapsed = (datetime.now(timezone.utc) - self.expectations.release_at).total_seconds()
        return 0 <= elapsed < self.expectations.window_seconds

    async def analyze_content(self, content, content_id_for_logging="N/A"):
        if not self.in_release_window():
            return AnalysisAbstention(source="pce", reason="Outside the configured PCE release window.")
        result = await super().analyze_content(content, content_id_for_logging)
        if not self.in_release_window():
            return AnalysisAbstention(source="pce", reason="PCE release window expired during analysis.")
        return result
