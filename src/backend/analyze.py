from datetime import timedelta

from rich.console import Console
from rich.table import Table
from rich.style import Style

from client import fetch_report
from report import Fight, Report


console = Console()


class EventsTable:
    def __init__(self, has_rune_error):
        self._events = []
        self._last_event = None
        self._has_rune_error = has_rune_error

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim")
        table.add_column("Ability")
        table.add_column("Runic Power")
        if not has_rune_error:
            table.add_column("Runes")
        table.add_column("Buffs")
        table.add_column("Notes")
        self._table = table

    def _format_rune_state(self, runes):
        rune_color = ["red", "red", "turquoise2", "turquoise2", "green", "green"]
        state = ""

        for i, rune in enumerate(runes):
            r = rune["name"][0]
            if rune["name"] == "Death" and rune["is_available"]:
                r = f"[purple]{r}[/purple]"
            elif rune["is_available"]:
                r = f"[{rune_color[i]}]{r}[/{rune_color[i]}]"
            else:
                r = f"[dim]{r}[/dim]"
            state += r
        return state

    def _format_timestamp(self, timestamp, include_minutes=True):
        time = timedelta(milliseconds=timestamp)
        minutes, seconds = divmod(time.seconds, 60)
        milliseconds = time.microseconds // 1000
        if include_minutes:
            return f"{minutes:02}:{seconds:02}.{milliseconds:03}"
        return f"{seconds:01}.{milliseconds:03}"

    def add_event(self, event):
        notes = []

        time = self._format_timestamp(event["timestamp"])
        if self._last_event is None:
            offset = event["timestamp"]
        else:
            offset = event["timestamp"] - self._last_event["timestamp"]

        if offset > 2000:
            offset_color = "red"
        elif offset > 1600:
            offset_color = "yellow1"
        else:
            offset_color = "green3"
        offset_pretty = self._format_timestamp(offset, include_minutes=False)

        if event.get("has_gcd"):
            time = f"{time} [{offset_color}](+{offset_pretty})[/{offset_color}]"

        ability = event["ability"]
        if event["ability"] == "Obliterate":
            ability = f"[bold]{ability}[/bold]"
        if event["type"] == "removebuff":
            ability = f"[dim]{ability} ends[/dim]"
        if event["type"] == "applybuff":
            ability = f"[dim]{ability} begins[/dim]"
        if event["type"] == "removedebuff":
            ability = f"[bold grey0 on red]{ability} drops[bold grey0 on red]"
        if event["ability"] == "Howling Blast":
            ability = f"{ability} ({event['num_targets']})"
        if event.get("bad_howling_blast"):
            ability = f"[red]{ability}[red]"
            notes.append("[red]BAD_HOWLING_BLAST[/red]")
        if event.get("consumes_km") or event.get("consumes_rime"):
            ability = f"[blue]{ability}[blue]"

        runic_power = event["runic_power"] // 10
        if event.get("runic_power_waste"):
            runic_power_waste = event["runic_power_waste"] // 10
            runic_power = f"[red]{runic_power} (+{runic_power_waste})[/red]"
        else:
            runic_power = f"{runic_power}"

        rune_str = ""
        if not self._has_rune_error:
            if event["runes_before"] and (
                event.get("rune_cost")
                or event["ability"] in ("Blood Tap", "Empower Rune Weapon")
            ):
                rune_str += self._format_rune_state(event["runes_before"])
                rune_str += " -> "
            rune_str += self._format_rune_state(event["runes"])

        buff_strs = []
        for buff in event["buff_short_names"]:
            if buff == "Rime" and event.get("consumes_rime"):
                buff_strs.append(f"[blue]{buff}[/blue]")
            elif buff == "KM" and event.get("consumes_km"):
                buff_strs.append(f"[blue]{buff}[/blue]")
            else:
                buff_strs.append(buff)
        buff_str = ", ".join(buff_strs)

        if event.get("is_miss"):
            notes.append(f"[red]{event['hit_type']}[/red]")
            ability = f"[red]{ability}[/red]"

        row = [time, ability, runic_power]
        if not self._has_rune_error:
            row.append(rune_str)
        row += [buff_str, ",".join(notes)]

        style = (
            Style(bgcolor="grey15")
            if (
                "Unbreakable Armor" in event["buffs"]
                or event["ability"] == "Unbreakable Armor"
            )
            else None
        )

        self._table.add_row(
            *row,
            style=style,
        )

        if event["type"] == "cast" and event["has_gcd"]:
            self._last_event = event

    def print(self):
        console.print(self._table)


