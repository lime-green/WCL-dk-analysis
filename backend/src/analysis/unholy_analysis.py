from typing import List

from analysis.base import AnalysisScorer, BaseAnalyzer, ScoreWeight
from analysis.core_analysis import (
    BombAnalyzer,
    BuffTracker,
    CoreAnalysisConfig,
    RPAnalyzer,
)
from report import Fight


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

    def __repr__(self):
        return f"<Window start={self.start} end={self.end}>"


class BuffUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, end_time, buff_tracker, buff_names, start_time=0):
        self._start_time = start_time
        self._end_time = end_time
        self._windows = []
        self._window = None

        if isinstance(buff_names, set):
            self._buff_names = buff_names
        else:
            self._buff_names = {buff_names}

        for buff_name in buff_names:
            if buff_name in buff_tracker:
                self._add_window(start_time)

    def _add_window(self, start, end=None):
        assert self._start_time <= start
        if end:
            assert end <= self._end_time

        self._window = Window(start, end)
        self._windows.append(self._window)

    def add_event(self, event):
        if event["type"] not in ("applybuff", "removebuff"):
            return

        if event["ability"] not in self._buff_names:
            return

        if event["type"] == "applybuff" and event["timestamp"] <= self._end_time:
            if not self._window or self._window.end is not None:
                self._add_window(event["timestamp"])
        elif event["type"] == "removebuff":
            end = min(event["timestamp"], self._end_time)

            if self._window:
                self._window.end = end
            else:  # assume it was a starting aura
                self._add_window(self._start_time, end)

    def uptime(self):
        uptime_duration = 0

        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._end_time

        for window in self._windows:
            uptime_duration += min(window.end, self._end_time) - window.start

        return uptime_duration / (self._end_time - self._start_time)

    def score(self):
        return self.uptime()


class DebuffUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, end_time, debuff_name):
        self._windows = []
        self._window = None
        self._debuff_name = debuff_name
        self._end_time = end_time

    def _add_window(self, start, end=None):
        self._window = Window(start, end)
        self._windows.append(self._window)

    def add_event(self, event):
        if event["type"] not in ("applydebuff", "removedebuff", "refreshdebuff"):
            return

        if event["ability"] != self._debuff_name:
            return

        if event["type"] in ("applydebuff", "refreshdebuff"):
            if not self._window or self._window.end is not None:
                self._add_window(event["timestamp"])
        elif event["type"] == "removedebuff":
            end = event["timestamp"]
            self._window.end = end

    def uptime(self):
        uptime_duration = 0

        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._end_time

        for window in self._windows:
            uptime_duration += window.end - window.start

        return uptime_duration / self._end_time

    def score(self):
        return self.uptime()


class BloodPlagueAnalyzer(DebuffUptimeAnalyzer):
    def __init__(self, end_time):
        super().__init__(end_time, "Blood Plague")

    def report(self):
        return {
            "blood_plague_uptime": self.uptime(),
        }


class FrostFeverAnalyzer(DebuffUptimeAnalyzer):
    def __init__(self, end_time):
        super().__init__(end_time, "Frost Fever")

    def report(self):
        return {
            "frost_fever_uptime": self.uptime(),
        }


class BoneShieldAnalyzer(BuffUptimeAnalyzer):
    def __init__(self, duration, buff_tracker):
        super().__init__(duration, buff_tracker, "Bone Shield")

    def report(self):
        return {"bone_shield_uptime": self.uptime()}


class DesolationAnalyzer(BuffUptimeAnalyzer):
    def __init__(self, duration, buff_tracker):
        super().__init__(duration, buff_tracker, "Desolation")

    def report(self):
        return {"desolation_uptime": self.uptime()}


class GhoulFrenzyAnalyzer(BuffUptimeAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, duration, buff_tracker):
        super().__init__(duration, buff_tracker, "Ghoul Frenzy")

    def report(self):
        return {"ghoul_frenzy_uptime": self.uptime()}


