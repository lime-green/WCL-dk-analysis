from analysis.base import AnalysisScorer, BaseAnalyzer, ScoreWeight
from analysis.core_analysis import (
    BombAnalyzer,
    BuffTracker,
    CoreAnalysisConfig,
    DiseaseAnalyzer,
    GCDAnalyzer,
    HyperspeedAnalyzer,
    MeleeUptimeAnalyzer,
    RuneTracker,
)
from console_table import console
from report import Fight


class KMAnalyzer(BaseAnalyzer):
    class Window:
        def __init__(self, timestamp):
            self.gained_timestamp = timestamp
            self.used_timestamp = None

    def __init__(self):
        self._windows = []
        self._window = None

    def add_event(self, event):
        if event.get("ability") != "Killing Machine":
            return

        if event["type"] in ("refreshbuff", "applybuff"):
            self._window = self.Window(event["timestamp"])
            self._windows.append(self._window)
        # Could have no window if a previous KM proc was carried over
        if event["type"] == "removebuff" and self._window:
            if event["timestamp"] - self._window.gained_timestamp < 30000:
                self._window.used_timestamp = event["timestamp"]
            self._window = None

    def print(self):
        report = self.report()["killing_machine"]

        if report["num_total"]:
            console.print(
                f"* You used {report['num_used']} of {report['num_total']} Killing Machine procs"
            )
            console.print(
                f"* Your average Killing Machine proc usage delay was {report['avg_latency']:.2f} ms"
            )
        else:
            console.print("* You did not use any Killing Machine procs")

    def get_data(self):
        used_windows = [window for window in self._windows if window.used_timestamp]
        num_windows = len(self._windows)
        num_used = len(used_windows)
        latencies = [
            window.used_timestamp - window.gained_timestamp for window in used_windows
        ]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        return num_used, num_windows, avg_latency

    def score(self):
        num_used, num_windows, avg_latency = self.get_data()
        if avg_latency < 1800:
            return 1
        if avg_latency < 1900:
            return 0.9
        if avg_latency < 2000:
            return 0.8
        if avg_latency < 2100:
            return 0.7
        if avg_latency < 2200:
            return 0.6
        if avg_latency < 2300:
            return 0.5
        if avg_latency < 2500:
            return 0.4
        if avg_latency < 3000:
            return 0.2
        return 0

    def report(self):
        num_used, num_windows, avg_latency = self.get_data()
        return {
            "killing_machine": {
                "num_used": num_used,
                "num_total": num_windows,
                "avg_latency": avg_latency,
            },
        }


