from app.ai.jev_analyzer import JevAnalyzer
from app.ai.jev_schemas import NFPJudgments
from app.models import NFPExpectation, FailedNFPAnalysis


class NFPDecisionAnalyzer(JevAnalyzer):
    source = "nfp"
    schema = NFPJudgments
    expectation_type = NFPExpectation
    failure_type = FailedNFPAnalysis

    def __init__(self, expectations_path="app/nfp_expectations.json"):
        super().__init__(expectations_path)
