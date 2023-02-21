from typing import Optional, TypeVar, Type

from console_table import console, EventsTable, SHOULD_PRINT
from report import Fight, Report

R = TypeVar("R")


class BaseAnalyzer:
    def add_event(self, event):
        pass

    def print(self):
        pass

    def report(self):
        return {}


class DeadZoneAnalyzer(BaseAnalyzer):
    MELEE_ABILITIES = {
        "Melee",
        "Obliterate",
        "Frost Strike",
        "Blood Strike",
    }

    class DeadZone:
        def __init__(self, last_event, curr_event):
            self._last_event = last_event
            self._curr_event = curr_event
            self.start = last_event["timestamp"] + 1
            self.end = curr_event["timestamp"]

        def __contains__(self, item):
            return self.start <= item <= self.end

    def __init__(self, fight: Fight):
        self._fight = fight
        self._dead_zones = []
        self._last_event = None
        self._checker = {
            "Loatheb": self._check_loatheb,
            "Thaddius": self._check_thaddius,
            "Maexxna": self._check_maexxna,
            "Kel'Thuzad": self._check_kelthuzad,
            "Ignis the Furnace Master": self._check_ignis,
            "Razorscale": self._check_razorscale,
        }.get(self._fight.encounter.name)
        self._encounter_name = self._fight.encounter.name

    def _check_ignis(self, event):
        if event["type"] not in ("removedebuff", "applydebuff"):
            return

        if event["ability"] != "Slag Pot":
            return

        if event["type"] == "applydebuff":
            self._last_event = event
        elif event["type"] == "removedebuff":
            dead_zone = self.DeadZone(self._last_event, event)
            self._dead_zones.append(dead_zone)

    def _check_kelthuzad(self, event):
        if event["type"] not in ("removedebuff", "applydebuff"):
            return

        if event["ability"] != "Frost Blast":
            return

        if event["type"] == "applydebuff":
            self._last_event = event
        elif event["type"] == "removedebuff":
            dead_zone = self.DeadZone(self._last_event, event)
            self._dead_zones.append(dead_zone)

    def _check_maexxna(self, event):
        if event["type"] not in ("removedebuff", "applydebuff"):
            return

        if event["ability"] != "Web Spray":
            return

        if event["type"] == "applydebuff":
            self._last_event = event
        elif event["type"] == "removedebuff":
            dead_zone = self.DeadZone(self._last_event, event)
            self._dead_zones.append(dead_zone)

    def _check_thaddius(self, event):
        if event["type"] not in ("cast", "damage"):
            return

        if event.get("target") not in ("Thaddius", "Stalagg", "Feugen"):
            return

        if event["source"] != self._fight.source.name:
            return

        if self._last_event and self._last_event["target"] != event["target"]:
            dead_zone = self.DeadZone(self._last_event, event)
            self._dead_zones.append(dead_zone)

        self._last_event = event

    def _check_razorscale(self, event):
        if event.get("target") != "Razorscale":
            return

        if event["type"] != "cast" or event["ability"] not in self.MELEE_ABILITIES:
            return

        if event["source"] != self._fight.source.name:
            return

        if (
            self._last_event
            and event["timestamp"] - self._last_event["timestamp"] > 5000
        ):
            dead_zone = self.DeadZone(self._last_event, event)
            self._dead_zones.append(dead_zone)

        self._last_event = event

    def _check_loatheb(self, event):
        if event.get("target") != "Loatheb":
            return

        if event["type"] != "cast" or event["ability"] not in self.MELEE_ABILITIES:
            return

        if event["source"] != self._fight.source.name:
            return

        if (
            self._last_event
            and event["timestamp"] - self._last_event["timestamp"] > 2000
        ):
            dead_zone = self.DeadZone(self._last_event, event)
            self._dead_zones.append(dead_zone)

        self._last_event = event

    def add_event(self, event):
        if not self._checker:
            return

        return self._checker(event)

    def get_recent_dead_zone(self, end) -> Optional[DeadZone]:
        for dead_zone in reversed(self._dead_zones):
            # returns the closest dead-zone
            if dead_zone.start <= end:
                return dead_zone
        return None

    def decorate_event(self, event):
        dead_zone = self.get_recent_dead_zone(event["timestamp"])
        event["in_dead_zone"] = dead_zone and event["timestamp"] in dead_zone
        event["recent_dead_zone"] = dead_zone and (dead_zone.start, dead_zone.end)


