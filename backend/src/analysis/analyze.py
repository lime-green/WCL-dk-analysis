from analysis.core_analysis import (
    CoreAnalysisConfig,
    DeadZoneAnalyzer,
    BuffTracker,
)
from analysis.frost_analysis import (
    FrostAnalysisConfig,
)
from analysis.unholy_analysis import UnholyAnalysisConfig
from console_table import EventsTable, SHOULD_PRINT
from report import Fight, Report


class Analyzer:
    SPEC_ANALYSIS_CONFIGS = {
        "Default": CoreAnalysisConfig,
        "Frost": FrostAnalysisConfig,
        "Unholy": UnholyAnalysisConfig,
    }

    def __init__(self, fight: Fight):
        self._fight = fight
        self._events = self._filter_events()
        self.__spec = None
        self._analysis_config = self.SPEC_ANALYSIS_CONFIGS.get(
            self._detect_spec(),
            self.SPEC_ANALYSIS_CONFIGS["Default"],
        )()
        self._buff_tracker = None

    def _get_valid_initial_rune_state(self):
        rune_death_states = [(False, False), (True, False), (False, True), (True, True)]

        for rune_death_state in rune_death_states:
            runes = self._analysis_config.create_rune_tracker()

            for i, is_death in enumerate(rune_death_state):
                runes.runes[i].is_death = is_death

            for event in self._events:
                runes.add_event(event)
                if event.get("rune_spend_error"):
                    break
            else:
                return rune_death_state

        return None

    def _preprocess_events(self):
        dead_zone_analyzer = DeadZoneAnalyzer(self._fight)
        buff_tracker = self._get_buff_tracker()

        for event in self._events:
            dead_zone_analyzer.preprocess_event(event)
            buff_tracker.preprocess_event(event)

        for event in self._events:
            dead_zone_analyzer.decorate_event(event)
            buff_tracker.decorate_event(event)

        return dead_zone_analyzer

    def _get_buff_tracker(self):
        if self._buff_tracker is None:
            source_id = self._fight.source.id
            combatant_info = self._fight.get_combatant_info(source_id)
            starting_auras = combatant_info.get("auras", [])

            self._buff_tracker = BuffTracker(
                {
                    "Unbreakable Armor",
                    "Heroism",
                    "Bloodlust",
                    "Speed",
                    "Rime",
                    "Meteorite Whetstone",
                    "Hyperspeed Acceleration",
                    "Reflection of Torment",
                    "Greatness",
                    "Killing Machine",
                    "Grim Toll",
                    "Indestructible",
                    "Mark of Norgannon",
                    "Berserking",
                    "Blood Fury",
                    "Black Magic",
                    "Swordguard Embroidery",
                    "Unholy Strength",
                    "Skyflare Swiftness",
                    "Edward's Insight",
                    "Loatheb's Shadow",
                    "Cinderglacier",
                    "Mjolnir Runestone",
                    "Implosion",  # Dark Matter
                    "Comet's Trail",
                    "Wrathstone",
                    "Blood of the Old God",
                    "Pyrite Infusion",
                    "Fury of the Five Flights",
                    "Desolation",
                },
                self._fight.duration,
                starting_auras,
                self._detect_spec(),
            )
        return self._buff_tracker

    def _detect_spec(self):
        if not self.__spec:

            def detect():
                for event in self._events:
                    if event["type"] == "cast" and event["ability"] in (
                        "Howling Blast",
                        "Frost Strike",
                    ):
                        return "Frost"
                    if event["type"] == "cast" and event["ability"] in (
                        "Summon Gargoyle",
                        "Ghoul Frenzy",
                    ):
                        return "Unholy"

                # If the above doesn't work, then try with less determinate spells
                for event in self._events:
                    if event["type"] == "cast" and event["ability"] == "Obliterate":
                        return "Frost"
                    if (
                        event["type"] == "cast"
                        and event["ability"] == "Death and Decay"
                    ):
                        return "Unholy"

                return None

            self.__spec = detect()
        return self.__spec

    def _filter_events(self):
        """Remove any events we don't care to analyze or show"""
        events = []

        for i, event in enumerate(self._fight.events):
            # We're neither the source nor the target
            if (
                event["sourceID"] != self._fight.source.id
                and event["targetID"] != self._fight.source.id
                and event["sourceID"] not in self._fight.source.pets
                and event["targetID"] not in self._fight.source.pets
            ):
                continue

            # Don't really care about these
            if event["type"] in ("applydebuffstack",):
                continue

            if (
                event["type"] in ("refreshbuff", "applybuff", "removebuff")
                and event["targetID"] != self._fight.source.id
                and event["targetID"] not in self._fight.source.pets
            ):
                continue

            events.append(event)
        return events

    @property
    def displayable_events(self):
        """Remove any events we don't care to show in the UI"""
        events = []

        for event in self._events:
            if event["sourceID"] == self._fight.source.id and (
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
                    in (
                        "Fungal Creep",
                        "Web Spray",
                        "Frost Blast",
                        "Slag Pot",
                        "Black Hole",
                    )
                )
            ):
                events.append(event)
        return events

    def analyze(self):
        self._preprocess_events()

        runes = self._analysis_config.create_rune_tracker()
        initial_rune_state = self._get_valid_initial_rune_state()
        if initial_rune_state:
            for i, is_death in enumerate(initial_rune_state):
                runes.runes[i].is_death = is_death
            has_rune_error = False
        else:
            has_rune_error = True

        table = EventsTable()

        buff_tracker = self._get_buff_tracker()
        analyzers = [runes, buff_tracker]
        analyzers.extend(self._analysis_config.get_analyzers(self._fight, buff_tracker))
        analyzers.append(self._analysis_config.get_scorer(analyzers))

        source_id = self._fight.source.id
        for event in self._events:
            for analyzer in analyzers:
                if (
                    event["sourceID"] == source_id or event["targetID"] == source_id
                ) or (
                    analyzer.INCLUDE_PET_EVENTS
                    and (event["is_owner_pet_source"] or event["is_owner_pet_target"])
                ):
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
            "spec": self._detect_spec(),
            "show_procs": self._analysis_config.show_procs,
            "show_speed": self._analysis_config.show_speed,
        }


def analyze(report: Report, fight_id: int):
    fight = report.get_fight(fight_id)
    analyzer = Analyzer(fight)
    return analyzer.analyze()
