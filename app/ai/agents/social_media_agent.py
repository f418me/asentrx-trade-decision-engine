from app.ai.jev_analyzer import JevAnalyzer
from app.ai.jev_schemas import SocialJudgments
from app.models import FailedSocialMediaAnalysis


class SocialMediaPostAnalyzer(JevAnalyzer):
    source = "social"
    schema = SocialJudgments
    failure_type = FailedSocialMediaAnalysis