class Rune:
    RUNE_GRACE = 2471

    def __init__(self, full_name, type):
        self.full_name = full_name
        self.type = type
        self.regen_time = None
        # Flag for death rune (when converted normally)
        self.is_death = False
        # Blood Tap is tracked as separate attribute since a blood-tapped
        # death rune doesn't convert back to blood when used
        # like a normal death rune does
        self.blood_tapped = False

    def can_spend(self, timestamp: int):
        if self.regen_time is None:
            return True
        return timestamp >= self.regen_time

    def can_spend_death(self, timestamp: int):
        return (self.is_death or self.blood_tapped) and self.can_spend(timestamp)

    def _rune_grace_used(self, timestamp):
        return min(self.RUNE_GRACE, self.time_since_regen(timestamp))

    def refresh(self, timestamp):
        self.regen_time = timestamp

    def spend(self, timestamp: int, convert: bool):
        if not self.can_spend(timestamp):
            return False, 0

        rune_grace_used = self._rune_grace_used(timestamp)
        rune_grace_wasted = max(0, self.time_since_regen(timestamp) - self.RUNE_GRACE)
        self.regen_time = timestamp + (10000 - rune_grace_used)

        if convert and not self.blood_tapped:
            self.convert_to_death()
        return True, rune_grace_wasted

    def convert_to_death(self):
        assert not self.blood_tapped
        self.is_death = True

    def blood_tap(self):
        assert not self.is_death
        self.blood_tapped = True

    def stop_blood_tap(self):
        self.blood_tapped = False

    def spend_death(self, timestamp: int, convert_back: bool):
        if not self.can_spend_death(timestamp):
            return False, 0

        spend, rune_grace_wasted = self.spend(timestamp, False)
        if not spend:
            return spend, rune_grace_wasted

        if convert_back and not self.blood_tapped:
            self.is_death = False
        return spend, rune_grace_wasted

    def get_name(self):
        if self.is_death or self.blood_tapped:
            return "Death"
        return self.type

    def time_since_regen(self, timestamp):
        if self.regen_time is None:
            return 0
        return max(0, timestamp - self.regen_time)


