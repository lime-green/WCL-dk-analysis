from typing import List

from analysis.base import (
    AnalysisScorer,
    BaseAnalyzer,
    ScoreWeight,
    range_overlap,
    Window,
)
from analysis.core_analysis import (
    BombAnalyzer,
    BuffTracker,
    CoreAnalysisConfig,
    GCDAnalyzer,
    HyperspeedAnalyzer,
    RPAnalyzer,
    MeleeUptimeAnalyzer,
)
from report import Fight


class BuffUptimeAnalyzer(BaseAnalyzer):
    def __init__(
        self, end_time, buff_tracker, buff_names, start_time=0, max_duration=None
    ):
        self._start_time = start_time
        self._end_time = end_time
        self._windows = []
        self._window = None
        self._max_duration = max_duration

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

    def set_start_time(self, start):
        self._start_time = start

    def add_event(self, event):
        if event["type"] not in (
            "applybuff",
            "removebuff",
            "removebuffstack",
            "refreshbuff",
        ):
            return

        if event["ability"] not in self._buff_names:
            return

        if (
            event["type"] in ("removebuffstack", "refreshbuff")
            and event["timestamp"] <= self._end_time
        ):
            # If we don't have a window, assume it was a starting aura
            if not self._windows:
                self._add_window(self._start_time)
        elif event["type"] == "applybuff" and event["timestamp"] <= self._end_time:
            if not self._window or self._window.end is not None:
                self._add_window(event["timestamp"])
        elif event["type"] == "removebuff":
            end = min(event["timestamp"], self._end_time)
            if self._window and not self._window.end:
                self._window.end = end
            elif not self._windows:  # assume it was a starting aura
                self._add_window(self._start_time, end)

    def uptime(self):
        uptime_duration = 0

        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._end_time

        for window in self._windows:
            # If the window is entirely outside the range, ignore it
            if range_overlap(
                (window.start, window.end), (self._start_time, self._end_time)
            ):
                uptime_duration += min(window.end, self._end_time) - max(
                    window.start, self._start_time
                )

        total_duration = self._end_time - self._start_time
        if self._max_duration:
            total_duration = min(total_duration, self._max_duration)
        return min(1, uptime_duration / total_duration)

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
        elif event["type"] == "removedebuff" and self._window:
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


class UnholyPresenceUptimeAnalyzer(BuffUptimeAnalyzer):
    def __init__(self, duration, buff_tracker, start_time=0):
        super().__init__(duration, buff_tracker, "Unholy Presence", start_time)
        self._last_ability_at = None

    def add_event(self, event):
        super().add_event(event)

        if (
            not self._windows
            and self._last_ability_at
            and event["type"] == "cast"
            and event["ability"] not in GCDAnalyzer.NO_GCD
            and not event["is_owner_pet_source"]
            and not event["is_owner_pet_target"]
            and event["timestamp"] - self._last_ability_at < 1250
        ):
            self._add_window(self._start_time)
        elif event["type"] == "cast" and event["ability"] in (
            "Blood Strike",
            "Plague Strike",
        ):
            self._last_ability_at = event["timestamp"]


class GargoyleWindow(Window):
    def __init__(self, start, fight_duration, buff_tracker):
        self.start = start
        self.end = min(start + 30000, fight_duration)
        self._gargoyle_first_cast = None
        self.snapshotted_greatness = "Greatness" in buff_tracker
        self.snapshotted_fc = "Unholy Strength" in buff_tracker
        self._up_uptime = UnholyPresenceUptimeAnalyzer(
            self.end, buff_tracker, self.start
        )
        self._bl_uptime = BuffUptimeAnalyzer(
            self.end, buff_tracker, {"Bloodlust", "Heroism"}, self.start
        )
        self._speed_uptime = BuffUptimeAnalyzer(
            self.end, buff_tracker, "Speed", self.start, max_duration=15000 - 25
        )
        self._hyperspeed_uptime = BuffUptimeAnalyzer(
            self.end,
            buff_tracker,
            "Hyperspeed Acceleration",
            self.start,
            max_duration=12000 - 25,
        )
        self._uptimes = [
            self._up_uptime,
            self._bl_uptime,
            self._speed_uptime,
            self._hyperspeed_uptime,
        ]
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

    @property
    def speed_uptime(self):
        return self._speed_uptime.uptime()

    @property
    def hyperspeed_uptime(self):
        return self._hyperspeed_uptime.uptime()

    def _set_gargoyle_first_cast(self, event):
        self._gargoyle_first_cast = event["timestamp"]
        for uptime in self._uptimes:
            uptime.set_start_time(event["timestamp"])

    def add_event(self, event):
        for uptime in self._uptimes:
            uptime.add_event(event)

        if event["source"] == "Ebon Gargoyle":
            if (
                event["type"] in ("cast", "startcast")
                and self._gargoyle_first_cast is None
            ):
                self._set_gargoyle_first_cast(event)
            if event["type"] == "cast":
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
            ScoreWeight(self.hyperspeed_uptime, 2),
            ScoreWeight(self.up_uptime, 4),
            ScoreWeight(self.bl_uptime, 10 if self.bl_uptime else 0),
            ScoreWeight(self.num_casts / max(1, self.num_melees + self.num_casts), 4),
        )