class Rune:
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
        self._leeway = 0

    def can_spend(self, timestamp: int):
        if self.regen_time is None:
            return True
        return timestamp >= self.regen_time

    def can_spend_death(self, timestamp: int):
        return (self.is_death or self.blood_tapped) and self.can_spend(timestamp)

    def _rune_grace_used(self, timestamp):
        return min(2500, self.time_since_regen(timestamp))

    def refresh(self, timestamp):
        self.regen_time = timestamp

    def spend(self, timestamp: int, convert: bool):
        if not self.can_spend(timestamp):
            return False, 0

        rune_grace_used = self._rune_grace_used(timestamp)
        rune_grace_wasted = max(0, self.time_since_regen(timestamp) - 2500)
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

    def spend_death(self, timestamp: int, is_same_type: bool):
        if not self.can_spend_death(timestamp):
            return False, 0

        spend, rune_grace_wasted = self.spend(timestamp, False)
        if not spend:
            return spend, rune_grace_wasted

        if not is_same_type and not self.blood_tapped:
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

    def copy(self):
        obj = self.__class__(self.full_name, self.type)
        obj.regen_time = self.regen_time
        obj.is_death = self.is_death
        obj.blood_tapped = self.blood_tapped
        return obj


class RuneTracker:
    def __init__(self):
        self.runes = [
            Rune("Blood1", "Blood"),
            Rune("Blood2", "Blood"),
            Rune("Frost1", "Frost"),
            Rune("Frost2", "Frost"),
            Rune("Unholy1", "Unholy"),
            Rune("Unholy2", "Unholy"),
        ]
        self._rune_grace_wasted = 0
        self.rune_spend_error = False

    def _spend_runes(self, num, runes, timestamp, convert=False):
        if not num:
            return True, 0

        spent = 0
        rune_grace_wasted = 0
        rune_type = runes[0].type

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
                rune_grace_wasted += rune.spend_death(
                    timestamp, is_same_type=(rune.type == rune_type)
                )[1]
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

    def spend(self, timestamp: int, blood: int, frost: int, unholy: int):
        blood_spend = self._spend_runes(blood, self.runes[0:2], timestamp, True)
        frost_spend = self._spend_runes(frost, self.runes[2:4], timestamp)
        unholy_spend = self._spend_runes(unholy, self.runes[4:6], timestamp)

        spent = blood_spend[0] and frost_spend[0] and unholy_spend[0]
        rune_grace_wasted = blood_spend[1] + frost_spend[1] and unholy_spend[1]
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

    def add_event(self, event):
        event["runes_before"] = self.serialize(event["timestamp"])

        if event["type"] == "removebuff" and event["ability"] == "Blood Tap":
            self.stop_blood_tap()

        if event["type"] == "cast":
            if event.get("rune_cost"):
                spent, rune_grace_wasted = self.spend(
                    event["timestamp"],
                    **event["rune_cost"],
                )
                event["rune_grace_wasted"] = rune_grace_wasted
                event["rune_spend_error"] = not spent
                self._rune_grace_wasted += rune_grace_wasted

            if event["ability"] == "Blood Tap":
                self.blood_tap(event["timestamp"])

            if event["ability"] == "Empower Rune Weapon":
                self.erw(event["timestamp"])

        event["runes"] = self.serialize(event["timestamp"])

    def copy(self):
        obj = self.__class__()
        obj.runes = [rune.copy() for rune in self.runes]
        return obj

    def print(self):
        console.print(f"* You drifted runes by a total of {self._rune_grace_wasted} ms")

    def serialize(self, timestamp):
        return [
            {
                "name": rune.get_name(),
                "is_available": rune.can_spend(timestamp),
                "regen_time": rune.regen_time,
            }
            for rune in self.runes
        ]