class RuneTracker(BaseAnalyzer):
    def __init__(self):
        self.runes = [
            Rune("Blood1", "Blood"),
            Rune("Blood2", "Blood"),
            Rune("Frost1", "Frost"),
            Rune("Frost2", "Frost"),
            Rune("Unholy1", "Unholy"),
            Rune("Unholy2", "Unholy"),
        ]
        self.rune_grace_wasted = 0
        self.rune_spend_error = False

    @property
    def current_death_runes(self):
        return [r for r in self.runes if r.is_death or r.blood_tapped]

    def _sorted_runes(self, runes):
        runes_ = [(rune, i) for i, rune in enumerate(runes)]
        runes_sorted = sorted(runes_, key=lambda r: (r[0].regen_time or 0, r[1]))
        return [rune for rune, _ in runes_sorted]

    def resync_runes(self, timestamp, rune_cost, runes_used):
        def _resync_runes(runes, num):
            refreshed = 0

            for rune in self._sorted_runes(runes):
                if refreshed >= num:
                    break
                if not rune.can_spend(timestamp):
                    rune.refresh(timestamp)
                refreshed += 1

            return refreshed == num

        total_cost = rune_cost["blood"] + rune_cost["frost"] + rune_cost["unholy"]
        total_used = runes_used["blood"] + runes_used["frost"] + runes_used["unholy"]

        _resync_runes(self.runes[0:2], runes_used["blood"])
        _resync_runes(self.runes[2:4], runes_used["frost"])
        _resync_runes(self.runes[4:6], runes_used["unholy"])
        _resync_runes(self.current_death_runes, total_cost - total_used)

    def _spend_runes(self, num, runes, timestamp, convert=False):
        if not num:
            return True, 0

        spent = 0
        rune_grace_wasted = 0

        for rune in runes:
            if spent == num:
                break
            # Don't spend deaths here in order to prioritize normal runes,
            # deaths will be done in next loop
            if rune.can_spend(timestamp) and not rune.can_spend_death(timestamp):
                rune_grace_wasted += rune.spend(timestamp, convert)[1]
                spent += 1

        for rune in self.runes[:2]:
            if spent == num:
                break
            if rune.can_spend_death(timestamp):
                # Ignore death rune_grace_wasted
                rune.spend_death(timestamp, convert_back=not convert)
                spent += 1

                # This handles the case where we use a death rune for a spell
                # that would convert some runes to death.
                # The in-game behaviour is that if a death is used instead,
                # then it finds a rune that could have been converted and does so
                if convert and rune.blood_tapped:
                    # A rune should never be both blood tapped and a
                    # normally converted death rune
                    assert not rune.is_death

                    # Find the first non-blood-tapped rune and convert it
                    for rune_ in runes:
                        if not rune_.is_death and not rune_.blood_tapped:
                            rune_.convert_to_death()
                            break

        return spent == num, rune_grace_wasted

    def spend(self, ability, timestamp: int, blood: int, frost: int, unholy: int):
        convert_blood = ability in ("Blood Strike", "Pestilence")
        blood_spend = self._spend_runes(
            blood, self.runes[0:2], timestamp, convert_blood
        )
        frost_spend = self._spend_runes(frost, self.runes[2:4], timestamp)
        unholy_spend = self._spend_runes(unholy, self.runes[4:6], timestamp)

        spent = blood_spend[0] and frost_spend[0] and unholy_spend[0]

        # Note: we don't really care about blood runes drifting
        rune_grace_wasted = max(frost_spend[1], unholy_spend[1])
        return spent, rune_grace_wasted

    def blood_tap(self, timestamp: int):
        # Convert one of the runes to a death rune
        for i in range(2):
            if not self.runes[i].is_death:
                self.runes[i].blood_tap()
                break

        # Refresh the cooldown of one of the runes
        for i in range(2):
            if not self.runes[i].can_spend(timestamp):
                self.runes[i].refresh(timestamp)
                break

    def stop_blood_tap(self):
        for i in range(2):
            if self.runes[i].blood_tapped:
                self.runes[i].stop_blood_tap()
                break

    def erw(self, timestamp: int):
        for i in range(6):
            if not self.runes[i].can_spend(timestamp):
                self.runes[i].refresh(timestamp)

    def current_runes(self, timestamp):
        def _count_rune(i):
            return 1 if self.runes[i].can_spend(timestamp) else 0

        return {
            "blood": sum(_count_rune(i) for i in range(0, 2)),
            "frost": sum(_count_rune(i) for i in range(2, 4)),
            "unholy": sum(_count_rune(i) for i in range(4, 6)),
        }

    def add_event(self, event):
        if event.get("rune_cost"):
            # Bit of a hack to deal with the logs saying there's no rune
            # but there actually is. So we only respawn a new rune if we actually need it
            # http://localhost:5173/?fight=56&source=19&report=4ZtgQYvTyAmbMLDX
            runes_needed = {}
            for rune_type, num in self.current_runes(event["timestamp"]).items():
                runes_used = event["runes_used"]
                runes_needed[rune_type] = max(num, runes_used[rune_type])

            # Sync runes to what we think they should be
            self.resync_runes(event["timestamp"], event["rune_cost"], runes_needed)

        event["runes_before"] = self._serialize(event["timestamp"])

        if event["type"] == "cast":
            if event.get("rune_cost"):
                spent, rune_grace_wasted = self.spend(
                    event["ability"],
                    event["timestamp"],
                    **event["rune_cost"],
                )
                event["rune_spend_error"] = not spent

                if not event["in_dead_zone"] and (
                    not event["recent_dead_zone"]
                    or event["timestamp"] - event["recent_dead_zone"][1] > 7500
                ):
                    event["rune_grace_wasted"] = rune_grace_wasted
                    self.rune_grace_wasted += rune_grace_wasted

            if event["ability"] == "Blood Tap":
                self.blood_tap(event["timestamp"])

            if event["ability"] == "Empower Rune Weapon":
                self.erw(event["timestamp"])

        if event["type"] == "removebuff" and event["ability"] == "Blood Tap":
            self.stop_blood_tap()

        event["runes"] = self._serialize(event["timestamp"])

    def print(self):
        console.print(f"* You drifted runes by a total of {self.rune_grace_wasted} ms")

    def score(self):
        return max(0.0, 1 - self.rune_grace_wasted * 0.000025)

    def _serialize(self, timestamp):
        return [
            {
                "name": rune.get_name(),
                "is_available": rune.can_spend(timestamp),
                "regen_time": rune.regen_time,
            }
            for rune in self.runes
        ]

    def report(self):
        return {
            "rune_drift": {
                "rune_drift_ms": self.rune_grace_wasted,
            }
        }


