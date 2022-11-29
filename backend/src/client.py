import aiohttp
import logging

from report import Report, Source


class WCLClient:
    base_url = "https://classic.warcraftlogs.com/api/v2/client"

    def __init__(self, client_id, client_secret):
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth = None
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self._session.__aexit__(*args)
        self._session = None

    async def _fetch_metadata(self, report_code):
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
          subType
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
}
""" % report_code
        return (await self._query(metadata_query))["data"]

    async def _fetch_events(self, report_code, fight_id, source_id):
        events = []
        combatant_info = []
        next_page_timestamp = 0
        events_query_t = """
{
  reportData {
    report(code: "%(report_code)s") {
      events(
        killType: Kills
        startTime: %(next_page_timestamp)s
        endTime: 100000000000
        sourceID: %(source_id)s
        useActorIDs: true
        includeResources: true
        fightIDs: [%(fight_id)s]
      ) {
        nextPageTimestamp
        data
      }
      rankings(
        fightIDs: [%(fight_id)s]
      )
      combatantInfo: events(
        killType: Kills
        startTime: %(next_page_timestamp)s
        endTime: 100000000000
        useActorIDs: true
        dataType: CombatantInfo
      ) {
        data
      }
    }
  }
}
"""
        while next_page_timestamp is not None:
            events_query = events_query_t % dict(
                report_code=report_code,
                next_page_timestamp=next_page_timestamp,
                source_id=source_id,
                fight_id=fight_id,
            )
            r = (await self._query(events_query))["data"]["reportData"]["report"]
            combatant_info = r["combatantInfo"]["data"]
            next_page_timestamp = r["events"]["nextPageTimestamp"]
            events += r["events"]["data"]

            if r["rankings"]:
                rankings = r["rankings"]["data"]
            else:
                rankings = []

        return events, combatant_info, rankings

    async def query(self, report_id, fight_id, source_id):
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

        zones = (await self._query(encounter_query))["data"]["worldData"]["zones"]
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

        events, combatant_info, rankings = await self._fetch_events(
            report_id, fight_id, source_id
        )

        return Report(
            source,
            events,
            rankings,
            combatant_info,
            encounters,
            actors,
            report_metadata["masterData"]["abilities"],
            report_metadata["fights"],
        )

    async def get_ability_icon(self, ability_id):
        query = (
            """
{
  gameData {
    ability(id: %s) {
      id
      icon
      name
    }
  }
}

"""
            % ability_id
        )
        return (await self._query(query))["data"]["gameData"]

    async def _query(self, query):
        session = await self.session()
        r = await session.post(
            self.base_url,
            json={"query": query},
            headers=dict(Authorization=f"Bearer {self._auth}"),
            raise_for_status=True,
        )
        json = await r.json()

        if "errors" in json:
            logging.error(json["errors"])

        return json

    async def session(self):
        if not self._auth:
            r = await self._session.post(
                "https://www.warcraftlogs.com/oauth/token",
                auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
                raise_for_status=True,
            )
            self._auth = (await r.json())["access_token"]
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