class BuffTracker:
    def __init__(self, buffs_to_track, starting_auras):
        self._buffs_to_track = buffs_to_track
        self._active = {}  # preserves insertion order
        self._has_flask = False
        self._pots_used = 0
        self.add_starting_auras(starting_auras)

    def has(self, buff):
        return buff in self._active

    def add(self, buff):
        if buff == "Flask of Endless Rage":
            self._has_flask = True

        if buff == "Speed":
            self._pots_used += 1

        if buff in self._buffs_to_track:
            self._active[buff] = True

    def remove(self, buff):
        if buff == "Flask of Endless Rage":
            self._has_flask = False

        if buff in self._buffs_to_track:
            if buff in self._active:
                del self._active[buff]

    def get_buff_short_names(self):
        return [self._buffs_to_track[buff] for buff in self._active]

    def add_event(self, event):
        if event["type"] == "applybuff":
            self.add(event["ability"])
        if event["type"] == "removebuff":
            self.remove(event["ability"])
        event["buffs"] = set(self._active)
        event["buff_short_names"] = self.get_buff_short_names()

    def add_starting_auras(self, starting_auras):
        for aura in starting_auras:
            if "name" in aura:
                self.add(aura["name"])

    def print(self):
        red = "[red]x[/red]"
        green = "[green]✓[/green]"

        s = green if self._pots_used == 2 else red
        s += f" {self._pots_used} potions used"
        console.print(s)

        s = green if self._has_flask else red
        s += " Had" if self._has_flask else " Missing"
        s += " Flask of Endless Rage"
        console.print(s)


class RPAnalyzer:
    def __init__(self):
        self._count = 0
        self._sum = 0

    def add_event(self, event):
        if event["type"] == "cast" and event.get("runic_power_waste", 0) > 0:
            self._count += 1
            self._sum += event["runic_power_waste"] // 10

    def print(self):
        console.print(
            f"* Over-capped RP {self._count} times with a total of {self._sum} RP wasted"
        )


class UAAnalyzer:
    class Window:
        def __init__(self, expected_oblits):
            self.oblits = 0
            self.expected_oblits = expected_oblits

        def __str__(self):
            s = (
                "[green]✓[/green] "
                if self.oblits == self.expected_oblits
                else "[red]x[/red] "
            )
            s += f"Hit {self.oblits} of {self.expected_oblits} obliterates"
            if self.expected_oblits == 6:
                s += " (with ERW)"
            return s

    def __init__(self, fight_end_time):
        self._window = None
        self._windows = []
        self._fight_end_time = fight_end_time

    def add_event(self, event):
        if event["type"] == "applybuff" and event["ability"] == "Unbreakable Armor":
            self._window = self.Window(5)
            self._windows.append(self._window)
        elif event["type"] == "removebuff" and event["ability"] == "Unbreakable Armor":
            self._window = None
        elif self._window and not event.get("is_miss"):
            if event["ability"] == "Empower Rune Weapon":
                self._window.expected_oblits = 6
            if event["type"] == "cast" and event["ability"] == "Obliterate":
                self._window.oblits += 1

    def print(self):
        possible_ua_windows = 1 + (self._fight_end_time - 3000) // 60000

        color = (
            "[green]✓[/green]"
            if possible_ua_windows == len(self._windows)
            else "[red]x[/red]"
        )
        console.print(
            f"{color} You used UA {len(self._windows)}"
            f" out of a possible {possible_ua_windows} times"
        )

        for window in self._windows:
            console.print(f"\t - {window}")


class KMAnalyzer:
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
        used_windows = [window for window in self._windows if window.used_timestamp]
        num_windows = len(self._windows)
        num_used = len(used_windows)
        latencies = [
            window.used_timestamp - window.gained_timestamp for window in used_windows
        ]

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            console.print(
                f"* You used {num_used} of {num_windows} Killing Machine procs"
            )
            console.print(
                f"* Your average Killing Machine proc usage delay was {avg_latency:.2f} ms"
            )
        else:
            console.print("* You did not use any Killing Machine procs")


class GCDAnalyzer:
    NO_GCD = {
        "Unbreakable Armor",
        "Blood Tap",
        "Global Thermal Sapper Charge",
        "Saronite Bomb",
        "Speed",
        "Empower Rune Weapon",
        "Cobalt Frag Bomb",
        "Hyperspeed Acceleration",
    }

    def __init__(self):
        self._gcds = []

    def add_event(self, event):
        if not event["type"] == "cast":
            return

        event["has_gcd"] = event["ability"] not in self.NO_GCD

        if event["has_gcd"]:
            self._gcds.append(event["timestamp"])

    def print(self):
        last_timestamp = None
        latencies = []

        for timestamp in self._gcds:
            if last_timestamp is None:
                timestamp_diff = timestamp
            else:
                timestamp_diff = timestamp - last_timestamp

            # don't handle spell GCD for now
            latency = timestamp_diff - 1500
            if latency > 0:
                latencies.append(latency)
            last_timestamp = timestamp

        average_latency = sum(latencies) / len(latencies)
        console.print(f"* Your average GCD usage delay was {average_latency:.2f} ms")


