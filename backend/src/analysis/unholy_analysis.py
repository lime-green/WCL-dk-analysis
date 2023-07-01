from collections import defaultdict
from typing import List

from analysis.base import (
    AnalysisScorer,
    BaseAnalyzer,
    ScoreWeight,
    calculate_uptime,
    combine_windows,
    Window,
)
from analysis.core_analysis import (
    BombAnalyzer,
    BuffTracker,
    CoreAnalysisConfig,
    HyperspeedAnalyzer,
    RPAnalyzer,
    MeleeUptimeAnalyzer,
    TrinketAnalyzer,
    BuffUptimeAnalyzer,
    SigilUptimeAnalyzer,
    T9UptimeAnalyzer,
)
from analysis.items import ItemPreprocessor
from report import Fight


class DebuffUptimeAnalyzer(BaseAnalyzer):
    class WindowManager:
        def __init__(self, end_time):
            self._windows_by_target = defaultdict(list)
            self._window_by_target = {}
            self._end_time = end_time

        def add_window(self, target, start, end=None):
            window = Window(start, end)
            self._window_by_target[target] = window
            self._windows_by_target[target].append(window)

        def end_window(self, target, end):
            window = self._window_by_target.get(target)
            if window:
                window.end = end

        def has_active_window(self, target):
            window = self._window_by_target.get(target)
            return window and window.end is None

        def coalesce(self):
            windows = [
                window
                for windows in sorted(self._windows_by_target.values())
                for window in windows
            ]
            if not windows:
                return windows

            for window in windows:
                if window.end is None:
                    window.end = self._end_time

            coalesced_windows = [windows[0].copy()]
            for window in windows[1:]:
                if window.start <= coalesced_windows[-1].end:
                    coalesced_windows[-1].end = window.end
                else:
                    coalesced_windows.append(window.copy())
            return coalesced_windows

    def __init__(self, end_time, debuff_name, ignore_windows):
        self._debuff_name = debuff_name
        self._end_time = end_time
        self._ignore_windows = ignore_windows
        self._wm = self.WindowManager(end_time)

    def add_event(self, event):
        if not event.get("target_is_boss"):
            return

        if event["type"] not in ("applydebuff", "removedebuff", "refreshdebuff"):
            return

        if event["ability"] != self._debuff_name:
            return

        if event["type"] in ("applydebuff", "refreshdebuff"):
            if not self._wm.has_active_window(event["target"]):
                self._wm.add_window(event["target"], event["timestamp"])
        elif event["type"] == "removedebuff":
            self._wm.end_window(event["target"], event["timestamp"])

    def uptime(self):
        windows = self._wm.coalesce()

        return calculate_uptime(
            windows,
            self._ignore_windows,
            self._end_time,
        )

    def score(self):
        return self.uptime()


class BloodPlagueAnalyzer(DebuffUptimeAnalyzer):
    def __init__(self, end_time, ignore_windows):
        super().__init__(end_time, "Blood Plague", ignore_windows)

    def report(self):
        return {
            "blood_plague_uptime": self.uptime(),
        }


class FrostFeverAnalyzer(DebuffUptimeAnalyzer):
    def __init__(self, end_time, ignore_windows):
        super().__init__(end_time, "Frost Fever", ignore_windows)

    def report(self):
        return {
            "frost_fever_uptime": self.uptime(),
        }


class BoneShieldAnalyzer(BuffUptimeAnalyzer):
    def __init__(self, duration, buff_tracker, ignore_windows):
        super().__init__(duration, buff_tracker, ignore_windows, "Bone Shield")

    def report(self):
        return {"bone_shield_uptime": self.uptime()}


class DesolationAnalyzer(BuffUptimeAnalyzer):
    def __init__(self, duration, buff_tracker, ignore_windows):
        super().__init__(duration, buff_tracker, ignore_windows, "Desolation")

    def report(self):
        return {"desolation_uptime": self.uptime()}


