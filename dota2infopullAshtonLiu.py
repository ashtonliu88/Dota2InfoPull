# Libraries to install:
# pip3 install python3
# pip3 install requests
# pip3 install PyYaml
# pip3 install http
# pip3 install asyncio
# pip3 install aiohttp

# HOW TO RUN:
# python3 dota2infopull.py <n number of top teams you want to see> <output file>

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

#I have decided to cache the data and store the information so that each time the program runs it doesn't request it each time.
#This decision was based off of video games and how the top leaderboards don't update immediately, but more after a certain time so that
#the system doesn't crash.
#Furthermore, if a user wants to access the leaderboard multiple times in a row and I don't set up a cache system, they would be met with invalid
#response codes because there would be too many request in a given time period.
cacheFile = "cache.json"
cacheDuration = timedelta(minutes=5)

#Retry codes implemented to check if error occurs in response status code
#Stack overflow: https://stackoverflow.com/questions/61463224/when-to-use-raise-for-status-vs-status-code-testing for reference
retry_codes = [
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
]

#Obtain a list of all pro players
def accessProPlayers():
    #Access openDota's api's endpoing for proPlayers and select URL of proPlayers
    proPlayerURL = f"{homeURL}/proPlayers"

    #Access response from proPlayerURL
    try:
        response = requests.get(proPlayerURL, timeout = 5)
        response.raise_for_status()
        time.sleep(0.1)
        return response.json()
    
    #Exception error to check if too many requests for free dota API trial
    except Exception as e:
        print(f"Failed to retrive players, response code: {response.status_code}")
    return []

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
            #Using async to set up a session per response
            async with session.get(teamsURL) as response:

                #Checking if the response status code is in the retryCodes list
                if response.status in retry_codes:

                    #If the response status code is not 200, add more attempts to see if everything works
                    if attempt < retries - 1:

                        #Test output to make sure retries work
                        #print(f"Retrying team {teamID} in {retryDelay} seconds...")

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

            #Print line to check if error fetching team details
            #print(f"Error fetching team details for team ID {teamID}: {e}")

            return None
    

#This function calculates the experience time in hours for a player since video games mainly show statistics in hours
#I first take off the microseconds since it is irrelevant in the final output of the program and only obtain the date, hour, minute, and second
#My program does not account for players without a full_history_time and takes them out of consideration
def calculatePlayerTimeExperience(playerVar):

    #Check to see if full_history_time is found in players
    if 'full_history_time' in playerVar:

        try:
            #Accessing the team experience time of a player and stripping it down to only up until the second without decimal
            #Microseconds are unnecessary in the grand scheme since I am reporting each team experience in hours
            historyTime = datetime.strptime(str(playerVar['full_history_time'])[0:19], "%Y-%m-%dT%H:%M:%S")

            #Accessing current time of local machine and getting rid of microseconds to compare with historyTime
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
            #Test print statement to check if an account ID doesn't have a full_history_time
            #print(f"Error parsing time, {playerVar['account_id']} does not have full_history_time: {e}")
            return None
    
    else:
        return None


#Implementing asyncio function to make this more efficient
async def obtainProTeams():

    #Creating dictionary and list
    teamXPDictionary = {}
    proPlayerList = accessProPlayers()

    #Obtain the team id for each pro player if applicable
    teamIDs = set(player['team_id'] for player in proPlayerList if player['team_id'])

    #Creates a client session with asyncio and aiohttp
    async with aiohttp.ClientSession() as session:
        #Creating task of accessing each team's id to run asynchronously with each other
        tasks = [accessSpecificTeamData(session, team_id) for team_id in teamIDs]
        #Obtains the data list of teams from the task
        teamDataList = await asyncio.gather(*tasks)

    #Iterating through each team data and team id
    for teamData, teamID in zip(teamDataList, teamIDs):

        #Make sure team data exists
        if teamData is None:
            
            #Test print method to check if a team id is skipped
            #print(f"Skipping team ID {teamID} due to fetch error, data for {teamID} not found")

            continue
    
        #Specifically targets pro players in each team to not confuse other non-pro players in the team
        playersForTeam = [player for player in proPlayerList if player['team_id'] == teamID]
        teamXP = 0

        allPlayersInfo = []
        #Calculate each pro players experience in a team
        for player in playersForTeam:

            #Calculate each pro player's experience
            playerXP = calculatePlayerTimeExperience(player)

            if playerXP is not None:

                teamXP += float(playerXP)

                #Implement the player information first to ensure that only pro players are being accounted for
                allPlayersInfo.append({
                    'personaname': player['personaname'],
                    'playerXP': playerXP,
                    'countryCode': player['country_code']
                })

        teamXP = round(teamXP, 2)

        #Create the dictionary for each new team accounted for
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

        #Accessing yaml to dump the information obtained from obtainProTeams() into an output file
        yaml_string = yaml.dump(data, default_flow_style=False, sort_keys=False)

        #Adds new line before each team to make it easier to read
        yaml_string = yaml_string.replace("\n- ", "\n\n- ")

        file.write(yaml_string)

#Function to load the cache so that it doesn't request too often
def loadCache():
    if os.path.exists(cacheFile):
        with open(cacheFile, 'r') as file:
            cacheData = json.load(file)
            cacheTime = datetime.strptime(cacheData['timestamp'], "%Y-%m-%dT%H:%M:%S")
            return cacheData['data'], cacheTime
    return None, None

#Function to save cache to cache.json
def saveCache(data):
    with open(cacheFile, 'w') as file:
        cacheData = {
            'timestamp': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            'data': data
        }
        json.dump(cacheData, file)

#Function to check if the cache time and the time now has been over 5 minutes
def isCacheExpired(cacheTime):
    if cacheTime:
        return (datetime.now() - cacheTime) > cacheDuration
    return True
        

#Main function to take in input N number of teams as well as input file
def main(inputNum, inputOutFile):

    if inputNum <= 0:
        print("Number of teams input must be greater than 0")
        return
    
    #Checking to see if user input for outfile is in yaml format
    if not inputOutFile.endswith(('.yaml', '.yml')):
        print("Output file must have a .yaml or .yml extension")
        return

    #load cache data
    cachedData, cacheTime = loadCache()

    #Check to see if cache data needs to be refreshed
    if cachedData and not isCacheExpired(cacheTime):
        topTeamData  = cachedData
        print("Using Cache Data, cache will refresh after 5 minutes from first use")
        timeElapsed = datetime.now() - cacheTime
        print(f"Time elapsed since recent cache refresh: {timeElapsed}")

    else:
        #Running asyncio with my asynch function to have all team information gathered at once
        topTeamData = asyncio.run(obtainProTeams())

        #Checking to see if topTeamData exists
        if topTeamData:
            #Saving new data request pull to cache
            saveCache(topTeamData)
            print("Saved new data to cache")
    
        else:
            #Check if too many requests have been pulled and program can't access dota2API
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
        #Fail Message to check if daily limit is reached for Dota2API
        print(f"Failed to process data. Check API")

    return

#Taking in inputs
if __name__ == "__main__":

    #Making sure user inputs correct input format
    if len(sys.argv) != 3:
        print("python script should be run like this: python dota2infopull.py <top N teams> <outFile>")
    else:
        topNum = int(sys.argv[1])
        outFile = sys.argv[2]
        main(topNum, outFile)
