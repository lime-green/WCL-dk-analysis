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

NO_RUNES = {"blood": 0, "frost": 0, "unholy": 0}


class Report:
    def __init__(
        self,
        source: Source,
        events,
        combatant_info,
        encounters,
        actors,
        abilities,
        fights,
    ):
        self.source = source
        self._events = events
        self._combatant_info = combatant_info
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
                combatant_info = [
                    c for c in self._combatant_info if c["fight"] == fight["id"]
                ]
                assert combatant_info

                return Fight(
                    self,
                    encounter,
                    fight["startTime"],
                    fight["endTime"],
                    [event for event in self._events if fight["id"] == event["fight"]],
                    combatant_info,
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
            if ability_id in (28878, 6562):
                return "Heroic Presence"
            if ability_id == 393387:
                return "Leader of the Pack"
            raise Exception(f"No ability name found for id: {ability_id}")


class Fight:
    def __init__(
        self,
        report: Report,
        encounter: Encounter,
        start_time: int,
        end_time: int,
        events,
        combatant_info,
    ):
        self._report = report
        self.encounter = encounter
        self._global_start_time = start_time
        self._global_end_time = end_time
        self.start_time = 0
        self.end_time = end_time - start_time
        self._combatant_info_lookup = {c["sourceID"]: c for c in combatant_info}

        self.events = [self._normalize_event(event) for event in events]
        self._fix_cotg()
        self._add_rp()
        self.events = self._coalesce()

    @property
    def source(self):
        return self._report.source

    def get_combatant_info(self, source_id: int):
        combatant_info = self._combatant_info_lookup[source_id]
        for aura in combatant_info["auras"]:
            if "name" not in aura:
                aura["name"] = self._report.get_ability_name(aura["ability"])
        return combatant_info

    def _fix_cotg(self):
        """
        WOW combat log is not correctly emitting events for curse of the grave
        the advanced combat log eventually (after a few events, usually) updates
        to correctly have the new RP.
        :return:
        """
        stated_rp = None

        def _update_waste(event):
            if "runic_power_waste" not in event:
                event["runic_power_waste"] = 0

            event["runic_power_waste"] += event["runic_power"] - 1300
            event["runic_power"] = min(event["runic_power"], 1300)

        for i, event in enumerate(self.events):
            if (
                event["type"] == "resourcechange"
                and event["ability"] == "Obliterate"
                and event["resourceChangeType"] == 6
            ):
                stated_rp = event["runic_power"]
                event["runic_power"] += 50
                _update_waste(event)

                for next_event in self.events[i + 1 :]:  # noqa
                    if next_event["timestamp"] - event["timestamp"] > 500:
                        break

                    if "runic_power" in event:
                        if next_event.get("runic_power") == stated_rp:
                            next_event["runic_power"] += 50
                            # Only add to the waste if it's not already over cap
                            if next_event[
                                "type"
                            ] == "resourcechange" and not next_event.get(
                                "runic_power_waste"
                            ):
                                next_event["runic_power_waste"] = max(
                                    0, next_event["runic_power"] - 1300
                                )
                            next_event["runic_power"] = min(
                                1300, next_event["runic_power"]
                            )

    def _add_rp(self):
        last_event = None

        for event in self.events:
            if not event.get("runic_power"):
                runic_power = last_event["runic_power"] if last_event else 0
                event["runic_power"] = runic_power
            last_event = event

    def _coalesce(self):
        """
        Merge multiple events into each other in two cases:
        - Damage events to their respective cast event to detect misses
        - RP events to their respective cast event to track RP gains / losses
        """
        events = []

        for i, event in enumerate(self.events):
            extra = {}

            if event["type"] == "cast":
                # Check if we're actually hitting a target
                if event["targetID"] != -1:
                    # Go through subsequent events to coalesce miss into this event
                    for next_event in self.events[i + 1 :]:  # noqa
                        if (
                            next_event["type"] == "damage"
                            and next_event["abilityGameID"] == event["abilityGameID"]
                            and abs(next_event["timestamp"] - event["timestamp"]) < 100
                        ):
                            is_miss = next_event["is_miss"]
                            hit_type = next_event["hitType"]
                            extra.update(is_miss=is_miss, hit_type=hit_type)
                            break
                    else:
                        extra.update(is_miss=False, hit_type="NO_DAMAGE_EVENT")

                # Go through subsequent events to coalesce RP into this event
                for next_event in self.events[i + 1 :]:  # noqa
                    if next_event["timestamp"] - event["timestamp"] > 100:
                        break

                    if next_event["runic_power"] != event["runic_power"]:
                        if next_event["runic_power"] < event["runic_power"]:
                            break

                        # We want to get the last change event of the group
                        event["runic_power"] = next_event["runic_power"]

                # Coalesce runic_power_waste
                for next_event in self.events[i + 1 :]:  # noqa
                    if next_event["timestamp"] - event["timestamp"] > 100:
                        break

                    if next_event.get("runic_power_waste") and (
                        next_event["abilityGameID"] == event["abilityGameID"]
                        or (
                            event["ability"] == "Obliterate"
                            and next_event["ability"] == "Fingers of the Damned"
                        )
                    ):
                        event["runic_power_waste"] = (
                            event.get("runic_power_waste", 0)
                            + next_event["runic_power_waste"]
                        )

                # Spells like frost strike don't seem to immediately use the RP
                if event.get("runic_power_cost", 0) > 0:
                    for next_event in self.events[i + 1 :]:  # noqa
                        if next_event["runic_power"] != event["runic_power"]:
                            if next_event["runic_power"] > event["runic_power"]:
                                break
                            event["runic_power"] = next_event["runic_power"]
                            break

                event = {
                    "timestamp": event["timestamp"],
                    "ability": event["ability"],
                    "abilityGameID": event["abilityGameID"],
                    "type": event["type"],
                    "source": event["source"],
                    "sourceID": event["sourceID"],
                    "target": event["target"],
                    "targetID": event["targetID"],
                    "rune_cost": event["rune_cost"],
                    "runic_power": event["runic_power"],
                    "runic_power_waste": event.get("runic_power_waste", 0),
                    **extra,
                }
            events.append(event)
        return events

    def _normalize_event(self, event):
        normalized_event = {**event}
        normalized_event["timestamp"] = event["timestamp"] - self._global_start_time

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
        if event["type"] == "cast":
            normalized_event["rune_cost"] = {**NO_RUNES}
        if "classResources" in event:
            for resource in event["classResources"]:
                if resource["type"] == 6:
                    normalized_event["runic_power"] = resource["amount"]
                    if resource.get("cost"):
                        normalized_event["runic_power_cost"] = resource["cost"]
                if resource["type"] == 20:
                    normalized_event["rune_cost"]["blood"] += 1
                if resource["type"] == 21:
                    normalized_event["rune_cost"]["frost"] += 1
                if resource["type"] == 22:
                    normalized_event["rune_cost"]["unholy"] += 1
            if normalized_event.get("rune_cost") == NO_RUNES:
                normalized_event["rune_cost"] = None
        if "waste" in event:
            normalized_event["runic_power_waste"] = event["waste"] * 10

        return normalized_event
