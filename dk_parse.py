import json
import pickle
from dataclasses import dataclass
from typing import Dict, List

import requests


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


class Report:
    def __init__(self, source: Source, events, encounters, actors, abilities, fights):
        self._source = source
        self._events = events
        self._encounters = [Encounter(encounter["id"], encounter["name"]) for encounter in encounters]
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
    def __init__(self, report: Report, encounter: Encounter, start_time: int, end_time: int, events):
        self._report = report
        self.encounter = encounter
        self.start_time = start_time
        self.end_time = end_time
        self.events = [self._normalize_event(event) for event in events]
        self._fix_cotg()

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
            if event["type"] == "resourcechange" and event["ability"] in ("Obliterate", "Fingers of the Damned"):
                for resource in event["classResources"]:
                    if resource["type"] == 6:
                        stated_rp = resource["amount"]
                        resource["amount"] += 50
            elif "classResources" in event and any(resource["type"] == 6 for resource in event["classResources"]):
                for resource in event["classResources"]:
                    if resource["type"] == 6:
                        if resource["amount"] == stated_rp:
                            resource["amount"] += 50
                        else:
                            stated_rp = None

    def _normalize_event(self, event):
        normalized_event = {**event}
        normalized_event["timestamp"] = event["timestamp"] - self.start_time

        if "sourceID" in event:
            normalized_event["source"] = self._report.get_actor_name(normalized_event["sourceID"])
        if "targetID" in event:
            normalized_event["target"] = self._report.get_actor_name(normalized_event["targetID"])
        if "abilityGameID" in event:
            normalized_event["ability"] = self._report.get_ability_name(event["abilityGameID"])
        if "hitType" in event:
            normalized_event["hitType"] = HIT_TYPES[event["hitType"]]

        return normalized_event


class Client:
    base_url = "https://classic.warcraftlogs.com/api/v2/client"
    client_id = "***REMOVED***"
    client_secret = "***REMOVED***"

    def __init__(self):
        self._session = requests.Session()
        self._auth = None

    def _fetch_events(self, report_code, source_id):
        events = []
        next_page_timestamp = 0
        events_query_t = """
        {
  reportData {
    report(code: "%s") {
			events(killType: Kills, startTime: %s, endTime: 100000000000, sourceID: %s, useActorIDs: true, includeResources: true) {
				nextPageTimestamp
				data
			}
		}
  }
}	
"""
        while next_page_timestamp is not None:
            events_query = events_query_t % (report_code, 0, source_id)
            r = self._query(events_query).json()["data"]["reportData"]["report"]["events"]
            next_page_timestamp = r["nextPageTimestamp"]
            events += r["data"]

        return events

    def query(self, report_code, character):
        metadata_query = """
        {
  reportData {
    report(code: "%s") {
			masterData {
				abilities {
					gameID
					name
					icon
					type
				}
				actors {
					id
					name
					type
				}
			}
			fights(killType: Kills) {
				encounterID
				id
				startTime
				endTime
			}
		}
  }
  worldData {
		zone(id: 1015) {
			encounters {
				id, name
			}
		}
	}
}	
""" % report_code

        metadata = self._query(metadata_query).json()["data"]
        report_metadata = metadata["reportData"]["report"]

        for actor in report_metadata["masterData"]["actors"]:
            if actor["type"] == "Player" and actor["name"] == character:
                source_id = actor["id"]
                break
        else:
            raise Exception("Character not found")

        events = self._fetch_events(report_code, source_id)

        return Report(
            source_id,
            events,
            metadata["worldData"]["zone"]["encounters"],
            report_metadata["masterData"]["actors"],
            report_metadata["masterData"]["abilities"],
            report_metadata["fights"],
        )

    def _query(self, query):
        r = self.session.post(
            self.base_url,
            json={"query": query},
            headers=dict(Authorization=f"Bearer {self._auth}")
        )
        r.raise_for_status()
        return r

    @property
    def session(self):
        if not self._auth:
            r = self._session.post(
                "https://www.warcraftlogs.com/oauth/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
            )
            r.raise_for_status()
            self._auth = r.json()["access_token"]
        return self._session


def fetch(report_code, character):
    report = Client().query(report_code, character)

    with open("data.json", "wb") as f:
        pickle.dump(report, f)


def load():
    with open("data.json", "rb") as f:
        return pickle.load(f)


def analyze(report: Report):
    fight = report.get_fight("Patchwerk")

    for event in fight.events:
        if event["source"] == "Sails":
            print(event)


report_code = "zjKL827F1DVrgv4B"
character = "Sails"
fetch(report_code, character)
analyze(load())





