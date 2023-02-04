import os
from datetime import timedelta

from rich.console import Console
from rich.table import Table
from rich.style import Style

# Don't print report to console if in lambda
SHOULD_PRINT = os.environ.get("AWS_EXECUTION_ENV") is None

# console = Console(quiet=not SHOULD_PRINT)
console = Console(quiet=True)


class EventsTable:
    def __init__(self):
        self._events = []

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim")
        table.add_column("Ability")
        table.add_column("Runic Power")
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
            r += f" {rune['regen_time']}"
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

        if "gcd_offset" in event:
            offset = event["gcd_offset"]
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

        if event.get("rune_spend_error"):
            notes.append("RUNE_ERROR")

        row = [time, ability, runic_power]
        row.append(rune_str)
        row += [buff_str, ",".join(notes)]

        style = (
            Style(bgcolor="grey15")
            if (
                "UA" in event["buff_short_names"]
                or event["ability"] == "Unbreakable Armor"
            )
            else None
        )

        self._table.add_row(
            *row,
            style=style,
        )

    def print(self):
        console.print(self._table)

