import requests
import json
import collections
def readVersionInfo(fileName:str):
    infos = list()
    with open(fileName, "r") as f:
            infos = f.readlines()
    return infos

def checkVulnVersion(infos:list):   # Try to identify each product as vendor:product string instead of just product
    cve_api = "https://services.nvd.nist.gov/rest/json/cves/2.0?virtualMatchString=cpe:2.3:*:"
    vuln_count_dict = collections.OrderedDict()
    for info in infos:
        count = 0
        print(f"\x1b[38;2;225;000;000m--------------------[{info.split(':')[0]+' '+ info.split(':')[1]}]-----------------------------\x1b[0m")
        url = cve_api + info.strip()
        json_response = json.loads(requests.get(url).text)
        for vuln in json_response['vulnerabilities']:
            print(f"\x1b[38;2;000;225;000m[+]{vuln['cve']['id']}:\x1b[0m",vuln['cve']['descriptions'][0]['value'])
            count+=1
        vuln_count_dict[info.split(':')[0] + ":" + info.split(':')[1] + ":" + info.split(':')[2].strip()] = count
        print(f"\x1b[38;2;225;000;000m-----------------------------------------------------------------------------------------------\x1b[0m\n\n")
    #url = cve_api + infos[0].strip()
    #json_response = json.loads(requests.get(url).text)
    #for vuln in json_response['vulnerabilities']:
    #    print(vuln['cve']['id'],vuln['cve']['descriptions'][0]['value'])    
    #print(json_response['vulnerabilities'][0]['cve']['id']) 
    return vuln_count_dict

def updateToLatestVersion(product:str):
    cpe_api = "https://services.nvd.nist.gov/rest/json/cpes/2.0?cpeMatchString=cpe:2.3:a:"
    url = cpe_api + product.split(':')[0] + ":" + product.split(':')[1]
    json_response = json.loads(requests.get(url).text)
    updated_product = json_response['products'][-1]['cpe']['cpeName'].split(":")[3] + ":" + json_response['products'][-1]['cpe']['cpeName'].split(":")[4] + ":" + json_response['products'][-1]['cpe']['cpeName'].split(":")[5]
    return updated_product
    

def retrieveLatestVersion(vulnCountDict:dict):
    updated_product_list = list()
    filename = "VersionInfo.txt"
    for product in vulnCountDict.keys():
        if vulnCountDict[product] > 0:
            updated_product_list.append(updateToLatestVersion(product) + "\n")
        else:
            updated_product_list.append(product + "\n")
    print("\x1b[38;2;225;000;000m-----------Summary--------------------\x1b[0m")
    for product in vulnCountDict.keys():
        print(f"\x1b[38;2;000;225;000mNumber of vulns in {product} : {vulnCountDict[product]}\x1b[0m")
    print(f"\x1b[38;2;225;000;000m-----------Latest Versions--------------------\x1b[0m")
    counter = 0
    for product in vulnCountDict.keys():
        print(f"\x1b[38;2;000;225;000mLatest Version of {product} : {updated_product_list[counter].split(':')[2]}\x1b[0m")
        counter+=1
    answer = input("\x1b[38;2;255;255;000m[?]Do you wish to  update?[y/n]:\x1b[0m")
    if answer == 'n' or answer == 'N':
        print("\x1b[38;2;225;000;000m[#!]Exiting without updating!\x1b[0m")
        return
    with open(filename,"w") as f:
        f.write("".join(updated_product_list))
    print("\x1b[38;2;000;225;000m[#]File has been updated! Please check.\x1b[0m")

retrieveLatestVersion(checkVulnVersion(readVersionInfo("VersionInfo.txt")))
