import yaml
import requests
from http import HTTPStatus

import time
from datetime import datetime, timedelta
import sys

#Need these libraries to improve efficiency of code
import asyncio
import aiohttp

import os
import json

homeURL = "https://api.opendota.com/api"

#I have decided to cache the data and store the information so that each time the program runs it doesn't request it each time
#This decision was based off of video games and how the top leaderboards don't update immediately, but more after a certain time so that
#the system doesn't crash
cacheFile = "cache.json"
cacheDuration = timedelta(minutes=5)

#Obtain a list of all pro players
def accessProPlayers():
    #Access openDota's api's endpoing for proPlayers and select URL of proPlayers
    proPlayerURL = f"{homeURL}/proPlayers"

    #Obtain response of 200 to make sure systems are up
    response = requests.get(proPlayerURL)

    #Check if the status code is 200 to see if systems are up
    if response.status_code == 200:
        time.sleep(0.1)
        #Return the list of pro players in a .json format
        return response.json()
    
    #Output message if status code is not 200, signifying that system is not working
    else:
        print(f"Failed to retrive players, response code: {response.status_code}")
    
    return []

#Retry codes implemented to check if error occurs in response status code
#Stack overflow: https://stackoverflow.com/questions/61463224/when-to-use-raise-for-status-vs-status-code-testing for reference
retry_codes = [
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
]

#Obtain team data of specific team, using async to run all team gathering at the same time instead of one by one
async def accessSpecificTeamData(session, teamID):
    #Access specific team player data endpoint for teamID
    teamsURL = f"{homeURL}/teams/{teamID}"

    #Retry time active in case server cant obtain info
    retries = 3
    backoffFactor = 2
    retryDelay= 1

    #Classifying for loop to give the program 3 retries if status code is not 200
    for attempt in range(retries):

        try:
            async with session.get(teamsURL) as response:

                if response.status in retry_codes:

                    #If the response status code is not 200, add more attempts to see if everything works
                    if attempt < retries - 1:
                        print(f"Retrying team {teamID} in {retryDelay} seconds...")
                        #Wait for retry_delay seconds
                        await asyncio.sleep(retryDelay)
                        #Exponential backoff
                        retryDelay *= backoffFactor
                        continue

                #Return the response object if response is successful
                response.raise_for_status()

                #Return response from function
                return await response.json()
            
        #Error handling to output if team details are not found
        except Exception as e:
            print(f"Error fetching team details for team ID {teamID}: {e}")

            return None
    
    

#This function calculates the experience time in hours for a player since video games mainly show statistics in hours
#I first take off the microseconds since it is irrelevant in the long run and only obtain the date, hour, minute, and second
def calculatePlayerTimeExperience(playerVar):

    if 'full_history_time' in playerVar:
        try:

            #Accessing the team experience time of a player and stripping it down to only up until the second without decimal
            #Microseconds are unnecessary in the grand scheme since I am reporting each team experience in hours
            historyTime = datetime.strptime(str(playerVar['full_history_time'])[0:19], "%Y-%m-%dT%H:%M:%S")


            currTime = datetime.now().replace(microsecond = 0)
        
            #Calculates the hours passed since the team experience
            timeDiff = currTime - historyTime
            timeHours = float(timeDiff.total_seconds() / 3600)

            #This makes sure that any breaking cases are accounted for
            if timeHours and timeHours > 0:
                return ("{:.2f}".format(timeHours))
            else:
                return None
            
        #Mainly here for seeing if NONE exists as a player experience placeholder for some players
        except ValueError as e:
            print(f"Error parsing time, {playerVar['account_id']} does not have full_history_time: {e}")
            return None
    
    else:
        return None


