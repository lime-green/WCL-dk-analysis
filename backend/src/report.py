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
        rankings,
        combatant_info,
        encounters,
        actors,
        abilities,
        fights,
    ):
        self.source = source
        self._events = events
        self._rankings = self._parse_rankings(rankings)
        self._combatant_info = combatant_info
        self._encounters = {
            encounter["id"]: Encounter(encounter["id"], encounter["name"])
            for encounter in encounters
        }
        self._actors = {actor["id"]: actor for actor in actors}
        self._abilities = abilities
        self._fights = fights

    def _parse_rankings(self, rankings):
        ret = {}

        for fight_ranking in rankings:
            fight_id = fight_ranking["fightID"]
            ret[fight_id] = {
                "player_rankings": [],
                "fight_ranking": {
                    "speed_percentile": fight_ranking["speed"]["rankPercent"],
                    "execution_percentile": fight_ranking["execution"]["rankPercent"],
                },
            }

            for ranking in fight_ranking["roles"]["dps"]["characters"]:
                ranking = {
                    "name": ranking["name"],
                    "dps": ranking["amount"],
                    "rank_percentile": ranking["rankPercent"],
                }
                ret[fight_id]["player_rankings"].append(ranking)

        return ret

    def get_fight(self, fight_id):
        for fight in self._fights:
            # Assumes one successful fight per encounter
            if fight["id"] == fight_id:
                combatant_info = [
                    c for c in self._combatant_info if c["fight"] == fight["id"]
                ]
                assert combatant_info

                fight_rankings = self._rankings[fight["id"]]
                for player_ranking in fight_rankings["player_rankings"]:
                    if player_ranking["name"] == self.source.name:
                        fight_rankings = {
                            "player_ranking": player_ranking,
                            "fight_ranking": fight_rankings["fight_ranking"],
                        }
                        break
                else:
                    raise Exception("No rankings found for fight")

                return Fight(
                    self,
                    self._encounters[fight["encounterID"]],
                    fight["startTime"],
                    fight["endTime"],
                    [event for event in self._events if fight["id"] == event["fight"]],
                    fight_rankings,
                    combatant_info,
                )
        else:
            raise Exception(f"No fight found with ID: {fight_id}")

    def get_actor_name(self, actor_id: int):
        return self._actors[actor_id]["name"]

    def get_is_boss_actor(self, actor_id: int):
        return self._actors[actor_id]["subType"] == "Boss"

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

    def get_ability_icon(self, ability_id: int):
        if ability_id == 51271:
            return "https://wow.zamimg.com/images/wow/icons/large/inv_armor_helm_plate_naxxramas_raidwarrior_c_01.jpg"
        if ability_id == 50842:
            return "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_plaguecloud.jpg"

        for ability in self._abilities:
            if ability["gameID"] == ability_id:
                return (
                    f'https://wow.zamimg.com/images/wow/icons/large/{ability["icon"]}'
                )
        else:
            if ability_id in (28878, 6562):
                return "https://wow.zamimg.com/images/wow/icons/large/inv_helmet_21.jpg"
            if ability_id == 393387:
                return "https://wow.zamimg.com/images/wow/icons/large/spell_nature_unyeildingstamina.jpg"
            raise Exception(f"No ability icon found for id: {ability_id}")

    def get_ability_type(self, ability_id: int):
        for ability in self._abilities:
            if ability["gameID"] == ability_id:
                return int(ability["type"])
        else:
            raise Exception(f"No ability icon found for id: {ability_id}")


