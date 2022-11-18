import requests

from report import Report, Source


class WCLClient:
    base_url = "https://classic.warcraftlogs.com/api/v2/client"

    def __init__(self, client_id, client_secret):
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = requests.Session()
        self._auth = None

    def _fetch_events(self, report_code, source_id):
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
      ) {
        nextPageTimestamp
        data
      }
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
            )
            r = self._query(events_query).json()["data"]["reportData"]["report"]
            combatant_info = r["combatantInfo"]["data"]
            next_page_timestamp = r["events"]["nextPageTimestamp"]
            events += r["events"]["data"]

        return events, combatant_info

    def query(self, report_code, character, zone_id):
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
    zone(id: %s) {
      encounters {
        id
        name
      }
    }
  }
}
""" % (
            report_code,
            zone_id,
        )

        metadata = self._query(metadata_query).json()["data"]
        report_metadata = metadata["reportData"]["report"]

        for actor in report_metadata["masterData"]["actors"]:
            if actor["type"] == "Player" and actor["name"] == character:
                source = Source(actor["id"], actor["name"])
                break
        else:
            raise Exception("Character not found")

        events, combatant_info = self._fetch_events(report_code, source.id)

        return Report(
            source,
            events,
            combatant_info,
            metadata["worldData"]["zone"]["encounters"],
            report_metadata["masterData"]["actors"],
            report_metadata["masterData"]["abilities"],
            report_metadata["fights"],
        )

    def _query(self, query):
        r = self.session.post(
            self.base_url,
            json={"query": query},
            headers=dict(Authorization=f"Bearer {self._auth}"),
        )
        r.raise_for_status()

        if "errors" in r.json():
            raise Exception(r.json()["errors"])

        return r

    @property
    def session(self):
        if not self._auth:
            r = self._session.post(
                "https://www.warcraftlogs.com/oauth/token",
                auth=(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
            )
            r.raise_for_status()
            self._auth = r.json()["access_token"]
        return self._session
