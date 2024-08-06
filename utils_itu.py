import json
import requests  # pip install requests

url_prefix = "https://api.triathlon.org/v1/"

with open("api_key.txt", "r") as f:
    api_key = f.readline()
headers = {'apikey': api_key}


def get_request(url_suffix, params=""):
    url = url_prefix + url_suffix
    # print(url)
    response = requests.request("GET", url, headers=headers, params=params)
    d = json.loads(response.text)
    d = d["data"]
    return d


category_mapping = {
    343: "games",  # "Major Games",
    345: "games",  # "Recognised Event",
    346: "games",  # "Recognised Games",
    624: "wcs",  # "World Championship Finals",
    351: "wcs",  # "World Championship Series",
    349: "world-cup",  # "World Cup",
}