class UAAnalyzer(BaseAnalyzer):
    class Window:
        def __init__(self, expected_oblits, with_erw=False):
            self.oblits = 0
            self.expected_oblits = expected_oblits
            self.with_erw = with_erw

        @property
        def num_expected(self):
            return max(self.expected_oblits, self.oblits)

        @property
        def num_actual(self):
            return self.oblits

        def __str__(self):
            s = (
                "[green]✓[/green] "
                if self.oblits == self.num_expected
                else "[red]x[/red] "
            )
            s += f"Hit {self.oblits} of {self.num_expected} obliterates"
            if self.with_erw:
                s += " (with ERW)"
            return s

    def __init__(self, fight_end_time):
        self._window = None
        self._windows = []
        self._fight_end_time = fight_end_time

    def _get_expected_oblits(self, ua_start_time):
        time_left = self._fight_end_time - ua_start_time

        if time_left >= 16000:
            return 5
        if time_left >= 14500:
            return 4
        if time_left >= 10500:
            return 3
        if time_left >= 5000:
            return 2
        if time_left >= 2500:
            return 1
        return 0

    def add_event(self, event):
        if event["type"] == "applybuff" and event["ability"] == "Unbreakable Armor":
            expected_oblits = self._get_expected_oblits(event["timestamp"])
            self._window = self.Window(expected_oblits)
            self._windows.append(self._window)
        elif event["type"] == "removebuff" and event["ability"] == "Unbreakable Armor":
            self._window = None
        elif self._window and not event.get("is_miss"):
            if event["type"] == "cast" and event["ability"] == "Empower Rune Weapon":
                self._window.expected_oblits = 6
                self._window.with_erw = True
            if (
                event["type"] == "cast"
                and (
                    event["ability"] == "Obliterate"
                    or (
                        event["ability"] == "Howling Blast"
                        and not event.get("consumes_rime")
                    )
                )
                and not event["is_miss"]
            ):
                self._window.oblits += 1

    @property
    def possible_ua_windows(self):
        return max(1 + (self._fight_end_time - 10000) // 63000, len(self._windows))

    @property
    def num_possible(self):
        if self._windows and not self._windows[-1].num_expected:
            return max(self.num_actual, self.possible_ua_windows - 1)
        return max(self.num_actual, self.possible_ua_windows)

    @property
    def num_actual(self):
        return len(self._windows)

    def get_data(self):
        return (
            self.num_possible,
            self.num_actual,
            [
                (
                    window.with_erw,
                    window.num_actual,
                    window.num_expected,
                )
                for window in self._windows
            ],
        )

    def print(self):
        color = (
            "[green]✓[/green]"
            if self.possible_ua_windows == len(self._windows)
            else "[red]x[/red]"
        )
        console.print(
            f"{color} You used UA {len(self._windows)}"
            f" out of a possible {self.possible_ua_windows} times"
        )

        for window in self._windows:
            console.print(f"\t - {window}")

    def score(self):
        total_weight = 0
        score = 0

        for window in self._windows:
            num_expected = window.num_expected
            if num_expected:
                score += num_expected * (window.num_actual / num_expected) ** 2
                total_weight += num_expected

        # account for unused UAs
        for i in range(0, self.possible_ua_windows - len(self._windows)):
            # account for unused last UA
            if i == 0:
                possible_ua_start = (self.possible_ua_windows - 1) * 63000
                num_expected = self._get_expected_oblits(possible_ua_start)
                total_weight += num_expected
            # account for all other unused mid-fight UAs
            else:
                total_weight += 5

        if total_weight:
            return score / total_weight
        else:
            return 1

    def report(self):
        num_possible, num_actual, windows = self.get_data()

        return {
            "unbreakable_armor": {
                "num_possible": num_possible,
                "num_actual": num_actual,
                "windows": [
                    {
                        "with_erw": with_erw,
                        "num_actual": w_num_actual,
                        "num_possible": w_num_possible,
                    }
                    for with_erw, w_num_actual, w_num_possible in windows
                ],
            }
        }


class HowlingBlastAnalyzer(BaseAnalyzer):
    def __init__(self):
        self._bad_usages = 0

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Howling Blast":
            if event["num_targets"] >= 3 or event["consumes_rime"]:
                is_bad = False
            elif event["num_targets"] == 2 and event["consumes_km"]:
                is_bad = False
            else:
                is_bad = True

            event["bad_howling_blast"] = is_bad
            if is_bad:
                self._bad_usages += 1

    def print(self):
        if self._bad_usages:
            console.print(
                "[red]x[/red] You used Howling Blast without Rime"
                f" on less than 3 targets {self._bad_usages} times"
            )
        else:
            console.print(
                "[green]✓[/green] You always used Howling Blast with rime or on 3+ targets"
            )

    def score(self):
        if self._bad_usages == 0:
            return 1
        if self._bad_usages == 1:
            return 0.5
        return 0

    def report(self):
        return {
            "howling_blast_bad_usages": {
                "num_bad_usages": self._bad_usages,
            }
        }


class RimeAnalyzer(BaseAnalyzer):
    def __init__(self, buff_tracker: BuffTracker):
        self._num_total = 1 if buff_tracker.is_active("Rime", 0) else 0
        self._num_used = 0

    def add_event(self, event):
        if event["type"] in ("applybuff", "refreshbuff") and event["ability"] == "Rime":
            self._num_total += 1
        if event.get("consumes_rime"):
            self._num_used += 1

    def score(self):
        # bug with Razorscale, can start with rime
        total = max(self._num_total, self._num_used)

        if not total:
            return 0
        return 1 * (self._num_used / total)

    def report(self):
        return {
            "rime": {
                "num_total": self._num_total,
                "num_used": self._num_used,
            }
        }


class RaiseDeadAnalyzer(BaseAnalyzer):
    def __init__(self, fight_end_time):
        self._num_raise_deads = 0
        self._fight_end_time = fight_end_time

    @property
    def possible_raise_deads(self):
        return max(1 + (self._fight_end_time - 20000) // 183000, self._num_raise_deads)

    def add_event(self, event):
        if event["type"] == "cast" and event["ability"] == "Raise Dead":
            self._num_raise_deads += 1

    def score(self):
        return self._num_raise_deads / self.possible_raise_deads

    def report(self):
        return {
            "raise_dead_usage": {
                "num_usages": self._num_raise_deads,
                "possible_usages": self.possible_raise_deads,
            }
        }


class FrostAnalysisScorer(AnalysisScorer):
    def report(self):
        # Speed
        gcd_score = ScoreWeight(self.get_analyzer(GCDAnalyzer).score(), 3)
        drift_score = ScoreWeight(self.get_analyzer(RuneTracker).score(), 3)
        km_score = ScoreWeight(self.get_analyzer(KMAnalyzer).score(), 1)

        # Rotation
        ua_analyzer = self.get_analyzer(UAAnalyzer)
        ua_score = ScoreWeight(ua_analyzer.score(), ua_analyzer.num_possible)
        disease_score = ScoreWeight(self.get_analyzer(DiseaseAnalyzer).score(), 2)
        hb_score = ScoreWeight(self.get_analyzer(HowlingBlastAnalyzer).score(), 0.5)
        rime_score = ScoreWeight(self.get_analyzer(RimeAnalyzer).score(), 0.5)
        raise_dead = self.get_analyzer(RaiseDeadAnalyzer)
        raise_dead_score = ScoreWeight(
            raise_dead.score(), raise_dead.possible_raise_deads
        )
        melee_score = ScoreWeight(
            self.get_analyzer(MeleeUptimeAnalyzer).score() ** 1.5, 4
        )

        # Misc
        consume_score = ScoreWeight(self.get_analyzer(BuffTracker).score(), 1)
        bomb_score = ScoreWeight(self.get_analyzer(BombAnalyzer).score(), 2)
        hyperspeed_score = ScoreWeight(self.get_analyzer(HyperspeedAnalyzer).score(), 1)

        total_score = ScoreWeight.calculate(
            gcd_score,
            drift_score,
            km_score,
            ua_score,
            disease_score,
            hb_score,
            rime_score,
            consume_score,
            raise_dead_score,
            bomb_score,
            hyperspeed_score,
            melee_score,
        )

        return {
            "analysis_scores": {
                "total_score": total_score,
            }
        }


class FrostAnalysisConfig(CoreAnalysisConfig):
    show_procs = True
    show_speed = True

    def get_analyzers(self, fight: Fight, buff_tracker):
        return super().get_analyzers(fight, buff_tracker) + [
            DiseaseAnalyzer(fight.encounter.name, fight.duration),
            KMAnalyzer(),
            UAAnalyzer(fight.duration),
            HowlingBlastAnalyzer(),
            RimeAnalyzer(buff_tracker),
            RaiseDeadAnalyzer(fight.duration),
        ]

    def get_scorer(self, analyzers):
        return FrostAnalysisScorer(analyzers)

    def create_rune_tracker(self):
        return RuneTracker(
            should_convert_blood=True,
            track_drift_type={"Frost", "Unholy"},
        )