class GhoulFrenzyAnalyzer(BuffUptimeAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, duration, buff_tracker, ignore_windows, items):
        self._has_sigil = items.sigil is not None
        super().__init__(duration, buff_tracker, ignore_windows, "Ghoul Frenzy")

    @property
    def max_uptime(self):
        return 0.45 if self._has_sigil else 1

    def score(self):
        return min(1, self.uptime() / self.max_uptime)

    def report(self):
        return {
            "ghoul_frenzy_uptime": self.uptime(),
            "ghoul_frenzy_max_uptime": self.max_uptime,
        }


class UnholyPresenceUptimeAnalyzer(BuffUptimeAnalyzer):
    def __init__(self, duration, buff_tracker, ignore_windows, start_time=0):
        super().__init__(
            duration, buff_tracker, ignore_windows, "Unholy Presence", start_time
        )


class GargoyleWindow(Window):
    def __init__(
        self,
        start,
        fight_duration,
        buff_tracker: BuffTracker,
        ignore_windows,
        items: ItemPreprocessor,
    ):
        self.start = start
        self.end = min(start + 30000, fight_duration)
        self._gargoyle_first_cast = None
        self.snapshotted_greatness = buff_tracker.is_active("Greatness", start)
        self.snapshotted_fc = buff_tracker.is_active("Unholy Strength", start)
        self.snapshotted_sigil = (
            buff_tracker.is_active(items.sigil.buff_name, start)
            if items.sigil
            else None
        )
        self.snapshotted_t9 = (
            buff_tracker.is_active("Unholy Might", start) if items.has_t9_2p() else None
        )

        self._up_uptime = UnholyPresenceUptimeAnalyzer(
            self.end,
            buff_tracker,
            ignore_windows,
            self.start,
        )
        self._bl_uptime = BuffUptimeAnalyzer(
            self.end, buff_tracker, ignore_windows, {"Bloodlust", "Heroism"}, self.start
        )
        self._speed_uptime = BuffUptimeAnalyzer(
            self.end,
            buff_tracker,
            ignore_windows,
            "Speed",
            self.start,
            max_duration=15000 - 25,
        )
        self._hyperspeed_uptime = BuffUptimeAnalyzer(
            self.end,
            buff_tracker,
            ignore_windows,
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
        self.num_melees = 0
        self.num_casts = 0
        self.total_damage = 0
        self._items = items
        self._snapshottable_trinkets = []
        self._uptime_trinkets = []
        self.trinket_snapshots = []
        self.trinket_uptimes = []

        for trinket in self._items.trinkets:
            if trinket.snapshots_gargoyle:
                self._snapshottable_trinkets.append(trinket)
            else:
                self._uptime_trinkets.append(trinket)

        for snapshottable_trinket in self._snapshottable_trinkets:
            self.trinket_snapshots.append(
                {
                    "trinket": snapshottable_trinket,
                    "did_snapshot": buff_tracker.is_active(
                        snapshottable_trinket.buff_name, start
                    ),
                }
            )

        for uptime_trinket in self._uptime_trinkets:
            uptime = BuffUptimeAnalyzer(
                self.end,
                buff_tracker,
                ignore_windows,
                uptime_trinket.buff_name,
                self.start,
                max_duration=uptime_trinket.proc_duration - 25,
            )

            self._uptimes.append(uptime)
            self.trinket_uptimes.append(
                {
                    "trinket": uptime_trinket,
                    "uptime": uptime,
                    "duration": uptime_trinket.proc_duration,
                }
            )

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

    def score(self):
        return ScoreWeight.calculate(
            ScoreWeight(int(self.snapshotted_greatness), 2),
            ScoreWeight(int(self.snapshotted_fc), 3),
            # Lower weight since this only lasts 12s
            ScoreWeight(self.hyperspeed_uptime, 2),
            ScoreWeight(self.up_uptime, 4),
            ScoreWeight(self.bl_uptime, 10 if self.bl_uptime else 0),
            ScoreWeight(self.num_casts / max(1, self.num_melees + self.num_casts), 4),
            ScoreWeight(
                len([t for t in self.trinket_snapshots if t["did_snapshot"]])
                / (len(self.trinket_snapshots) if self.trinket_snapshots else 1),
                len(self.trinket_snapshots) * 2,
            ),
            ScoreWeight(
                sum([t["uptime"].uptime() for t in self.trinket_uptimes])
                / (len(self.trinket_uptimes) if self.trinket_uptimes else 1),
                len(self.trinket_uptimes) * 2,
            ),
            ScoreWeight(
                int(self.snapshotted_sigil)
                if self.snapshotted_sigil is not None
                else 0,
                2 if self.snapshotted_sigil is not None else 0,
            ),
            ScoreWeight(
                int(self.snapshotted_t9) if self.snapshotted_t9 is not None else 0,
                2 if self.snapshotted_t9 is not None else 0,
            ),
        )


class GargoyleAnalyzer(BaseAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, fight_duration, buff_tracker, ignore_windows, items):
        self.windows: List[GargoyleWindow] = []
        self._window = None
        self._buff_tracker = buff_tracker
        self._fight_duration = fight_duration
        self._ignore_windows = ignore_windows
        self._items = items

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Summon Gargoyle":
            self._window = GargoyleWindow(
                event["timestamp"],
                self._fight_duration,
                self._buff_tracker,
                self._ignore_windows,
                self._items,
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
                        "snapshotted_sigil": window.snapshotted_sigil,
                        "snapshotted_t9": window.snapshotted_t9,
                        "sigil_name": self._items.sigil and self._items.sigil.name,
                        "unholy_presence_uptime": window.up_uptime,
                        "bloodlust_uptime": window.bl_uptime,
                        "num_casts": window.num_casts,
                        "num_melees": window.num_melees,
                        "speed_uptime": window.speed_uptime,
                        "hyperspeed_uptime": window.hyperspeed_uptime,
                        "start": window.start,
                        "end": window.end,
                        "trinket_snapshots": [
                            {
                                "name": t["trinket"].name,
                                "did_snapshot": t["did_snapshot"],
                                "icon": t["trinket"].icon,
                            }
                            for t in window.trinket_snapshots
                        ],
                        "trinket_uptimes": [
                            {
                                "name": t["trinket"].name,
                                "uptime": t["uptime"].uptime(),
                                "icon": t["trinket"].icon,
                            }
                            for t in window.trinket_uptimes
                        ],
                    }
                    for window in self.windows
                ],
            }
        }


