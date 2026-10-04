from app.ai.jev_analyzer import JevAnalyzer
from app.ai.jev_schemas import CPIJudgments
from app.models import CPIExpectation, FailedCPIAnalysis


class CPIDecisionAnalyzer(JevAnalyzer):
    source = "cpi"
    schema = CPIJudgments
    expectation_type = CPIExpectation
    failure_type = FailedCPIAnalysis

    def __init__(self, expectations_path="app/cpi_expectations.json"):
        super().__init__(expectations_path)
