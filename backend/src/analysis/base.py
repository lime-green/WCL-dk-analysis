from typing import Type, TypeVar

R = TypeVar("R")


class BaseAnalyzer:
    def add_event(self, event):
        pass

    def print(self):
        pass

    def report(self):
        return {}


class AnalysisScorer(BaseAnalyzer):
    class ScoreWeight:
        def __init__(self, score, weight):
            self.score = score
            self.weight = weight

    def __init__(self, analyzers):
        self._analyzers = {analyzer.__class__: analyzer for analyzer in analyzers}

    def get_analyzer(self, cls: Type[R]) -> R:
        return self._analyzers[cls]

    @staticmethod
    def _get_scores(*score_weights):
        total = sum(score.weight for score in score_weights)
        return sum((score.score * score.weight) / total for score in score_weights)

    def report(self):
        return {
            "analysis_scores": {
                "total_score": 1,
            }
        }