class DiseaseAnalyzer:
    DISEASE_DURATION_MS = 15000

    def __init__(self):
        self._dropped_diseases_timestamp = []

    def add_event(self, event):
        if event["type"] == "removedebuff" and event["ability"] in (
            "Blood Plague",
            "Frost Fever",
        ):
            self._dropped_diseases_timestamp.append(event["timestamp"])

    def print(self):
        num_diseases_dropped = 0
        last_timestamp = None

        for timestamp in self._dropped_diseases_timestamp:
            if last_timestamp is None:
                num_diseases_dropped += 1
            elif timestamp - last_timestamp > self.DISEASE_DURATION_MS:
                num_diseases_dropped += 1
            last_timestamp = timestamp

        if num_diseases_dropped:
            console.print(
                f"[red]x[/red] You dropped diseases {num_diseases_dropped} times"
            )
        else:
            console.print("[green]✓[/green] You did not drop diseases")


class HowlingBlastAnalyzer:
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
                "[green]✓[/green] You always used Howling Blast with rime or on multiple targets"
            )


class Analyzer:
    def __init__(self, fight: Fight):
        self._fight = fight
        self._events = self._filter_events()

    def _has_rune_error(self):
        runes = RuneTracker()

        for event in self._events:
            runes.add_event(event)
            if event.get("rune_spend_error"):
                break
        else:
            return False

        return True

    def _filter_events(self):
        events = []

        for i, event in enumerate(self._fight.events):
            if event.get("abilityGameID") == 1:  # melee
                continue

            # We're neither the source nor the target (eg: ghouls attacking boss)
            if (
                event["sourceID"] != self._fight.source.id
                and event["targetID"] != self._fight.source.id
            ):
                continue

            # Don't really care about these
            if event["type"] in (
                "applydebuffstack",
                "refreshdebuff",
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
                (event["type"] == "cast" and event["ability"] != "Speed")
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
                )
            ):
                events.append(event)
        return events

    def analyze(self):
        if not self._events:
            raise Exception("There are no events to analyze")

        source_id = self._fight.source.id
        combatant_info = self._fight.get_combatant_info(source_id)
        starting_auras = combatant_info["auras"]

        runes = RuneTracker()
        table = EventsTable(self._has_rune_error())
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
            },
            starting_auras,
        )
        analyzers = [
            runes,
            KMAnalyzer(),
            GCDAnalyzer(),
            RPAnalyzer(),
            UAAnalyzer(self._fight.end_time),
            buff_tracker,
            DiseaseAnalyzer(),
            HowlingBlastAnalyzer(),
        ]

        for event in self._events:
            for analyzer in analyzers:
                analyzer.add_event(event)

        displayable_events = self.displayable_events

        for event in displayable_events:
            table.add_event(event)
        table.print()

        for analyzer in analyzers:
            analyzer.print()

        return {
            "fight_metadata": {
                "source": self._fight.source.name,
                "encounter": self._fight.encounter.name,
                "start_time": self._fight.start_time,
                "end_time": self._fight.end_time,
                "duration": self._fight.end_time - self._fight.start_time,
            },
            "events": displayable_events,
        }


def analyze(report: Report, encounter: str):
    fight = report.get_fight(encounter)
    analyzer = Analyzer(fight)
    return analyzer.analyze()


# report_code = "9Cp8zD1KtMfNQhPZ"
# encounter = "Heigan the Unclean"
# character = "Ennthoz"

# report_code = "yZCw8mhdtF6H3X9T"
# encounter = "Patchwerk"
# character = "Launched"

report_code = "hpZnwjfbMC8Gyz2q"
encounter = "Anub'Rekhan"
character = "Sails"

# report_code = "kYHfBd3wqmVZt7hx"
# encounter = "Patchwerk"
# character = "Selitos"

# report_code = "3fprXWKHBxkPynqA"
# encounter = "Patchwerk"
# character = "Km"

# report_code = "g934AyzjwZLp1rha"
# encounter = "Patchwerk"
# character = "Sails"

# Leeway issue (too little?)
# report_code = "g934AyzjwZLp1rha"
# character = "Coomroom"

# Leeway issue (too much):
# report_code = "vryQC8gMZ9Bb43fK"
# character = "Sammarah"
# encounter = "Patchwerk"


if __name__ == "__main__":

    async def run():
        report = await fetch_report(report_code, character, encounter)
        analyze(report, encounter)

    import asyncio

    asyncio.run(run())
