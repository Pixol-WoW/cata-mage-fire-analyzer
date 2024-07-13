import requests
import json
from dataclasses import dataclass, field
import pandas as pd
import asyncio
from utils.wcl.PixolWCLReport import WCLReportMetaData, WCLReportFightData

# /lib/python3.11/site-packages/urllib3/connectionpool.py:1101:
# InsecureRequestWarning: Unverified HTTPS request is being made to host 'classic.warcraftlogs.com'.
# Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
# Making unverified HTTPS requests is strongly discouraged, however, if you understand the risks and wish to disable these warnings, you can use disable_warnings():
import urllib3
urllib3.disable_warnings()

@dataclass
class Encounter:
    id: int
    name: str

class WCLClientException(Exception):
    pass

class PrivateReport(WCLClientException):
    pass

class InvalidReport(WCLClientException):
    pass

class TemporaryUnavailable(WCLClientException):
    pass

class UnauthenticatedQuery(WCLClientException):
    pass

class WCLClient:
    base_url = "https://classic.warcraftlogs.com/api/v2/client"
    _zones = None
    _token = None

    def __init__(self, client_id="", client_secret=""):
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = None

    async def _generate_token(self):
        url = "https://www.warcraftlogs.com/oauth/token"
        headers = {
            'Accept': "application/json",
        }

        data = {
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'grant_type': 'client_credentials'
        }

        response = requests.post(url, headers=headers, data=data)
        response_json = json.loads(response.text)

        if 'access_token' not in response_json:
            raise UnauthenticatedQuery()
        
        return json.loads(response.text)['access_token']

    async def get_api_rate(self):
        query = """
                query{
                  rateLimitData {
                    limitPerHour
                    pointsResetIn
                    pointsSpentThisHour
                  }
                }
                """
        data = await self._query(query)
        return '%.1f/%d WCL Points Used (%.1f%%) [Reset: %02dm %02ds]'%(data['data']['rateLimitData']['pointsSpentThisHour'],data['data']['rateLimitData']['limitPerHour'],data['data']['rateLimitData']['pointsSpentThisHour']/data['data']['rateLimitData']['limitPerHour']*100,data['data']['rateLimitData']['pointsResetIn']//60,data['data']['rateLimitData']['pointsResetIn']%60)

    async def _query(self, query):
        if not self._token:
            self._token = await self._generate_token()

        headers = {
            'Content-Type': "application/json",
            'Accept': "application/json",
            'Authorization': f"Bearer {self._token}"
        }
        response = requests.post(self.base_url, json={'query': query}, headers=headers)
        response_json = json.loads(response.text)

        if "errors" in response_json:
            # logging.error(response_json["errors"])
            error_msg = response_json["errors"][0]["message"]

            if error_msg == "You do not have permission to view this report.":
                raise Exception('Private Report')
            elif error_msg == "This report does not exist.":
                raise Exception('Invalid Report')
        elif "error" in response_json:
            if response_json["error"] == "Unauthenticated.":
                raise Exception('Unauthenticated Query')

        return response_json

    async def _get_encounters(self):
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
            zones = (await self._query(encounter_query))["data"]["worldData"]["zones"]
            encounters = [encounter for zone in zones for encounter in zone["encounters"]]

            self.__class__._encounters = {
                encounter["id"]: Encounter(encounter["id"], encounter["name"])
                for encounter in encounters
            }
        return self._encounters

    async def _get_metadata(self, report_code, includeAllFightsAsEncounters=False):
        meta_data_query = """
            query{
                reportData
                {
                    report(code:"%s")
                    {
                        title
                        startTime
                        playerDetails(startTime:0, endTime: 10000000000)
                        fights
                        {
                            id
                            name
                            difficulty
                            encounterID
                            hardModeLevel
                            bossPercentage
                            fightPercentage
                            kill
                            lastPhase
                            lastPhaseAsAbsoluteIndex
                            lastPhaseIsIntermission
                            friendlyPlayers
                            startTime
                            endTime
                            size
                            phaseTransitions
                            {
                                id,
                                startTime,
                            }
                            enemyNPCs
                            {
                                gameID
                                id
                                instanceCount
                                groupCount
                                petOwner
                            }
                            enemyPets
                            {
                                gameID
                                id
                                instanceCount
                                groupCount
                                petOwner
                            }
                            enemyPlayers
                            friendlyNPCs
                            {
                                gameID
                                id
                                instanceCount
                                groupCount
                                petOwner
                            }
                            friendlyPets
                            {
                                gameID
                                id
                                instanceCount
                                groupCount
                                petOwner
                            }
                        }
                        guild{
                            name
                            server{
                                name
                            }
                        }
                        masterData
                        {
                            abilities
                            {
                                gameID
                                name
                                type
                                icon
                            }
                            actors
                            {
                                gameID
                                petOwner
                                icon
                                id
                                name
                                type
                                subType
                                server
                            }
                        }
                    }
                }
            }
        """ % (report_code)

        return WCLReportMetaData((await self._query(meta_data_query))['data']['reportData']['report'], includeAllFightsAsEncounters, report_code)

    async def _fetch_events(self, report_code, fight_id=None, source_id=None, filter_exp=None, include_deaths=False, include_combatant_info=False, metadata=None):
        deaths = []
        events = []
        combatant_info = []
        next_page_timestamp = 0
        entrySourceID = source_id and f"sourceID: {source_id}" or ""
        entryFightID = fight_id and f"fightIDs: [{fight_id}]" or ""
        filter_exp_base = 'type != "combatantinfo"'
        filter_exp = (filter_exp and " and ".join([filter_exp_base, filter_exp]) or filter_exp_base).replace("\"","\\\"")
        entryFilterExp = filter_exp and f"filterExpression: \"{filter_exp}\"" or ""

        deaths_query = include_deaths and """
      deaths: events(
        startTime: 0
        endTime: 100000000000
        useActorIDs: true
        sourceID: -1
        %(entryFightID)s
        limit: 10000
      ) {
        data
      }
""" or ""
        
        combatant_info_query = include_combatant_info and """
      combatantInfo: events(
        startTime: 0
        endTime: 100000000000
        %(entrySourceID)s
        useActorIDs: true
        dataType: CombatantInfo
        %(entryFightID)s
        limit: 10000
      ) {
        data
      }
""" or ""

        events_query_t = """
{
  reportData {
    report(code: "%(report_code)s") {
      events(
        startTime: %(next_page_timestamp)s
        endTime: 100000000000
        %(entrySourceID)s
        useActorIDs: true
        includeResources: true
        %(entryFightID)s
        %(entryFilterExp)s
        limit: 10000
      ) {
        nextPageTimestamp
        data
      }
      %(deathsQuery)s
      %(combatantInfoQuery)s
    }
  }
}
"""\
        .replace("%(deathsQuery)s", deaths_query)\
        .replace("%(combatantInfoQuery)s", combatant_info_query)

        while next_page_timestamp is not None:
            events_query = events_query_t % dict(
                report_code=report_code,
                next_page_timestamp=next_page_timestamp,
                entrySourceID=entrySourceID,
                entryFightID=entryFightID,
                entryFilterExp=entryFilterExp,
            )
            r = (await self._query(events_query))["data"]["reportData"]["report"]

            if next_page_timestamp == 0:
                if r.get('combatantInfo'):
                    combatant_info = r["combatantInfo"]["data"]
                if r.get('deaths'):
                    deaths = [death for death in r["deaths"]["data"] if death["type"] == "death"]

            next_page_timestamp = r["events"]["nextPageTimestamp"]
            events += r["events"]["data"]

        return WCLReportFightData(events, metadata=metadata, fight_id=fight_id), combatant_info, deaths