#Implementing asyncio function to make this more efficient
async def obtainProTeams():

    teamXPDictionary = {}
    proPlayerList = accessProPlayers()

    teamIDs = set(player['team_id'] for player in proPlayerList if player['team_id'])

    #Creates a client session with asyncio and aiohttp
    async with aiohttp.ClientSession() as session:
        tasks = [accessSpecificTeamData(session, team_id) for team_id in teamIDs]
        teamDataList = await asyncio.gather(*tasks)

    #Iterating through each team data and team id
    for teamData, teamID in zip(teamDataList, teamIDs):

        #Make sure team data exists
        if teamData is None:
            print(f"Skipping team ID {teamID} due to fetch error, data for {teamID} not found")
            continue
    
        #Specifically targets pro players in each team to not confuse other non-pro players in the team
        playersForTeam = [player for player in proPlayerList if player['team_id'] == teamID]
        teamXP = 0

        allPlayersInfo = []
        #Calculate each pro players experience in a team
        for player in playersForTeam:
            playerXP = calculatePlayerTimeExperience(player)
            if playerXP is not None:
                teamXP += float(playerXP)
                allPlayersInfo.append({
                    'personaname': player['personaname'],
                    'playerXP': playerXP,
                    'countryCode': player['country_code']
                })

        teamXP = round(teamXP, 2)

        teamXPDictionary[teamID] = {
            'teamID': teamID,
            'teamName': teamData.get('name', 'Unknown Team'),
            'teamWins': teamData.get('wins', 0),
            'teamLosses': teamData.get('losses', 0),
            'teamRating': teamData.get('rating', 0),
            'teamExperience': teamXP,
            'players': allPlayersInfo
        }

    return teamXPDictionary

#Yaml function to yaml data gained
def YAML (data, outFile):
    with open(outFile, 'w') as file:
        yaml_string = yaml.dump(data, default_flow_style=False, sort_keys=False)
        yaml_string = yaml_string.replace("\n- ", "\n\n- ")  # Add a newline before each team entry
        file.write(yaml_string)

#Loading the cache so that it doesn't request too often
def loadCache():
    if os.path.exists(cacheFile):
        with open(cacheFile, 'r') as file:
            cacheData = json.load(file)
            cacheTime = datetime.strptime(cacheData['timestamp'], "%Y-%m-%dT%H:%M:%S")
            return cacheData['data'], cacheTime
    return None, None

def saveCache(data):
    with open(cacheFile, 'w') as file:
        cacheData = {
            'timestamp': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            'data': data
        }
        json.dump(cacheData, file)

def isCacheExpired(cacheTime):
    if cacheTime:
        return datetime.now() - cacheTime > cacheDuration
    
    return True
        

#Main function to take in input N number of teams as well as input file
def main(inputNum, inputOutFile):

    if inputNum <= 0:
        print("Number of teams input must be greater than 0")
        return
    
    cachedData, cacheTime = loadCache()
    if cachedData and not isCacheExpired(cacheTime):
        topTeamData  = cachedData
        print("Using Cache Data, cache will refresh after 5 minutes from first use")
        timeElapsed = datetime.now() - cacheTime
        print(f"Time elapsed since recent cache refresh: {timeElapsed}")
    else:
        #Running asyncio with my asynch function to have all team information gathered at once
        topTeamData = asyncio.run(obtainProTeams())

        if topTeamData:
            saveCache(topTeamData)
            print("Saved new data to cache")
        else:
            print(f"Failed to process data. Check API")
            return

    #Checking if I can obtain all the information or if the API doesn't allow me to access more information due to lack of API key
    if topTeamData:
        #Sorting function to generate a dictionary sorted by the values of teamExperience and then only keeping up until n number of teams in the list
        sortedTeams = sorted(topTeamData.values(), key=lambda x: x['teamExperience'], reverse=True)[:inputNum]
        YAML(sortedTeams, inputOutFile)
        #Success Message
        print(f"Saved top {inputNum} teams to {inputOutFile}")
    else:
        #Fail Message
        print(f"Failed to process data. Check API")

    return

#Taking in inputs
if __name__ == "__main__":

    #Making sure user inputs correct input format
    if len(sys.argv) != 3:
        print("python script should be run like this: python dota2infopull.py <top_n_team> <outFile>")
    else:
        topNum = int(sys.argv[1])
        outFile = sys.argv[2]
        main(topNum, outFile)
