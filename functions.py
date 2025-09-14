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
    numVulns = list()
    for key in versionInfo.keys():
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={key} {versionInfo[key]}"
        response = requests.get(url)
        #print(response.text)
        parsed_response = json.loads(response.text)
        #print(parsed_response)
        numVulns.append(len(parsed_response["vulnerabilities"]))
    return numVulns          
versionInfo = readVersions()
print(findVulnVersions(versionInfo))