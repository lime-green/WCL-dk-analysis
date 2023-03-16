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


class Window:
    start: int
    end: int

    def __init__(self, start, end=None):
        self.start = start
        self.end = end

    @property
    def duration(self):
        if self.end is None:
            return None
        return self.end - self.start

    def intersects(self, other):
        return range_overlap((self.start, self.end), (other.start, other.end))

    def intersection(self, other):
        if not self.intersects(other):
            return None

        return Window(max(self.start, other.start), min(self.end, other.end))

    def contains(self, timestamp):
        if self.end is None:
            return self.start <= timestamp
        return self.start <= timestamp <= self.end

    def __repr__(self):
        return f"<Window start={self.start} end={self.end}>"


def calculate_uptime(windows, ignore_windows, total_duration):
    total_uptime = sum(window.duration for window in windows)

    for window in windows:
        for ignore_window in ignore_windows:
            if window.intersects(ignore_window):
                total_uptime -= window.intersection(ignore_window).duration

    total_duration_without_ignores = total_duration - sum(
        window.duration for window in ignore_windows
    )
    return total_uptime / total_duration_without_ignores


def combine_windows(*windows_list):
    windows = [window for windows in windows_list for window in windows]

    if not windows:
        return []

    windows = sorted(windows, key=lambda window: window.start)

    combined_windows = [windows[0]]
    for window in windows[1:]:
        if window.start <= combined_windows[-1].end:
            combined_windows[-1] = Window(
                window.start, max(combined_windows[-1].end, window.end)
            )
        else:
            combined_windows.append(window)

    return combined_windows