class DeathAndDecayUptimeAnalyzer(BaseAnalyzer):
    def __init__(self, fight_duration, ignore_windows, items):
        self._dnd_ticks = 0
        self._last_tick_time = None
        self._fight_duration = fight_duration
        self._ignore_windows = ignore_windows
        self._has_sigil = items.sigil is not None

    def _is_in_ignore_window(self, timestamp):
        for window in self._ignore_windows:
            if window.start <= timestamp <= window.end:
                return True
        return False

    def add_event(self, event):
        if event["type"] == "damage" and event["ability"] == "Death and Decay":
            if (
                self._last_tick_time is None
                or event["timestamp"] - self._last_tick_time > 800
            ) and not self._is_in_ignore_window(event["timestamp"]):
                self._dnd_ticks += 1
                self._last_tick_time = event["timestamp"]

    def uptime(self):
        fight_duration = self._fight_duration

        for window in self._ignore_windows:
            fight_duration -= window.duration

        max_ticks = fight_duration * 11 / 15 // 1000
        return min(1, self._dnd_ticks / max_ticks)

    def score(self):
        return min(1, self.uptime() / self.max_uptime)

    @property
    def max_uptime(self):
        return 0.6 if self._has_sigil else 1

    def report(self):
        return {
            "dnd": {
                "max_uptime": self.max_uptime,
                "uptime": self.uptime(),
            }
        }


