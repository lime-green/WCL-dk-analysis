import itertools
import logging
from dataclasses import dataclass, field
from typing import Set


@dataclass
class Encounter:
    id: int
    name: str


@dataclass
class Source:
    id: int
    name: str
    pets: Set[int] = field(default_factory=lambda: set())


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
    9: "DEFLECT",
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

SPELL_TRANSLATIONS = {
    55775: "Swordguard Embroidery",
    60229: "Greatness",
    49909: "Icy Touch",
    49921: "Plague Strike",
    54758: "Hyperspeed Acceleration",
    51425: "Obliterate",
    55268: "Frost Strike",
    51411: "Howling Blast",
    49930: "Blood Strike",
    57623: "Horn of Winter",
    49895: "Death Coil",
    49938: "Death and Decay",
    56815: "Rune Strike",
    49941: "Blood Boil",
    63560: "Ghoul Frenzy",
}


class Report:
    def __init__(
        self,
        source: Source,
        events,
        deaths,
        rankings,
        combatant_info,
        encounters,
        actors,
        abilities,
        fights,
    ):
        self.source = source
        self._events = events
        self._deaths = {death["targetID"]: death for death in deaths}
        self._rankings = self._parse_rankings(rankings)
        self._combatant_info = combatant_info
        self._encounters = {
            encounter["id"]: Encounter(encounter["id"], encounter["name"])
            for encounter in encounters
        }
        self._actors = {actor["id"]: actor for actor in actors}
        self._abilities = abilities
        self._fights = {fight["id"]: fight for fight in fights}

        _boss_fights = [fight for fight in fights if fight["encounterID"] != 0]
        if _boss_fights:
            self._last_fight = _boss_fights[-1]
        else:
            self._last_fight = fights[-1]

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

            for ranking in itertools.chain(
                fight_ranking["roles"]["dps"]["characters"],
                fight_ranking["roles"]["tanks"]["characters"],
                fight_ranking["roles"]["healers"]["characters"],
            ):
                ranking = {
                    "name": ranking["name"],
                    "dps": ranking["amount"],
                    "rank_percentile": ranking["rankPercent"],
                }
                ret[fight_id]["player_rankings"].append(ranking)

        return ret

    def get_fight(self, fight_id):
        if fight_id == -1:
            fight_id = self._last_fight["id"]

        fight = self._fights[fight_id]
        combatant_info = [c for c in self._combatant_info if c["fight"] == fight["id"]]

        fight_rankings = self._rankings.get(fight["id"], {})
        for player_ranking in fight_rankings.get("player_rankings", []):
            if player_ranking["name"] == self.source.name:
                fight_rankings = {
                    "player_ranking": player_ranking,
                    "fight_ranking": fight_rankings["fight_ranking"],
                }
                break

        encounter = self._encounters.get(fight["encounterID"])
        if not encounter:
            actor_id = fight["enemyNPCs"][0]["id"]
            encounter = Encounter(0, self.get_actor_name(actor_id))

        return Fight(
            self,
            fight_id,
            encounter,
            fight["startTime"],
            fight["endTime"],
            [event for event in self._events if fight["id"] == event["fight"]],
            fight_rankings,
            combatant_info,
        )

    def get_actor_name(self, actor_id: int):
        return self._actors[actor_id]["name"]

    def is_owner_pet(self, actor_id: int):
        return actor_id in self.source.pets

    def get_is_boss_actor(self, actor_id: int):
        return self._actors[actor_id]["subType"] == "Boss"

    def get_target_death(self, actor_id: int):
        return self._deaths.get(actor_id, {}).get("timestamp")

    def get_ability_name(self, ability_id: int):
        if ability_id in SPELL_TRANSLATIONS:
            return SPELL_TRANSLATIONS[ability_id]

        if ability_id == 48266:
            return "Blood Presence"
        if ability_id in (48265, 49772):
            return "Unholy Presence"
        if ability_id == 48263:
            return "Frost Presence"
        for ability in self._abilities:
            if ability["gameID"] == ability_id:
                return ability["name"]
        else:
            if ability_id == 53748:
                return "Mighty Strength"
            if ability_id == 48470:
                return "Gift of the Wild"
            if ability_id == 53760:
                return "Flask of Endless Rage"
            if ability_id == 53758:
                return "Flask of Stoneblood"
            if ability_id == 25898:
                return "Greater Blessing of Kings"
            if ability_id in (57371, 57399, 57079, 65414, 57111, 57356, 57294):
                return "Well Fed"
            if ability_id == 24383:
                return "Swiftness of Zanza"
            if ability_id in (28878, 6562):
                return "Heroic Presence"
            if ability_id in (393387, 24932):
                return "Leader of the Pack"
            if ability_id == 53762:
                return "Indestructible"
            logging.warning(f"No ability name found for id: {ability_id}")
            return "Unknown"

    def get_ability_icon(self, ability_id: int):
        if ability_id == 48266:
            return "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_bloodpresence.jpg"
        if ability_id in (48265, 49772):
            return "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_unholypresence.jpg"
        if ability_id == 48263:
            return "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_frostpresence.jpg"
        if ability_id == 51271:
            return "https://wow.zamimg.com/images/wow/icons/large/inv_armor_helm_plate_naxxramas_raidwarrior_c_01.jpg"
        if ability_id == 50842:
            return "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_plaguecloud.jpg"
        if ability_id == 60229:
            return "https://wow.zamimg.com/images/wow/icons/large/inv_inscription_tarotgreatness.jpg"
        if ability_id == 63560:
            return (
                "https://wow.zamimg.com/images/wow/icons/large/ability_ghoulfrenzy.jpg"
            )

        for ability in self._abilities:
            if ability["gameID"] == ability_id:
                return (
                    f'https://wow.zamimg.com/images/wow/icons/large/{ability["icon"]}'
                )
        else:
            if ability_id == 53748:
                return (
                    "https://wow.zamimg.com/images/wow/icons/large/inv_potion_165.jpg"
                )
            if ability_id == 48470:
                return "https://wow.zamimg.com/images/wow/icons/large/spell_nature_giftofthewild.jpg"
            if ability_id == 53760:
                return "https://wow.zamimg.com/images/wow/icons/large/inv_alchemy_endlessflask_06.jpg"
            if ability_id == 53758:
                return "https://wow.zamimg.com/images/wow/icons/large/inv_alchemy_endlessflask_05.jpg"
            if ability_id == 25898:
                return "https://wow.zamimg.com/images/wow/icons/large/spell_magic_greaterblessingofkings.jpg"
            if ability_id in (57371, 57399, 57079, 65414, 57111, 57356, 57294):
                return (
                    "https://wow.zamimg.com/images/wow/icons/large/spell_misc_food.jpg"
                )
            if ability_id == 24383:
                return "https://wow.zamimg.com/images/wow/icons/large/inv_potion_31.jpg"
            if ability_id in (28878, 6562):
                return "https://wow.zamimg.com/images/wow/icons/large/inv_helmet_21.jpg"
            if ability_id in (393387, 24932):
                return "https://wow.zamimg.com/images/wow/icons/large/spell_nature_unyeildingstamina.jpg"
            if ability_id == 53762:
                return "https://wow.zamimg.com/images/wow/icons/large/inv_alchemy_elixir_empty.jpg"
            logging.warning(f"No ability icon found for id: {ability_id}")
            return "https://wow.zamimg.com/images/wow/icons/large/trade_engineering.jpg"

    def get_ability_type(self, ability_id: int):
        for ability in self._abilities:
            if ability["gameID"] == ability_id:
                return int(ability["type"])
        else:
            raise Exception(f"No ability type found for id: {ability_id}")