class GargoyleAnalyzer(BaseAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, fight_duration, buff_tracker):
        self.windows: List[GargoyleWindow] = []
        self._window = None
        self._buff_tracker = buff_tracker
        self._fight_duration = fight_duration

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Summon Gargoyle":
            self._window = GargoyleWindow(
                event["timestamp"], self._fight_duration, self._buff_tracker
            )
            self.windows.append(self._window)

        if not self._window:
            return

        self._window.add_event(event)

    @property
    def possible_gargoyles(self):
        return max(1 + (self._fight_duration - 10000) // 183000, len(self.windows))

    def score(self):
        window_score = sum(window.score() for window in self.windows)
        used_speed = any(window.speed_uptime for window in self.windows)
        return ScoreWeight.calculate(
            ScoreWeight(int(used_speed), 1),
            ScoreWeight(
                window_score / self.possible_gargoyles, 5 * self.possible_gargoyles
            ),
        )

    def report(self):
        return {
            "gargoyle": {
                "score": self.score(),
                "num_possible": self.possible_gargoyles,
                "num_actual": len(self.windows),
                "used_speed_potion": any(
                    window.used_speed_pot for window in self.windows
                ),
                "bloodlust_uptime": next(
                    (window.bl_uptime for window in self.windows if window.bl_uptime),
                    0,
                ),
                "average_damage": (
                    sum(window.total_damage for window in self.windows)
                    / len(self.windows)
                    if self.windows
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
                        "speed_uptime": window.speed_uptime,
                        "hyperspeed_uptime": window.hyperspeed_uptime,
                        "start": window.start,
                        "end": window.end,
                    }
                    for window in self.windows
                ],
            }
        }


class DeathAndDecayUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, fight_duration):
        self._dnd_ticks = 0
        self._last_tick_time = None
        self._max_ticks = fight_duration * 11 / 15 // 1000

    def add_event(self, event):
        if event["type"] == "damage" and event["ability"] == "Death and Decay":
            if (
                self._last_tick_time is None
                or event["timestamp"] - self._last_tick_time > 800
            ):
                self._dnd_ticks += 1
                self._last_tick_time = event["timestamp"]

    def uptime(self):
        return min(1, self._dnd_ticks / self._max_ticks)

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


class GhoulAnalyzer(BaseAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, fight_duration):
        self._fight_duration = fight_duration
        self._num_claws = 0
        self._num_gnaws = 0
        self._melee_uptime = MeleeUptimeAnalyzer(
            fight_duration, event_predicate=self._is_ghoul
        )
        self._windows = []
        self._window = None
        self.total_damage = 0

    def _is_ghoul(self, event):
        if not event["is_owner_pet_source"] and not event["is_owner_pet_target"]:
            return False

        if event["source"] in ("Army of the Dead", "Ebon Gargoyle") or event[
            "target"
        ] in ("Army of the Dead", "Ebon Gargoyle"):
            return False

        return True

    def add_event(self, event):
        # Should be called at the top so we can update the window
        self._melee_uptime.add_event(event)

        # Ghoul was revived
        if event["type"] == "cast" and event["ability"] == "Raise Dead":
            # It seems this can happen if the ghoul is dismissed
            if self._window and self._window.end is None:
                self._window.end = event["timestamp"]
            self._window = Window(event["timestamp"])
            self._windows.append(self._window)
            return

        if not self._is_ghoul(event):
            return

        if event["type"] == "damage":
            self.total_damage += event["amount"]

        # Ghoul was already alive
        if not self._windows:
            self._window = Window(0)
            self._windows.append(self._window)

        if event["is_owner_pet_source"]:
            if event["type"] == "cast" and event["ability"] == "Claw":
                self._num_claws += 1
            elif event["type"] == "cast" and event["ability"] == "Gnaw":
                self._num_gnaws += 1
        elif event["is_owner_pet_target"]:
            # Ghoul has died
            if event["type"] == "damage" and event.get("overkill"):
                self._window.end = event["timestamp"]

    @property
    def melee_uptime(self):
        return self._melee_uptime.uptime()

    def uptime(self):
        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._fight_duration

        return sum(window.duration for window in self._windows) / self._fight_duration

    def score(self):
        return ScoreWeight.calculate(
            ScoreWeight(min(1, self.claw_cpm / 15), 4),
            ScoreWeight(self.melee_uptime, 10),
            ScoreWeight(0 if self._num_gnaws else 1, 1),
        )

    @property
    def claw_cpm(self):
        return self._num_claws / (self._fight_duration / 1000 / 60)

    def report(self):
        return {
            "ghoul": {
                "score": self.score(),
                "num_claws": self._num_claws,
                "num_gnaws": self._num_gnaws,
                "melee_uptime": self._melee_uptime.uptime(),
                "uptime": self.uptime(),
                "claw_cpm": self.claw_cpm,
                "claw_cpm_possible": 15,
                "damage": self.total_damage,
            }
        }


class BloodPresenceUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, fight_duration, ignore_windows):
        self._windows = []
        self._window = None
        self._fight_duration = fight_duration
        self._ignore_windows = ignore_windows

    def _add_window(self, start):
        self._window = Window(start)
        self._windows.append(self._window)

    def add_event(self, event):
        if not self._windows:
            if (
                event["type"] in ("heal", "removebuff")
                and event["ability"] == "Blood Presence"
            ):
                self._add_window(0)
            elif event["type"] == "removebuff" and event["ability"] == "Blood Presence":
                self._add_window(0)
                self._window.end = event["timestamp"]
        elif event["type"] == "removebuff" and event["ability"] == "Blood Presence":
            self._window.end = event["timestamp"]
        elif event["type"] == "applybuff" and event["ability"] == "Blood Presence":
            self._add_window(event["timestamp"])

    def uptime(self):
        if self._windows and self._windows[-1].end is None:
            self._windows[-1].end = self._fight_duration

        total_uptime = sum(window.duration for window in self._windows)
        ignore_index = 0

        for window in self._windows:
            while ignore_index < len(self._ignore_windows) and not window.intersects(
                self._ignore_windows[ignore_index]
            ):
                ignore_index += 1

            while ignore_index < len(self._ignore_windows) and window.intersects(
                self._ignore_windows[ignore_index]
            ):
                intersection = window.intersection(self._ignore_windows[ignore_index])
                total_uptime -= intersection.duration
                ignore_index += 1

            # in case we have an ignore window that overlaps with multiple windows
            if ignore_index:
                ignore_index -= 1

        total_duration_without_ignores = self._fight_duration - sum(
            window.duration for window in self._ignore_windows
        )
        return total_uptime / total_duration_without_ignores

    def score(self):
        return self.uptime()

    def report(self):
        return {
            "blood_presence_uptime": self.uptime(),
        }


class UnholyAnalysisScorer(AnalysisScorer):
    def score(self):
        # Rotation
        gargoyle_analyzer = self.get_analyzer(GargoyleAnalyzer)
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
        blood_presence_score = ScoreWeight(
            self.get_analyzer(BloodPresenceUptimeAnalyzer).score(), 3
        )

        # Gargoyle
        gargoyle_score = ScoreWeight(
            gargoyle_analyzer.score(), 5 * gargoyle_analyzer.possible_gargoyles
        )

        # Ghoul
        ghoul_score = ScoreWeight(self.get_analyzer(GhoulAnalyzer).score(), 5)

        # Misc
        consume_score = ScoreWeight(self.get_analyzer(BuffTracker).score(), 1)
        bomb_score = ScoreWeight(self.get_analyzer(BombAnalyzer).score(), 1)
        hyperspeed_score = ScoreWeight(self.get_analyzer(HyperspeedAnalyzer).score(), 1)

        return ScoreWeight.calculate(
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
            hyperspeed_score,
            ghoul_score,
            blood_presence_score,
        )

    def report(self):
        return {
            "analysis_scores": {
                "total_score": self.score(),
            }
        }


class UnholyAnalysisConfig(CoreAnalysisConfig):
    def get_analyzers(self, fight: Fight, buff_tracker):
        gargoyle = GargoyleAnalyzer(fight.duration, buff_tracker)

        return super().get_analyzers(fight, buff_tracker) + [
            BoneShieldAnalyzer(fight.duration, buff_tracker),
            DesolationAnalyzer(fight.duration, buff_tracker),
            GhoulFrenzyAnalyzer(fight.duration, buff_tracker),
            gargoyle,
            BloodPlagueAnalyzer(fight.duration),
            FrostFeverAnalyzer(fight.duration),
            DeathAndDecayUptimeAnalyzer(fight.duration),
            MeleeUptimeAnalyzer(fight.duration),
            GhoulAnalyzer(fight.duration),
            BloodPresenceUptimeAnalyzer(fight.duration, gargoyle.windows),
        ]

    def get_scorer(self, analyzers):
        return UnholyAnalysisScorer(analyzers)
