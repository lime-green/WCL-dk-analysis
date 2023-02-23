from analysis.base import AnalysisScorer, BaseAnalyzer
from analysis.core_analysis import (
    BombAnalyzer,
    CoreAnalysisConfig,
    GCDAnalyzer,
    RuneTracker,
    DiseaseAnalyzer,
    BuffTracker,
)
from report import Fight


class Window:
    start: int
    end: int

    def __init__(self, start=None, end=None):
        self.start = start
        self.end = end

    def __repr__(self):
        return f"<Window start={self.start} end={self.end}>"


class UptimeAnalyzer(BaseAnalyzer):
    def __init__(self, duration, buff_tracker, buff_name):
        self._duration = duration
        self._windows = []
        self._window = None
        self._buff_name = buff_name

        if buff_name in buff_tracker:
            self._add_window(0)

    def _add_window(self, start, end=None):
        self._window = Window(start, end)
        self._windows.append(self._window)

    def add_event(self, event):
        if event["type"] not in ("applybuff", "removebuff"):
            return

        if event["ability"] != self._buff_name:
            return

        if event["type"] == "applybuff":
            if not self._window or self._window.end is not None:
                self._add_window(event["timestamp"])
        elif event["type"] == "removebuff":
            if self._window:
                self._window.end = event["timestamp"]
            else:  # assume it was a starting aura
                self._add_window(0, event["timestamp"])

    def uptime(self):
        uptime_duration = 0

        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._duration

        for window in self._windows:
            uptime_duration += (window.end - window.start)

        print(self._buff_name, uptime_duration / self._duration)
        return uptime_duration / self._duration

    def report(self):
        return {"uptime": self.uptime()}


class BoneShieldAnalyzer(BaseAnalyzer):
    def __init__(self, duration, buff_tracker):
        self._uptime = UptimeAnalyzer(duration, buff_tracker, "Bone Shield")

    def add_event(self, event):
        self._uptime.add_event(event)

    def report(self):
        return {
            "bone_shield_uptime": self._uptime.uptime()
        }


class DesolationAnalyzer(BaseAnalyzer):
    def __init__(self, duration, buff_tracker):
        self._uptime = UptimeAnalyzer(duration, buff_tracker, "Desolation")

    def add_event(self, event):
        self._uptime.add_event(event)

    def report(self):
        return {
            "desolation_uptime": self._uptime.uptime()
        }


class GhoulFrenzyAnalyzer(BaseAnalyzer):
    def __init__(self, duration, buff_tracker):
        self._uptime = UptimeAnalyzer(duration, buff_tracker, "Ghoul Frenzy")

    def add_event(self, event):
        self._uptime.add_event(event)

    def report(self):
        return {
            "ghoul_frenzy_uptime": self._uptime.uptime()
        }


class GargoyleAnalyzer(BaseAnalyzer):
    class GargoyleWindow:
        def __init__(self, start):
            self.start = start
            self.end = start + 30000

    def __init__(self, fight_duration, buff_tracker):
        self._windows = []
        self._window = None
        self._buff_tracker = buff_tracker
        self._fight_duration = fight_duration

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Summon Gargoyle":
            self._window = self.GargoyleWindow(event["timestamp"])
            self._windows.append(self._window)

        if not self._window or self._window.end > event["timestamp"]:
            return

    @property
    def possible_gargoyles(self):
        return max(1 + (self._fight_duration - 20000) // 183000, len(self._windows))


class UnholyAnalysisScorer(AnalysisScorer):
    def report(self):
        # Speed
        gcd_score = self.ScoreWeight(self.get_analyzer(GCDAnalyzer).score(), 3)
        drift_score = self.ScoreWeight(self.get_analyzer(RuneTracker).score(), 3)

        # Rotation
        disease_score = self.ScoreWeight(self.get_analyzer(DiseaseAnalyzer).score(), 1)

        # Misc
        consume_score = self.ScoreWeight(self.get_analyzer(BuffTracker).score(), 1)
        bomb_score = self.ScoreWeight(self.get_analyzer(BombAnalyzer).score(), 2)

        total_score = self._get_scores(
            gcd_score,
            drift_score,
            disease_score,
            consume_score,
            bomb_score,
        )

        return {
            "analysis_scores": {
                "total_score": total_score,
            }
        }


class UnholyAnalysisConfig(CoreAnalysisConfig):
    def get_analyzers(self, fight: Fight, buff_tracker):
        bone_shield_analyzer = BoneShieldAnalyzer(fight.duration, buff_tracker)
        desolation_analyzer = DesolationAnalyzer(fight.duration, buff_tracker)
        ghoul_frenzy_analyzer = GhoulFrenzyAnalyzer(fight.duration, buff_tracker)
        gargoyle_analyzer = GargoyleAnalyzer(fight.duration, buff_tracker)

        return super().get_analyzers(fight, buff_tracker) + [
            bone_shield_analyzer,
            desolation_analyzer,
            ghoul_frenzy_analyzer,
            gargoyle_analyzer,
        ]

    def get_scorer(self, analyzers):
        return UnholyAnalysisScorer(analyzers)