class Fight:
    def __init__(
        self,
        report: Report,
        fight_id,
        encounter: Encounter,
        start_time: int,
        end_time: int,
        events,
        rankings,
        combatant_info,
    ):
        self._fight_id = fight_id
        self._report = report
        self.encounter = encounter
        self._global_start_time = start_time
        self._global_end_time = end_time
        self.start_time = 0
        self.end_time = end_time - start_time
        self.duration = self.end_time - self.start_time
        self._combatant_info_lookup = {c["sourceID"]: c for c in combatant_info}
        self.rankings = rankings

        self.events = [self._normalize_event(event) for event in events]
        self._fix_cotg()
        self._add_rp()
        self.events = self._coalesce()
        self._add_proc_consumption()

        if encounter.name == "Razorscale":
            self.events = self._fix_razorscale()

    @property
    def source(self):
        return self._report.source

    def get_combatant_info(self, source_id: int):
        # It's possible there's no combatant info sometimes (WCL bug?)
        if source_id not in self._combatant_info_lookup:
            return {}

        combatant_info = self._combatant_info_lookup[source_id]
        for aura in combatant_info["auras"]:
            if "name" not in aura:
                aura["name"] = self._report.get_ability_name(aura["ability"])
            aura["ability_icon"] = self._report.get_ability_icon(aura["ability"])
        return combatant_info

    def _fix_razorscale(self):
        for event in self.events:
            if event.get("target") == "Razorscale":
                first_razorscale_event = event["timestamp"]
                break
        else:
            raise Exception("Razorscale event not found")

        filtered_events = []

        for event in self.events:
            if event["timestamp"] >= first_razorscale_event:
                event["timestamp"] -= first_razorscale_event
                filtered_events.append(event)
        self.duration = filtered_events[-1]["timestamp"]

        return filtered_events

    def _add_proc_consumption(self):
        auras = self.get_combatant_info(self.source.id).get("auras", [])
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
                            else:  # only show misses on same target
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
                    "target_dies_at": event["target_dies_at"],
                    "rune_cost": event["rune_cost"],
                    "runes_used": event["runes_used"],
                    "runic_power": event["runic_power"],
                    "runic_power_waste": event.get("runic_power_waste", 0),
                    "modifies_runes": event["modifies_runes"],
                    "num_targets": event.get("num_targets", 0),
                    "is_owner_pet_source": event["is_owner_pet_source"],
                    "is_owner_pet_target": event["is_owner_pet_target"],
                    **extra,
                }
            events.append(event)
        return events

    def _normalize_time(self, timestamp):
        if timestamp:
            return timestamp - self._global_start_time
        else:
            return 0

    def _get_rune_resource_types(self, normalized_event):
        frost_type = 21
        unholy_type = 22

        if normalized_event["ability"] == "Obliterate":
            frost_type = 22
            unholy_type = 21

        return {"frost": frost_type, "unholy": unholy_type}

    def _normalize_event(self, event):
        normalized_event = {**event}
        normalized_event["timestamp"] = self._normalize_time(event["timestamp"])

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
            normalized_event["target_dies_at"] = self._normalize_time(
                self._report.get_target_death(normalized_event["targetID"])
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
            normalized_event["runes_used"] = {**NO_RUNES}
        if "classResources" in event:
            rune_resource_types = self._get_rune_resource_types(normalized_event)

            for resource in event["classResources"]:
                if resource["type"] == 6:
                    normalized_event["runic_power"] = resource["amount"]
                    if resource.get("cost"):
                        normalized_event["runic_power_cost"] = resource["cost"]
                if resource["type"] == 20:
                    normalized_event["rune_cost"]["blood"] += resource["cost"]
                    normalized_event["runes_used"]["blood"] += min(
                        resource["amount"], resource["cost"]
                    )
                if resource["type"] == rune_resource_types["frost"]:
                    normalized_event["rune_cost"]["frost"] += resource["cost"]
                    normalized_event["runes_used"]["frost"] += min(
                        resource["amount"], resource["cost"]
                    )
                if resource["type"] == rune_resource_types["unholy"]:
                    normalized_event["rune_cost"]["unholy"] += resource["cost"]
                    normalized_event["runes_used"]["unholy"] += min(
                        resource["amount"], resource["cost"]
                    )
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

        if (
            normalized_event["type"] == "resourcechange"
            and normalized_event["ability"] == "Anti-Magic Shell"
        ):
            runic_power_gain = event["resourceChange"] - event["waste"]
            normalized_event["runic_power_gained_ams"] = runic_power_gain * 10

        normalized_event["is_owner_pet_source"] = self._report.is_owner_pet(
            normalized_event["sourceID"]
        )
        normalized_event["is_owner_pet_target"] = False
        if normalized_event.get("targetID"):
            normalized_event["is_owner_pet_target"] = self._report.is_owner_pet(
                normalized_event["targetID"]
            )

        return normalized_event
