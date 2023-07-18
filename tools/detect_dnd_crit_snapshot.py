import asyncio
import os
import pickle
import traceback
import urllib.parse
from functools import partial

from requests import Session

from client import get_client, WCLClient
from report import Fight


class Client:
    BASE_URL = "https://classic.warcraftlogs.com/v1/"

    def __init__(self, api_key):
        self._session = Session()
        self._api_key = api_key

    def get_zones(self):
        return self._get("zones")

    def get_encounters_for_zone(self, zone_name):
        zones = self.get_zones()
        for zone in zones:
            if zone["name"] == zone_name:
                return zone["encounters"]
        else:
            raise ValueError(f"Unknown zone {zone_name}")

    def get_fight(self, report_id):
        return self._get(f"report/fights/{report_id}")

    def get_source_id(self, report_id, source_name):
        fight = self.get_fight(report_id)
        for actor in fight["friendlies"]:
            if actor["name"] == source_name:
                return actor["id"]
        else:
            raise ValueError(f"Unknown source {source_name}")

    def get_rankings_for_encounter(self, encounter_id, **kwargs):
        return self._get(f"rankings/encounter/{encounter_id}", params=kwargs)

    def _get(self, path, params=None):
        path = urllib.parse.urljoin(self.BASE_URL, path)
        response = self._session.get(path, params={"api_key": self._api_key, **(params or {})})
        response.raise_for_status()
        return response.json()


def exhaust_all_pages(fetcher):
    page = 1
    while True:
        response = fetcher(page=page)
        yield response
        if not response["hasMorePages"] or page >= 50:
            break
        page += 1


async def get_report(report_id, fight_id, source_id):
    async with get_client() as client:
        return await client.query(report_id, fight_id, source_id)


class CritTickCounter:
    def __init__(self, num_crit, total_ticks):
        self.num_crit = num_crit
        self.total_ticks = total_ticks

    def __add__(self, other):
        return CritTickCounter(
            self.num_crit + other.num_crit,
            self.total_ticks + other.total_ticks,
        )

    @property
    def crit_rate(self):
        return self.num_crit / self.total_ticks if self.total_ticks else 0


def analyze_fight(fight: Fight):
    events = fight.events
    has_crit_buff = False
    snapshotted = False
    snapshotted_ticks = []
    unsnapshotted_ticks = []
    unsnapshotted_buffed_ticks = []
    buffed_ticks = []
    unbuffed_ticks = []
    total_ticks = 0

    for event in events:
        if event.get("ability") == "Implosion":
            if event["type"] in ("applybuff", "refreshbuff"):
                has_crit_buff = True
            elif event["type"] == "removebuff":
                has_crit_buff = False
            else:
                raise ValueError(f"Unknown event type {event['type']}")
        elif event.get("ability") == "Death and Decay":
            if event["type"] == "damage":
                total_ticks += 1

                if has_crit_buff:
                    buffed_ticks.append(event["is_crit"])
                else:
                    unbuffed_ticks.append(event["is_crit"])

                if snapshotted:
                    snapshotted_ticks.append(event["is_crit"])
                else:
                    unsnapshotted_ticks.append(event["is_crit"])
                    if has_crit_buff:
                        unsnapshotted_buffed_ticks.append(event["is_crit"])
            elif event["type"] == "cast":
                snapshotted = has_crit_buff

    snapshot_crit = CritTickCounter(len([x for x in snapshotted_ticks if x]), len(snapshotted_ticks))
    buffed_crit = CritTickCounter(len([x for x in buffed_ticks if x]), len(buffed_ticks))
    unbuffed_crit = CritTickCounter(len([x for x in unbuffed_ticks if x]), len(unbuffed_ticks))
    unsnapshotted_crit = CritTickCounter(len([x for x in unsnapshotted_ticks if x]), len(unsnapshotted_ticks))
    unsnapshotted_buffed_crit_rate = CritTickCounter(len([x for x in unsnapshotted_buffed_ticks if x]), len(unsnapshotted_buffed_ticks))
    return snapshot_crit, buffed_crit, unbuffed_crit, unsnapshotted_crit, unsnapshotted_buffed_crit_rate, total_ticks