class BuffTracker(BaseAnalyzer):
    def __init__(self, buffs_to_track, starting_auras):
        self._buffs_to_track = buffs_to_track
        self._active = {}  # preserves insertion order
        self._has_flask = False
        self._pots_used = 0
        self._add_starting_auras(starting_auras)

    def _add(self, id, name, icon):
        if name == "Flask of Endless Rage":
            self._has_flask = True

        # There's a bug where Speed is in starting auras but also
        # an event after the fight starts
        if name in ("Speed", "Indestructible") and name not in self._active:
            self._pots_used += 1

        if name in self._buffs_to_track:
            self._active[name] = {
                "abilityGameID": id,
                "ability": name,
                "ability_icon": icon,
            }

    def _remove(self, name):
        if name == "Flask of Endless Rage":
            self._has_flask = False

        if name in self._buffs_to_track:
            if name in self._active:
                del self._active[name]

    def get_buff_short_names(self):
        return [self._buffs_to_track[buff] for buff in self._active]

    def add_event(self, event):
        if event["type"] == "applybuff":
            self._add(event["abilityGameID"], event["ability"], event["ability_icon"])
        if event["type"] == "removebuff":
            self._remove(event["ability"])
        event["buffs"] = list(self._active.values())
        event["buff_short_names"] = self.get_buff_short_names()

    def _add_starting_auras(self, starting_auras):
        for aura in starting_auras:
            if "name" in aura:
                self._add(aura["ability"], aura["name"], aura["ability_icon"])

    def print(self):
        red = "[red]x[/red]"
        green = "[green]✓[/green]"

        s = green if self._pots_used >= 2 else red
        s += f" {self._pots_used} potions used"
        console.print(s)

        s = green if self._has_flask else red
        s += " Had" if self._has_flask else " Missing"
        s += " Flask of Endless Rage"
        console.print(s)

    def score(self):
        total_pots = max(2, self._pots_used)
        pot_score = self._pots_used / total_pots * 0.5
        flask_score = 0.5 if self._has_flask else 0
        return pot_score + flask_score

    def report(self):
        return {
            "potion_usage": {
                "potions_used": self._pots_used,
            },
            "flask_usage": {
                "has_flask": self._has_flask,
            },
        }


