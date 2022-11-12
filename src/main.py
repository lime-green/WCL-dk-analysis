import pickle

from client import WCLClient
from report import Fight, Report


def fetch(report_code, character, zone_id):
    client = WCLClient(
        "***REMOVED***",
        "***REMOVED***",
    )
    report = client.query(report_code, character, zone_id)

    with open("../data.pickle", "wb") as f:
        pickle.dump(report, f)


def load():
    with open("../data.pickle", "rb") as f:
        return pickle.load(f)


class Analyzer:
    def __init__(self, fight: Fight):
        self._fight = fight
        self._events = self._get_events()

    def _get_events(self):
        events = []

        for i, event in enumerate(self._fight.events):
            if event.get("abilityGameID") == 1:  # melee
                continue

            # We're neither the source or the target (eg: ghouls attacking boss)
            if (
                event["sourceID"] != self._fight.source
                and event["targetID"] != self._fight.source
            ):
                continue

            extra = {}
            if event["type"] == "cast":
                if event["targetID"] != -1:
                    for next_event in self._fight.events[i + 1 :]:  # noqa
                        if (
                            next_event["type"] == "damage"
                            and next_event["abilityGameID"] == event["abilityGameID"]
                        ):
                            is_miss = next_event["is_miss"]
                            hit_type = next_event["hitType"]
                            extra.update(is_miss=is_miss, hit_type=hit_type)
                            break
                    else:
                        extra.update(is_miss=False, hit_type="NO_DAMAGE_EVENT")

                event = {
                    "timestamp": event["timestamp"],
                    "ability": event["ability"],
                    "abilityGameID": event["abilityGameID"],
                    "type": event["type"],
                    "source": event["source"],
                    "target": event["target"],
                    **extra,
                }
                events.append(event)
        return events


def analyze(report: Report):
    fight = report.get_fight("Patchwerk")
    analyzer = Analyzer(fight)
    for event in analyzer._events:
        print(event)


report_code = "zjKL827F1DVrgv4B"
character = "Sails"
zone_id = 1015

# fetch(report_code, character, zone_id)
analyze(load())