class Fight:
    def __init__(
        self,
        report: Report,
        encounter: Encounter,
        start_time: int,
        end_time: int,
        events,
        rankings,
        combatant_info,
    ):
        self._report = report
        self.encounter = encounter
        self._global_start_time = start_time
        self._global_end_time = end_time
        self.start_time = 0
        self.end_time = end_time - start_time
        self._combatant_info_lookup = {c["sourceID"]: c for c in combatant_info}
        self.rankings = rankings

        self.events = [self._normalize_event(event) for event in events]
        self._fix_cotg()
        self._add_rp()
        self.events = self._coalesce()
        self._add_proc_consumption()

    @property
    def source(self):
        return self._report.source

    def get_combatant_info(self, source_id: int):
        combatant_info = self._combatant_info_lookup[source_id]
        for aura in combatant_info["auras"]:
            if "name" not in aura:
                aura["name"] = self._report.get_ability_name(aura["ability"])
            aura["ability_icon"] = self._report.get_ability_icon(aura["ability"])
        return combatant_info

    def _add_proc_consumption(self):
        auras = self.get_combatant_info(self.source.id)["auras"]
        has_rime = False
        has_km = False

        for aura in auras:
            name = aura.get("name")
            if name == "Rime":
                has_rime = True
            elif name == "Killing Machine":
                has_km = True

        for event in self.events:
            if event["type"] in ("applybuff", "refreshbuff", "removebuff"):
                if event["ability"] == "Rime":
                    has_rime = event["type"] != "removebuff"
                if event["ability"] == "Killing Machine":
                    has_km = event["type"] != "removebuff"

            if event["type"] == "cast":
                event["consumes_km"] = False
                event["consumes_rime"] = False

            if event["type"] == "cast" and event["ability"] in (
                "Frost Strike",
                "Howling Blast",
            ):
                if has_rime and event["ability"] == "Howling Blast":
                    event["consumes_rime"] = True
                if has_km:
                    event["consumes_km"] = True

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

            event["runic_power_waste"] += max(0, event["runic_power"] - 1300)
            event["runic_power"] = min(1300, event["runic_power"])

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
                    # Need a higher threshold here, it can take a while
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
                    event["num_targets"] = 1
                    # Go through subsequent events to coalesce miss into this event
                    for next_event in self.events[i + 1 :]:  # noqa
                        if (
                            next_event["type"] == "damage"
                            and next_event["abilityGameID"] == event["abilityGameID"]
                            and abs(next_event["timestamp"] - event["timestamp"]) < 100
                            and next_event.get("sourceInstance")
                            == event.get("sourceInstance")
                        ):
                            if event["targetID"] != next_event["targetID"]:
                                event["num_targets"] += 1

                            is_miss = next_event["is_miss"]
                            hit_type = next_event["hitType"]
                            extra.update(is_miss=is_miss, hit_type=hit_type)
                    if "is_miss" not in extra:
                        extra.update(is_miss=False, hit_type="NO_DAMAGE_EVENT")

                # Go through subsequent events to coalesce RP into this event
                for next_event in self.events[i + 1 :]:  # noqa
                    if next_event["timestamp"] - event["timestamp"] > 900:
                        break

                    if next_event["runic_power"] != event["runic_power"]:
                        if next_event["runic_power"] < event["runic_power"]:
                            break

                        # We want to get the last change event of the group
                        event["runic_power"] = next_event["runic_power"]

                # Coalesce runic_power_waste
                for next_event in self.events[i + 1 :]:  # noqa
                    if next_event["timestamp"] - event["timestamp"] > 900:
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
                    "ability_icon": event["ability_icon"],
                    "ability_type": event["ability_type"],
                    "type": event["type"],
                    "source": event["source"],
                    "sourceID": event["sourceID"],
                    "target": event["target"],
                    "targetID": event["targetID"],
                    "rune_cost": event["rune_cost"],
                    "runic_power": event["runic_power"],
                    "runic_power_waste": event.get("runic_power_waste", 0),
                    "modifies_runes": event["modifies_runes"],
                    "num_targets": event.get("num_targets", 0),
                    **extra,
                }
            events.append(event)
        return events

    def _normalize_event(self, event):
        normalized_event = {**event}
        normalized_event["timestamp"] = event["timestamp"] - self._global_start_time

        if "abilityGameID" in event:
            normalized_event["ability_icon"] = (
                self._report.get_ability_icon(event["abilityGameID"]),
            )
            normalized_event["ability_type"] = self._report.get_ability_type(
                event["abilityGameID"]
            )
        if "sourceID" in event:
            normalized_event["source"] = self._report.get_actor_name(
                normalized_event["sourceID"]
            )
        if "targetID" in event:
            normalized_event["target"] = self._report.get_actor_name(
                normalized_event["targetID"]
            )
            normalized_event["target_is_boss"] = self._report.get_is_boss_actor(
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

        normalized_event["modifies_runes"] = False
        if normalized_event.get("rune_cost") or normalized_event.get("ability") in (
            "Blood Tap",
            "Empower Rune Weapon",
        ):
            normalized_event["modifies_runes"] = True

        if "waste" in event and event["resourceChangeType"] == 6:
            normalized_event["runic_power_waste"] = event["waste"] * 10

        return normalized_event