class GhoulAnalyzer(BaseAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, fight_duration, ignore_windows):
        self._fight_duration = fight_duration
        self._num_claws = 0
        self._num_gnaws = 0
        self._melee_uptime = MeleeUptimeAnalyzer(
            fight_duration,
            ignore_windows,
            event_predicate=self._is_ghoul,
        )
        self._windows = []
        self._window = None
        self.total_damage = 0
        self._ignore_windows = ignore_windows

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

        # Ghoul was already alive
        if not self._windows:
            self._window = Window(0)
            self._windows.append(self._window)

        if event["is_owner_pet_source"]:
            if event["type"] == "cast" and event["ability"] == "Claw":
                self._num_claws += 1
            elif event["type"] == "cast" and event["ability"] == "Gnaw":
                self._num_gnaws += 1
            elif event["type"] == "damage":
                self.total_damage += event["amount"]
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

        return calculate_uptime(
            self._windows,
            self._ignore_windows,
            self._fight_duration,
        )

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
    def __init__(
        self,
        fight_duration,
        buff_tracker: BuffTracker,
        ignore_windows,
        gargoyle_windows,
    ):
        self._buff_tracker = buff_tracker
        self._ignore_windows = ignore_windows
        # Gargoyle windows are modified throughout the fight
        self._gargoyle_windows = gargoyle_windows
        self._fight_duration = fight_duration

    def uptime(self):
        windows = self._buff_tracker.get_windows("Blood Presence")
        ignore_windows = combine_windows(self._ignore_windows, self._gargoyle_windows)
        return calculate_uptime(windows, ignore_windows, self._fight_duration)

    def score(self):
        return self.uptime()

    def report(self):
        return {
            "blood_presence_uptime": self.uptime(),
        }


class SnapshottableBuff:
    def __init__(self, buffs, display_name):
        if isinstance(buffs, str):
            buffs = {buffs}

        self.buffs = buffs
        self.display_name = display_name

    def is_active(self, buff_tracker: BuffTracker, timestamp):
        return any(buff_tracker.is_active(buff, timestamp) for buff in self.buffs)


class ArmyAnalyzer(BaseAnalyzer):
    INCLUDE_PET_EVENTS = True

    def __init__(self, buff_tracker: BuffTracker, items: ItemPreprocessor):
        self._buff_tracker = buff_tracker
        self.total_damage = 0
        self._snapshots = []
        self._snapshottable_trinkets = [
            trinket for trinket in items.trinkets if trinket.snapshots_army_haste
        ]
        self._snapshottable_buffs = [
            SnapshottableBuff({"Bloodlust", "Heroism"}, "Bloodlust"),
            SnapshottableBuff("Hyperspeed Acceleration", "Hyperspeed"),
            SnapshottableBuff("Speed", "Speed"),
        ]

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Army of the Dead":
            for trinket in self._snapshottable_trinkets:
                did_snapshot = self._buff_tracker.is_active(
                    trinket.buff_name, event["timestamp"]
                )
                self._snapshots.append(
                    {
                        "name": trinket.name,
                        "did_snapshot": did_snapshot,
                        "icon": trinket.icon,
                    }
                )
            for buff in self._snapshottable_buffs:
                self._snapshots.append(
                    {
                        "name": buff.display_name,
                        "did_snapshot": buff.is_active(
                            self._buff_tracker, event["timestamp"]
                        ),
                    }
                )

        if event["type"] == "damage" and event["source"] == "Army of the Dead":
            self.total_damage += event["amount"]

    def report(self):
        return {
            "army": {
                "damage": self.total_damage,
                "snapshots": self._snapshots,
            }
        }

    def score(self):
        if not self._snapshots:
            return 0

        return sum(snapshot["did_snapshot"] for snapshot in self._snapshots) / len(
            self._snapshots
        )


