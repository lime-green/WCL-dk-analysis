from typing import Type, TypeVar

R = TypeVar("R")


def range_overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


class BaseAnalyzer:
    INCLUDE_PET_EVENTS = False

    def add_event(self, event):
        pass

    def print(self):
        pass

    def report(self):
        return {}

    def score(self):
        raise NotImplementedError


class ScoreWeight:
    def __init__(self, score, weight):
        assert 0 <= score <= 1
        self.score = score
        self.weight = weight

    @staticmethod
    def calculate(*score_weights):
        total = sum(score.weight for score in score_weights)
        return sum((score.score * score.weight) / total for score in score_weights)


class AnalysisScorer(BaseAnalyzer):
    def __init__(self, analyzers):
        self._analyzers = {analyzer.__class__: analyzer for analyzer in analyzers}

    def get_analyzer(self, cls: Type[R]) -> R:
        return self._analyzers[cls]

    def report(self):
        return {
            "analysis_scores": {
                "total_score": 1,
            }
        }
