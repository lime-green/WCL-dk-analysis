from dataclasses import dataclass


@dataclass
class Encounter:
    id: int
    name: str


@dataclass
class Source:
    id: int
    name: str


HIT_TYPES = {
    0: "MISS",
    1: "NORMAL",
    2: "CRIT",
    3: "ABSORB",
    4: "BLOCKED_NORMAL",
    5: "BLOCKED_CRIT",
    6: "GLANCING",
    7: "DODGE",
    8: "PARRY",
    10: "IMMUNE",
    11: "MISSFIRE",
    12: "REFLECT",
    13: "EVADE",
    14: "RESIST_FULL",
    15: "CRUSHING",
    16: "RESIST_PARTIAL",
    17: "RESIST_PARTIAL_CRIT",
}

MISS_EVENTS = {"MISS", "DODGE", "PARRY", "IMMUNE", "REFLECT", "EVADE", "RESIST_FULL"}


class Report:
    def __init__(self, source: Source, events, encounters, actors, abilities, fights):
        self.source = source
        self._events = events
        self._encounters = [
            Encounter(encounter["id"], encounter["name"]) for encounter in encounters
        ]
        self._actors = actors
        self._abilities = abilities
        self._fights = fights

    def get_fight(self, encounter_name):
        for encounter in self._encounters:
            if encounter.name == encounter_name:
                break
        else:
            raise Exception(f"No encounter with name: {encounter_name}")

        for fight in self._fights:
            # Assumes one successful fight per encounter
            if fight["encounterID"] == encounter.id:
                return Fight(
                    self,
                    encounter,
                    fight["startTime"],
                    fight["endTime"],
                    [event for event in self._events if fight["id"] == event["fight"]],
                )
        else:
            raise Exception(f"No fight found for encounter: {encounter_name}")

    def get_actor_name(self, actor_id: int):
        for actor in self._actors:
            if actor["id"] == actor_id:
                return actor["name"]
        else:
            raise Exception(f"No actor name found for id: {actor_id}")

    def get_ability_name(self, ability_id: int):
        for ability in self._abilities:
            if ability["gameID"] == ability_id:
                return ability["name"]
        else:
            raise Exception(f"No ability name found for id: {ability_id}")


class Fight:
    def __init__(
        self,
        report: Report,
        encounter: Encounter,
        start_time: int,
        end_time: int,
        events,
    ):
        self._report = report
        self.encounter = encounter
        self.start_time = start_time
        self.end_time = end_time
        self.events = [self._normalize_event(event) for event in events]
        self._fix_cotg()
        self._add_rp()

    @property
    def source(self):
        return self._report.source

    def _fix_cotg(self):
        """
        WOW combat log is not correctly emitting events for curse of the grave
        the advanced combat log eventually (after a few events, usually) updates
        to correctly have the new RP.

        We fix the events in between the first obliterate until the next event with
        an updated RP value, which we assume is the right one
        :return:
        """
        stated_rp = None

        for event in self.events:
            if event["type"] == "resourcechange" and event["ability"] in (
                "Obliterate",
                "Fingers of the Damned",
            ):
                stated_rp = event["runic_power"]
                event["runic_power"] += 50
            elif "runic_power" in event:
                if event["runic_power"] == stated_rp:
                    event["runic_power"] += 50
                else:
                    stated_rp = None

            if event.get("runic_power"):
                event["runic_power"] = min(event["runic_power"], 1300)

    def _add_rp(self):
        last_event = None

        for event in self.events:
            if not event.get("runic_power"):
                runic_power = last_event["runic_power"] if last_event else 0
                event["runic_power"] = runic_power
            last_event = event

    def _normalize_event(self, event):
        normalized_event = {**event}
        normalized_event["timestamp"] = event["timestamp"] - self.start_time

        if "sourceID" in event:
            normalized_event["source"] = self._report.get_actor_name(
                normalized_event["sourceID"]
            )
        if "targetID" in event:
            normalized_event["target"] = self._report.get_actor_name(
                normalized_event["targetID"]
            )
        if "abilityGameID" in event:
            normalized_event["ability"] = self._report.get_ability_name(
                event["abilityGameID"]
            )
            if event["abilityGameID"] == 50842:
                normalized_event["ability"] = "Pestilence"
            if event["abilityGameID"] == 51271:
                normalized_event["ability"] = "Unbreakable Armor"
        if "hitType" in event:
            normalized_event["hitType"] = HIT_TYPES[event["hitType"]]
            normalized_event["is_miss"] = normalized_event["hitType"] in MISS_EVENTS
        if "classResources" in event:
            for resource in event["classResources"]:
                if resource["type"] == 6:
                    normalized_event["runic_power"] = resource["amount"]

        return normalized_event
