from app.ai.jev_analyzer import JevAnalyzer
from app.ai.jev_schemas import FEDJudgments
from app.models import FEDExpectation, FailedFEDAnalysis


class FEDDecisionAnalyzer(JevAnalyzer):
    source = "fed"
    schema = FEDJudgments
    expectation_type = FEDExpectation
    failure_type = FailedFEDAnalysis

    def __init__(self, expectations_path="app/expectations.json"):
        super().__init__(expectations_path)