class GargoyleWindow:
    def __init__(self, start, buff_tracker):
        self.start = start
        self.end = start + 30000
        self.snapshotted_greatness = "Greatness" in buff_tracker
        self.snapshotted_fc = "Unholy Strength" in buff_tracker
        self._up_uptime = BuffUptimeAnalyzer(
            self.end, buff_tracker, "Unholy Presence", self.start
        )
        self._bl_uptime = BuffUptimeAnalyzer(
            self.end, buff_tracker, {"Bloodlust", "Heroism"}, self.start
        )
        self.used_hyperspeed = "Hyperspeed Acceleration" in buff_tracker
        self.used_speed_pot = "Speed" in buff_tracker
        self.num_melees = 0
        self.num_casts = 0
        self.total_damage = 0

    @property
    def up_uptime(self):
        return self._up_uptime.uptime()

    @property
    def bl_uptime(self):
        return self._bl_uptime.uptime()

    def add_event(self, event):
        self._up_uptime.add_event(event)

        if event["type"] == "cast" and event["source"] == "Ebon Gargoyle":
            if event["ability"] == "Melee":
                self.num_melees += 1
            if event["ability"] == "Gargoyle Strike":
                self.num_casts += 1

        if event["type"] == "damage" and event["source"] == "Ebon Gargoyle":
            self.total_damage += event["amount"]

        if event["timestamp"] > self.end:
            return

        if event["type"] != "cast":
            return

        if event["ability"] == "Hyperspeed Acceleration":
            self.used_hyperspeed = True

        if event["ability"] == "Speed":
            self.used_speed_pot = True

    def score(self):
        return ScoreWeight.calculate(
            ScoreWeight(int(self.snapshotted_greatness), 2),
            ScoreWeight(int(self.snapshotted_fc), 2),
            # Lower weight since this only lasts 12s
            ScoreWeight(int(self.used_hyperspeed), 2),
            ScoreWeight(self.up_uptime, 4),
            ScoreWeight(self.bl_uptime, 10 if self.bl_uptime else 0),
            ScoreWeight(self.num_casts / max(1, self.num_melees + self.num_casts), 4),
        )


class GargoyleAnalyzer(BaseAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, fight_duration, buff_tracker):
        self._windows: List[GargoyleWindow] = []
        self._window = None
        self._buff_tracker = buff_tracker
        self._fight_duration = fight_duration

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Summon Gargoyle":
            self._window = GargoyleWindow(event["timestamp"], self._buff_tracker)
            self._windows.append(self._window)

        if not self._window:
            return

        self._window.add_event(event)

    @property
    def possible_gargoyles(self):
        return max(1 + (self._fight_duration - 10000) // 183000, len(self._windows))

    def score(self):
        total_score = 0

        for window in self._windows:
            total_score += window.score()

        return total_score / self.possible_gargoyles

    def report(self):
        return {
            "gargoyle": {
                "score": self.score(),
                "num_possible": self.possible_gargoyles,
                "num_actual": len(self._windows),
                "used_speed_potion": any(
                    window.used_speed_pot for window in self._windows
                ),
                "bloodlust_uptime": next(
                    (window.bl_uptime for window in self._windows if window.bl_uptime),
                    0,
                ),
                "average_damage": (
                    sum(window.total_damage for window in self._windows)
                    / len(self._windows)
                    if self._windows
                    else 0
                ),
                "windows": [
                    {
                        "score": window.score(),
                        "damage": window.total_damage,
                        "snapshotted_greatness": window.snapshotted_greatness,
                        "snapshotted_fc": window.snapshotted_fc,
                        "used_hyperspeed": window.used_hyperspeed,
                        "unholy_presence_uptime": window.up_uptime,
                        "used_speed_potion": window.used_speed_pot,
                        "bloodlust_uptime": window.bl_uptime,
                        "num_casts": window.num_casts,
                        "num_melees": window.num_melees,
                    }
                    for window in self._windows
                ],
            }
        }


class DeathAndDecayUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, fight_duration):
        self._dnd_ticks = 0
        self._last_tick_time = None
        self._max_ticks = fight_duration * 10 / 15 // 1000

    def add_event(self, event):
        if event["type"] == "damage" and event["ability"] == "Death and Decay":
            if (
                self._last_tick_time is None
                or event["timestamp"] - self._last_tick_time > 500
            ):
                self._dnd_ticks += 1
            self._last_tick_time = event["timestamp"]

    def uptime(self):
        return self._dnd_ticks / self._max_ticks

    def score(self):
        return self.uptime()

    def report(self):
        return {
            "dnd": {
                "uptime": self.uptime(),
                "score": self.score(),
                "ticks": self._dnd_ticks,
                "max_ticks": self._max_ticks,
            }
        }


class MeleeUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, fight_duration):
        self._fight_duration = fight_duration
        self._windows = []
        self._window = None
        self._last_event_at = None

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Melee":
            if self._window and self._window.end is None:
                if event["timestamp"] - self._last_event_at >= 2500:
                    self._window.end = self._last_event_at
            else:
                self._window = Window(event["timestamp"])
                self._windows.append(self._window)

            self._last_event_at = event["timestamp"]

    def uptime(self):
        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._fight_duration

        return sum(window.duration for window in self._windows) / self._fight_duration

    def score(self):
        return self.uptime()

    def report(self):
        return {
            "melee_uptime": self.uptime(),
        }


class UnholyAnalysisScorer(AnalysisScorer):
    def report(self):
        # Rotation
        gargoyle_analyzer = self.get_analyzer(GargoyleAnalyzer)
        gargoyle_score = ScoreWeight(
            gargoyle_analyzer.score(), 5 * gargoyle_analyzer.possible_gargoyles
        )
        bp_score = ScoreWeight(self.get_analyzer(BloodPlagueAnalyzer).score(), 3)
        ff_score = ScoreWeight(self.get_analyzer(BloodPlagueAnalyzer).score(), 3)
        gf_score = ScoreWeight(self.get_analyzer(GhoulFrenzyAnalyzer).score(), 3)
        desolation_score = ScoreWeight(self.get_analyzer(DesolationAnalyzer).score(), 3)
        dnd_score = ScoreWeight(
            self.get_analyzer(DeathAndDecayUptimeAnalyzer).score(), 6
        )
        bone_shield_score = ScoreWeight(
            self.get_analyzer(BoneShieldAnalyzer).score(), 1
        )
        melee_score = ScoreWeight(self.get_analyzer(MeleeUptimeAnalyzer).score(), 3)
        rp_score = ScoreWeight(self.get_analyzer(RPAnalyzer).score(), 1)

        # Misc
        consume_score = ScoreWeight(self.get_analyzer(BuffTracker).score(), 1)
        bomb_score = ScoreWeight(self.get_analyzer(BombAnalyzer).score(), 1)

        total_score = ScoreWeight.calculate(
            consume_score,
            bomb_score,
            gargoyle_score,
            bp_score,
            ff_score,
            gf_score,
            desolation_score,
            dnd_score,
            bone_shield_score,
            melee_score,
            rp_score,
        )

        return {
            "analysis_scores": {
                "total_score": total_score,
            }
        }


class UnholyAnalysisConfig(CoreAnalysisConfig):
    def get_analyzers(self, fight: Fight, buff_tracker):
        return super().get_analyzers(fight, buff_tracker) + [
            BoneShieldAnalyzer(fight.duration, buff_tracker),
            DesolationAnalyzer(fight.duration, buff_tracker),
            GhoulFrenzyAnalyzer(fight.duration, buff_tracker),
            GargoyleAnalyzer(fight.duration, buff_tracker),
            BloodPlagueAnalyzer(fight.duration),
            FrostFeverAnalyzer(fight.duration),
            DeathAndDecayUptimeAnalyzer(fight.duration),
            MeleeUptimeAnalyzer(fight.duration),
        ]

    def get_scorer(self, analyzers):
        return UnholyAnalysisScorer(analyzers)