class BloodTapAnalyzer(BaseAnalyzer):
    def __init__(self, fight_end_time):
        self._num_used = 0
        self._fight_end_time = fight_end_time

    @property
    def max_usages(self):
        return max(1 + (self._fight_end_time - 10000) // 60000, self._num_used)

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Blood Tap":
            self._num_used += 1

    def score(self):
        return self._num_used / self.max_usages

    def report(self):
        return {
            "blood_tap_usages": self._num_used,
            "blood_tap_max_usages": self.max_usages,
        }


class UnholyAnalysisScorer(AnalysisScorer):
    def get_score_weights(self):
        exponent_factor = 1.5

        return {
            GargoyleAnalyzer: {
                "weight": lambda ga: 5 * ga.possible_gargoyles,
                "exponent_factor": exponent_factor,
            },
            BloodPlagueAnalyzer: {
                "weight": 3,
                "exponent_factor": exponent_factor,
            },
            FrostFeverAnalyzer: {
                "weight": 3,
                "exponent_factor": exponent_factor,
            },
            GhoulFrenzyAnalyzer: {
                "weight": 3,
                "exponent_factor": exponent_factor,
            },
            DesolationAnalyzer: {
                "weight": 3,
                "exponent_factor": exponent_factor,
            },
            DeathAndDecayUptimeAnalyzer: {
                "weight": 6,
                "exponent_factor": exponent_factor,
            },
            BoneShieldAnalyzer: {
                "weight": 1,
                "exponent_factor": exponent_factor,
            },
            MeleeUptimeAnalyzer: {
                "weight": 6,
                "exponent_factor": exponent_factor,
            },
            RPAnalyzer: {
                "weight": 1,
            },
            BloodPresenceUptimeAnalyzer: {
                "weight": 3,
                "exponent_factor": exponent_factor,
            },
            GhoulAnalyzer: {
                "weight": 5,
                "exponent_factor": exponent_factor,
            },
            BuffTracker: {
                "weight": 1,
            },
            BombAnalyzer: {
                "weight": 1,
            },
            HyperspeedAnalyzer: {
                "weight": 2,
            },
            TrinketAnalyzer: {
                "weight": lambda ta: ta.num_on_use_trinkets * 2,
            },
            ArmyAnalyzer: {
                "weight": 3,
            },
            T9UptimeAnalyzer: {
                "weight": lambda t9a: t9a.score_weight(),
            },
            SigilUptimeAnalyzer: {
                "weight": lambda sa: sa.score_weight(),
            },
            BloodTapAnalyzer: {
                "weight": 1,
            },
        }

    def report(self):
        return {
            "analysis_scores": {
                "total_score": self.score(),
            }
        }


class UnholyAnalysisConfig(CoreAnalysisConfig):
    def get_analyzers(self, fight: Fight, buff_tracker, dead_zone_analyzer, items):
        dead_zones = dead_zone_analyzer.get_dead_zones()
        gargoyle = GargoyleAnalyzer(fight.duration, buff_tracker, dead_zones, items)

        return super().get_analyzers(fight, buff_tracker, dead_zone_analyzer, items) + [
            BoneShieldAnalyzer(fight.duration, buff_tracker, dead_zones),
            DesolationAnalyzer(fight.duration, buff_tracker, dead_zones),
            GhoulFrenzyAnalyzer(fight.duration, buff_tracker, dead_zones, items),
            gargoyle,
            BloodPlagueAnalyzer(fight.duration, dead_zones),
            FrostFeverAnalyzer(fight.duration, dead_zones),
            DeathAndDecayUptimeAnalyzer(fight.duration, dead_zones, items),
            GhoulAnalyzer(fight.duration, dead_zones),
            BloodPresenceUptimeAnalyzer(
                fight.duration, buff_tracker, dead_zones, gargoyle.windows
            ),
            ArmyAnalyzer(buff_tracker, items),
            BloodTapAnalyzer(fight.end_time),
        ]

    def get_scorer(self, analyzers):
        return UnholyAnalysisScorer(analyzers)
