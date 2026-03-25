import requests
import json
# Write a function to read the file created by extractVersion.sh
# Write a function to scrape exploit.db and search for the software:version pair.
    # If found a hit, note it down in the file

def readVersions() -> dict[str, str]:
    versionInfo = dict()
    with open("VersionInfo.txt","r") as f:
        lines = f.readlines()
    for line in lines:
        versionInfo[line.split(":")[0]] = line.split(":")[1].strip()
    return versionInfo

def findVulnVersions(versionInfo: dict) -> list:
    productVersion = "0.5.6"
    vendor = "nginx"
    product = "nginx"
    # Changed the API. Refer to Session 15th October 2025
    retrieve_CPE_API= f"https://services.nvd.nist.gov/rest/json/cpematch/2.0?matchStringSearch=cpe:2.3:a:{vendor}:{product}:{productVersion}"
    retrieve_CVE_API_base = "https://services.nvd.nist.gov/rest/json/cves/2.0?cpeName="
    response = requests.get(retrieve_CPE_API)
    response = json.loads(response.text)
    #print(response)
    #versionStartIncluding = response['matchStrings'][0]['matchString']['versionStartIncluding']
    #versionEndIncluding = response['matchStrings'][0]['matchString']['versionEndIncluding']
    matches = response['matchStrings'][0]['matchString']
    print(matches)
    #for match in matches:
        #print(match['cpeName'])
        #response = requests.get(f"{retrieve_CVE_API_base}{match['cpeName']}")
        #print(f"--------------For version {match}------------------------------")
        #print(response.text,end='\n\n')
    #print(versionStartIncluding, versionEndIncluding) 
    #print(response['matchStrings'][0]['matchString'])       
versionInfo = readVersions()
#print(findVulnVersions(versionInfo))
findVulnVersions(versionInfo)