class RPAnalyzer(BaseAnalyzer):
    def __init__(self):
        self._count_wasted = 0
        self._sum_wasted = 0
        self._count_gained = 0
        self._sum_gained = 0

    def add_event(self, event):
        if event["type"] == "cast" and event.get("runic_power_waste", 0) > 0:
            self._count_wasted += 1
            self._sum_wasted += event["runic_power_waste"] // 10
        if event["type"] == "resourcechange" and "runic_power_gained_ams" in event:
            self._count_gained += 1
            self._sum_gained += event["runic_power_gained_ams"] // 10

    def print(self):
        console.print(
            f"* Over-capped RP {self._count_wasted} times with a total of {self._sum_wasted} RP wasted"
        )
        console.print(
            f"Gained RP {self._count_gained} times for a total of {self._sum_gained} RP"
        )

    def score(self):
        waste = self._sum_wasted - self._sum_gained
        if waste < 150:
            return 1
        if waste < 200:
            return 0.5
        if waste < 250:
            return 0.25
        return 0

    def report(self):
        return {
            "runic_power": {
                "overcap_times": self._count_wasted,
                "overcap_sum": self._sum_wasted,
                "gained_times": self._count_gained,
                "gained_sum": self._sum_gained,
            }
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


class GCDAnalyzer(BaseAnalyzer):
    NO_GCD = {
        "Unbreakable Armor",
        "Blood Tap",
        "Global Thermal Sapper Charge",
        "Saronite Bomb",
        "Speed",
        "Empower Rune Weapon",
        "Cobalt Frag Bomb",
        "Hyperspeed Acceleration",
        "Blood Fury",
        "Berserking",
        "Indestructible",
        "Deathchill",
        "Melee",
        "Path of Illidan",
        "Anti-Magic Shell",
        "Unholy Frenzy",
        "Wrathstone",
    }

    def __init__(self):
        self._gcds = []
        self._last_event = None

    def add_event(self, event):
        if not event["type"] == "cast":
            return

        if self._last_event is None:
            offset = event["timestamp"]
            last_timestamp = 0
        else:
            if event["recent_dead_zone"]:
                if event["in_dead_zone"]:
                    last_timestamp = event["timestamp"]
                else:
                    last_timestamp = max(
                        event["recent_dead_zone"][1], self._last_event["timestamp"]
                    )
            else:
                last_timestamp = self._last_event["timestamp"]

            offset = event["timestamp"] - last_timestamp

        event["gcd_offset"] = offset
        event["has_gcd"] = event["ability"] not in self.NO_GCD

        if event["has_gcd"]:
            self._gcds.append((event["timestamp"], last_timestamp))
            self._last_event = event

    @property
    def latencies(self):
        latencies = []

        for timestamp, last_timestamp in self._gcds:
            timestamp_diff = timestamp - last_timestamp

            # don't handle spell GCD for now
            latency = timestamp_diff - 1500
            if latency > -50:
                latencies.append(max(0, latency))

        return latencies

    @property
    def average_latency(self):
        latencies = self.latencies
        # Don't count first GCD
        return sum(latencies[1:]) / len(latencies[1:]) if len(latencies) > 1 else 0

    def print(self):
        average_latency = self.average_latency
        console.print(f"* Your average GCD usage delay was {average_latency:.2f} ms")

    def score(self):
        return max(0, 1 - 0.0017 * self.average_latency)

    def report(self):
        average_latency = self.average_latency

        return {
            "gcd_latency": {
                "average_latency": average_latency,
            }
        }


class DiseaseAnalyzer(BaseAnalyzer):
    DISEASE_DURATION_MS = 15000

    def __init__(self, encounter_name, fight_end_time):
        self._dropped_diseases_timestamp = []
        self._encounter_name = encounter_name
        self._fight_end_time = fight_end_time

    def add_event(self, event):
        if (
            event["type"] == "removedebuff"
            and event["ability"]
            in (
                "Blood Plague",
                "Frost Fever",
            )
            and event["target_is_boss"]
            and (self._encounter_name != "Thaddius" or not event["in_dead_zone"])
        ):
            if not event["target_dies_at"] or (
                event["target_dies_at"] - event["timestamp"] > 10000
            ):
                self._dropped_diseases_timestamp.append(event["timestamp"])

    @property
    def num_diseases_dropped(self):
        num_diseases_dropped = 0
        last_timestamp = None

        for timestamp in self._dropped_diseases_timestamp:
            # Dropping them at the end of the fight is fine
            if self._fight_end_time - timestamp < 10000:
                continue
            if last_timestamp is None:
                num_diseases_dropped += 1
            elif timestamp - last_timestamp > self.DISEASE_DURATION_MS:
                num_diseases_dropped += 1
            last_timestamp = timestamp
        return num_diseases_dropped

    def print(self):
        if self.num_diseases_dropped:
            console.print(
                f"[red]x[/red] You dropped diseases {self.num_diseases_dropped} times"
            )
        else:
            console.print("[green]✓[/green] You did not drop diseases")

    def score(self):
        if self.num_diseases_dropped == 0:
            return 1
        if self.num_diseases_dropped == 1:
            return 0.5
        return 0

    def report(self):
        return {
            "diseases_dropped": {
                "num_diseases_dropped": self.num_diseases_dropped,
            }
        }


class RimeAnalyzer(BaseAnalyzer):
    def __init__(self):
        self._num_total = 0
        self._num_used = 0

    def add_event(self, event):
        if event["type"] in ("applybuff", "refreshbuff") and event["ability"] == "Rime":
            self._num_total += 1
        if event.get("consumes_rime"):
            self._num_used += 1

    def score(self):
        if not self._num_total:
            return 0
        return 1 * (self._num_used / self._num_total)

    def report(self):
        return {
            "rime": {
                "num_total": self._num_total,
                "num_used": self._num_used,
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


class CoreAbilities(BaseAnalyzer):
    CORE_ABILITIES = {
        "Icy Touch",
        "Plague Strike",
        "Unbreakable Armor",
        "Obliterate",
        "Pestilence",
        "Howling Blast",
        "Blood Strike",
    }

    def add_event(self, event):
        if event["type"] == "cast":
            if event["ability"] in self.CORE_ABILITIES:
                event["is_core_cast"] = True
            else:
                event["is_core_cast"] = False


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


class AnalysisScores(BaseAnalyzer):
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
        # Speed
        gcd_score = self.ScoreWeight(self.get_analyzer(GCDAnalyzer).score(), 3)
        drift_score = self.ScoreWeight(self.get_analyzer(RuneTracker).score(), 3)
        km_score = self.ScoreWeight(self.get_analyzer(KMAnalyzer).score(), 1)

        # Rotation
        ua_analyzer = self.get_analyzer(UAAnalyzer)
        ua_score = self.ScoreWeight(ua_analyzer.score(), ua_analyzer.num_possible)
        disease_score = self.ScoreWeight(self.get_analyzer(DiseaseAnalyzer).score(), 2)
        hb_score = self.ScoreWeight(
            self.get_analyzer(HowlingBlastAnalyzer).score(), 0.5
        )
        rime_score = self.ScoreWeight(self.get_analyzer(RimeAnalyzer).score(), 0.5)
        raise_dead_score = self.ScoreWeight(self.get_analyzer(RaiseDeadAnalyzer).score(), 1)

        # Misc
        consume_score = self.ScoreWeight(self.get_analyzer(BuffTracker).score(), 0.5)

        total_score = self._get_scores(
            gcd_score,
            drift_score,
            km_score,
            ua_score,
            disease_score,
            hb_score,
            rime_score,
            consume_score,
            raise_dead_score,
        )

        return {
            "analysis_scores": {
                "total_score": total_score,
            }
        }


class Analyzer:
    def __init__(self, fight: Fight):
        self._fight = fight
        self._events = self._filter_events()

    def _get_valid_initial_rune_state(self):
        rune_death_states = [(False, False), (True, False), (False, True), (True, True)]

        for rune_death_state in rune_death_states:
            runes = RuneTracker()

            for i, is_death in enumerate(rune_death_state):
                runes.runes[i].is_death = is_death

            for event in self._events:
                runes.add_event(event)
                if event.get("rune_spend_error"):
                    break
            else:
                return rune_death_state

        return None

    def _analyze_dead_zones(self):
        dead_zone_analyzer = DeadZoneAnalyzer(self._fight)

        for event in self._events:
            dead_zone_analyzer.add_event(event)

        for event in self._events:
            dead_zone_analyzer.decorate_event(event)

        return dead_zone_analyzer

    def _filter_events(self):
        events = []

        for i, event in enumerate(self._fight.events):
            # We're neither the source nor the target (eg: ghouls attacking boss)
            if (
                event["sourceID"] != self._fight.source.id
                and event["targetID"] != self._fight.source.id
            ):
                continue

            # Don't really care about these
            if event["type"] in (
                "applydebuffstack",
                "damage",
                "heal",
            ):
                continue

            if (
                event["type"] == "removebuff"
                and event["targetID"] != self._fight.source.id
            ):
                continue

            if event["type"] == "cast" and event["sourceID"] != self._fight.source.id:
                continue

            events.append(event)
        return events

    @property
    def displayable_events(self):
        events = []

        for event in self._events:
            if (
                (event["type"] == "cast" and event["ability"] not in ("Speed", "Melee"))
                or (
                    event["type"] == "applybuff"
                    and event["ability"] == "Killing Machine"
                )
                or (
                    event["type"] == "removebuff"
                    and event["ability"] in ("Unbreakable Armor", "Blood Tap")
                )
                or (
                    event["type"] == "removedebuff"
                    and event["ability"] in ("Blood Plague", "Frost Fever")
                    and (
                        self._fight.encounter.name != "Thaddius"
                        or not event["in_dead_zone"]
                    )
                    and event["target_is_boss"]
                )
                or (
                    event["type"] in ("removedebuff", "applydebuff", "refreshdebuff")
                    and event["ability"]
                    in ("Fungal Creep", "Web Spray", "Frost Blast", "Slag Pot")
                )
            ):
                events.append(event)
        return events

    def analyze(self):
        if not self._events:
            raise Exception("There are no events to analyze")

        source_id = self._fight.source.id
        combatant_info = self._fight.get_combatant_info(source_id)
        starting_auras = combatant_info.get("auras", [])

        self._analyze_dead_zones()

        runes = RuneTracker()
        initial_rune_state = self._get_valid_initial_rune_state()
        if initial_rune_state:
            for i, is_death in enumerate(initial_rune_state):
                runes.runes[i].is_death = is_death
            has_rune_error = False
        else:
            has_rune_error = True

        table = EventsTable()
        buff_tracker = BuffTracker(
            {
                "Unbreakable Armor": "UA",
                "Heroism": "Lust",
                "Bloodlust": "Lust",
                "Speed": "Speed",
                "Rime": "Rime",
                "Meteorite Whetstone": "Whetstone",
                "Hyperspeed Acceleration": "Gloves",
                "Reflection of Torment": "Mirror",
                "Greatness": "Greatness",
                "Killing Machine": "KM",
                "Grim Toll": "Grim Toll",
                "Indestructible": "Indestructible",
                "Mark of Norgannon": "Mark",
                "Berserking": "Berserking",
                "Blood Fury": "Blood Fury",
                "Black Magic": "Black Magic",
                "Swordguard Embroidery": "Swordguard Embroidery",
                "Unholy Strength": "Unholy Strength",
                "Skyflare Swiftness": "Skyflare Swiftness",
                "Edward's Insight": "Edward's Insight",
                "Loatheb's Shadow": "Loatheb's Shadow",
                "Cinderglacier": "Cinderglacier",
                "Mjolnir Runestone": "Mjolnir Runestone",
                "Implosion": "Implosion",  # Dark Matter
                "Comet's Trail": "Comet's Trail",
                "Wrathstone": "Wrathstone",
                "Blood of the Old God": "Blood of the Old God",
                "Pyrite Infusion": "Pyrite Infusion",
                "Fury of the Five Flights": "Fury of the Five Flights,"
            },
            starting_auras,
        )

        analyzers = [
            runes,
            KMAnalyzer(),
            GCDAnalyzer(),
            RPAnalyzer(),
            UAAnalyzer(self._fight.duration),
            buff_tracker,
            DiseaseAnalyzer(self._fight.encounter.name, self._fight.duration),
            HowlingBlastAnalyzer(),
            CoreAbilities(),
            RimeAnalyzer(),
            RaiseDeadAnalyzer(self._fight.duration),
        ]
        analyzers.append(AnalysisScores(analyzers))

        for event in self._events:
            for analyzer in analyzers:
                analyzer.add_event(event)

        displayable_events = self.displayable_events

        if SHOULD_PRINT:
            for event in displayable_events:
                table.add_event(event)
            table.print()

        analysis = {"has_rune_spend_error": has_rune_error}

        for analyzer in analyzers:
            if SHOULD_PRINT:
                analyzer.print()
            analysis.update(**analyzer.report())

        return {
            "fight_metadata": {
                "source": self._fight.source.name,
                "encounter": self._fight.encounter.name,
                "start_time": self._fight.start_time,
                "end_time": self._fight.end_time,
                "duration": self._fight.end_time - self._fight.start_time,
                "rankings": self._fight.rankings,
            },
            "analysis": analysis,
            "events": displayable_events,
        }


def analyze(report: Report, fight_id: int):
    fight = report.get_fight(fight_id)
    analyzer = Analyzer(fight)
    return analyzer.analyze()
