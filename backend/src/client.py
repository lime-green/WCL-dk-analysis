import logging
from datetime import datetime, timedelta

import aiohttp
import asyncio.exceptions
import sentry_sdk
from report import Report, Source


class WCLClientException(Exception):
    pass


class PrivateReport(WCLClientException):
    pass


class CacheWithExpiry:
    def __init__(self):
        self._cache = {}

    def get(self, key):
        if key not in self._cache:
            return None
        value, expiry = self._cache[key]
        if expiry < datetime.utcnow():
            del self._cache[key]
            return None
        return value

    def set(self, key, value, expiry):
        self._cache[key] = (value, datetime.utcnow() + expiry)


class WCLClient:
    base_url = "https://classic.warcraftlogs.com/api/v2/client"
    _auth = None
    _zones = None
    _cache = CacheWithExpiry()

    def __init__(self, client_id, client_secret):
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self._session.__aexit__(*args)
        self._session = None

    async def _fetch_metadata(self, report_code):
        metadata_query = (
            """
{
  reportData {
    report(code: "%s") {
      endTime
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
          subType
          petOwner
        }
      }
      fights {
        encounterID
        id
        startTime
        endTime
        enemyNPCs {
            id
        }
      }
    }
  }
}
"""
            % report_code
        )
        return (await self._query(metadata_query, "metadata"))["data"]

    async def _is_rankings_available(self, report_code):
        rankings_query = (
            """
{
    reportData {
        report(code: "%s") {
            rankings (
                playerMetric: dps
                fightIDs: []
            )
        }
    }
}
"""
            % report_code
        )
        in_cache = self._cache.get("rankings_available")
        if in_cache is not None:
            return in_cache

        try:
            await self._query(rankings_query, "rankings", timeout=2)
            ret = True
        except asyncio.exceptions.TimeoutError:
            logging.error("Timeout fetching rankings")
            ret = False

        self._cache.set("rankings_available", ret, timedelta(minutes=60))
        return ret

    async def _fetch_events(self, report_code, fight_id, source: Source):
        deaths = []
        events = []
        combatant_info = []
        rankings = []
        next_page_timestamp = 0
        rankings_query = """
rankings(
    playerMetric: dps
    fightIDs: [%(fight_id)s]
)
""" % {"fight_id": fight_id}

        events_query_t = """
{
  reportData {
    report(code: "%(report_code)s") {
      events(
        startTime: %(next_page_timestamp)s
        endTime: 100000000000
        sourceID: %(source_id)s
        useActorIDs: true
        includeResources: true
        fightIDs: [%(fight_id)s]
        limit: 10000
      ) {
        nextPageTimestamp
        data
      }
      deaths: events(
        startTime: 0
        endTime: 100000000000
        useActorIDs: true
        sourceID: -1
        fightIDs: [%(fight_id)s]
        limit: 10000
      ) {
        data
      }
      
      %(rankings_query)s
      
      combatantInfo: events(
        startTime: 0
        endTime: 100000000000
        useActorIDs: true
        dataType: CombatantInfo
        fightIDs: [%(fight_id)s]
        limit: 10000
      ) {
        data
      }
    }
  }
}
"""
        if not await self._is_rankings_available(report_code):
            rankings_query = ""

        while next_page_timestamp is not None:
            events_query = events_query_t % dict(
                report_code=report_code,
                next_page_timestamp=next_page_timestamp,
                source_id=source.id,
                source_name=source.name,
                fight_id=fight_id,
                rankings_query=rankings_query,
            )
            r = (await self._query(events_query, "events"))["data"]["reportData"][
                "report"
            ]

            if next_page_timestamp == 0:
                combatant_info = r["combatantInfo"]["data"]
                if r.get("rankings"):
                    rankings = r["rankings"]["data"]
                deaths = [
                    death for death in r["deaths"]["data"] if death["type"] == "death"
                ]

            next_page_timestamp = r["events"]["nextPageTimestamp"]
            events += r["events"]["data"]

        return events, combatant_info, deaths, rankings

    async def _get_zones(self):
        if not self._zones:
            encounter_query = """
    {
        worldData {
            zones {
                encounters {
                    id
                    name
                }
            }
        }
    }
            """
            zones = (await self._query(encounter_query, "zones"))["data"]["worldData"][
                "zones"
            ]
            self.__class__._zones = zones
        return self._zones

    async def query(self, report_id, fight_id, source_id):
        zones = await self._get_zones()
        encounters = [encounter for zone in zones for encounter in zone["encounters"]]
        metadata = await self._fetch_metadata(report_id)
        report_metadata = metadata["reportData"]["report"]
        actors = report_metadata["masterData"]["actors"]

        for actor in actors:
            if actor["type"] == "Player" and actor["id"] == source_id:
                source = Source(actor["id"], actor["name"])
                break
        else:
            raise Exception("Character not found")

        # Get pets
        for actor in actors:
            if actor["type"] == "Pet" and actor["petOwner"] == source_id:
                source.pets.add(actor["id"])

        if fight_id == -1:
            boss_fights = [
                fight
                for fight in report_metadata["fights"]
                if fight["encounterID"] != 0
            ]
            if boss_fights:
                fight_id = boss_fights[-1]["id"]
            else:
                fight_id = report_metadata["fights"][-1]["id"]

        events, combatant_info, deaths, rankings = await self._fetch_events(
            report_id, fight_id, source
        )

        return Report(
            source,
            events,
            deaths,
            rankings,
            combatant_info,
            encounters,
            actors,
            report_metadata["masterData"]["abilities"],
            report_metadata["fights"],
            report_metadata["endTime"],
        )

    async def _query(self, query, description, timeout=3):
        session = await self.session()
        with sentry_sdk.start_span(op="http", description=description):
            r = await session.post(
                self.base_url,
                json={"query": query},
                headers=dict(Authorization=f"Bearer {self._auth}"),
                raise_for_status=True,
                timeout=timeout
            )
        json = await r.json()

        if "errors" in json:
            logging.error(json["errors"])

            if (
                json["errors"][0]["message"]
                == "You do not have permission to view this report."
            ):
                raise PrivateReport

        return json

    async def session(self):
        if not self._auth:
            with sentry_sdk.start_span(op="http", description="auth"):
                r = await self._session.post(
                    "https://www.warcraftlogs.com/oauth/token",
                    auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
                    data={"grant_type": "client_credentials"},
                    raise_for_status=True,
                )
            # Set on class, to be re-used (valid for a year, so probably don't have to worry)
            self.__class__._auth = (await r.json())["access_token"]
        return self._session


def get_client():
    return WCLClient(
        "***REMOVED***",
        "***REMOVED***",
    )


async def fetch_report(report_id, fight_id, source_id) -> Report:
    client = get_client()

    async with client:
        return await client.query(report_id, fight_id, source_id)