def detect_dnd_crit_snapshot():
    v1_client = Client(api_key=os.environ["WCL_API_KEY"])
    reports = []

    # if reports.txt exists, load reports from file
    if os.path.exists("reports.txt"):
        with open("reports.txt", "r") as f:
            for line in f.readlines():
                report_id, player_name, fight_id = line.split()
                reports.append((report_id, player_name, int(fight_id)))
    else:
        encounters = v1_client.get_encounters_for_zone("Trial of the Crusader")
        for encounter in encounters:
            print("Encounter", encounter["name"])
            fetcher = partial(v1_client.get_rankings_for_encounter, encounter["id"], **{"class": 1, "spec": 3, "filter": "items.46038"})
            for page in exhaust_all_pages(fetcher):
                print("Page", page["page"])
                for report in page["rankings"]:
                    reports.append((report["reportID"], report["name"], report["fightID"]))

        # save reports to file
        with open("reports.txt", "w") as f:
            for report in reports:
                f.write(f"{report[0]} {report[1]} {report[2]}\n")

    if os.path.exists("fight_map.pickle"):
        with open("fight_map.pickle", "rb") as f:
            fight_map = pickle.load(f)
    else:
        fight_map = {}

        try:
            for i, (report_id, player_name, fight_id) in enumerate(reports):
                source_id = v1_client.get_source_id(report_id, player_name)
                report = asyncio.run(get_report(report_id, fight_id, source_id))
                fight = report.get_fight(fight_id)
                fight_map[(report_id, player_name, fight_id)] = fight

                print(f"Report {i+1}/{len(reports)}")
        except:
            traceback.print_exc()
            print("Saving fight map to file")

        with open("fight_map.pickle", "wb") as f:
            pickle.dump(fight_map, f)

    running_snapshot_crits = CritTickCounter(0, 0)
    running_buffed_crits = CritTickCounter(0, 0)
    running_unbuffed_crits = CritTickCounter(0, 0)
    running_unsnapshotted_crits = CritTickCounter(0, 0)
    running_unsnapshotted_buffed_crits = CritTickCounter(0, 0)
    running_total_ticks = 0
    for fight in fight_map.values():
        snapshot_crit, buffed_crit, unbuffed_crit, unsnapshotted_crit, unsnapshotted_buffed_crit, total_ticks = analyze_fight(fight)
        running_snapshot_crits += snapshot_crit
        running_buffed_crits += buffed_crit
        running_unbuffed_crits += unbuffed_crit
        running_unsnapshotted_crits += unsnapshotted_crit
        running_unsnapshotted_buffed_crits += unsnapshotted_buffed_crit

        running_total_ticks += total_ticks
        print("Snapshot crit rate", snapshot_crit.crit_rate)
        print("Unsnapshotted crit rate", unsnapshotted_crit.crit_rate)
        print("Unsnapshotted buffed crit rate", unsnapshotted_buffed_crit.crit_rate)
        print("Buffed crit rate", buffed_crit.crit_rate)
        print("Unbuffed crit rate", unbuffed_crit.crit_rate)
        print("Total ticks", total_ticks)

    print("Overall total ticks: ", running_total_ticks)
    print(f"Overall snapshot crit rate (n={running_snapshot_crits.total_ticks})", running_snapshot_crits.crit_rate)
    print(f"Overall unsnapshotted crit rate (n={running_unsnapshotted_crits.total_ticks})", running_unsnapshotted_crits.crit_rate)
    print(f"Overall unsnapshotted buffed crit rate (n={running_unsnapshotted_buffed_crits.total_ticks})", running_unsnapshotted_buffed_crits.crit_rate)
    print(f"Overall buffed crit rate (n={running_buffed_crits.total_ticks})", running_buffed_crits.crit_rate)
    print(f"Overall unbuffed crit rate (n={running_unbuffed_crits.total_ticks})", running_unbuffed_crits.crit_rate)


if __name__ == "__main__":
    detect_dnd_crit_snapshot()
