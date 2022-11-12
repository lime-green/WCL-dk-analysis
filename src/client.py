import requests

from report import Report


class WCLClient:
    base_url = "https://classic.warcraftlogs.com/api/v2/client"

    def __init__(self, client_id, client_secret):
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = requests.Session()
        self._auth = None

    def _fetch_events(self, report_code, source_id):
        events = []
        next_page_timestamp = 0
        events_query_t = """
{
  reportData {
    report(code: "%s") {
      events(
        killType: Kills
        startTime: %s
        endTime: 100000000000
        sourceID: %s
        useActorIDs: true
        includeResources: true
      ) {
        nextPageTimestamp
        data
      }
    }
  }
}

"""
        while next_page_timestamp is not None:
            events_query = events_query_t % (
                report_code,
                next_page_timestamp,
                source_id,
            )
            r = self._query(events_query).json()["data"]["reportData"]["report"][
                "events"
            ]
            next_page_timestamp = r["nextPageTimestamp"]
            events += r["data"]

        return events

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
            headers=dict(Authorization=f"Bearer {self._auth}"),
        )
        r.raise_for_status()
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
