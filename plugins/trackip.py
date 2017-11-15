import urllib
import json
import re


class trackip():
  def trackip(self, main_ref, msg_info):
    if msg_info["channel"] == main_ref.config['connection']['nick']:
      return None

    if msg_info["message"].lower().startswith("!track "):
      address = re.match("!track (\S+)", msg_info["message"].lower())
      if address:
        response = self.get_info(address.group(1))
        main_ref.send_msg(msg_info["channel"], response)

  def get_info(self, adress):
    api = "http://freegeoip.net/json/" + adress
    try:
      result = json.load(urllib.request.urlopen(api))
    except urllib.error.HTTPError:
      return None

    response = "[" + adress + " | " + result["ip"] + " | country:  " + result["country_name"] + " | city: " + \
           result["city"] + " | map link: "
    map_link = "http://www.openstreetmap.org/#map=11/" + str(result["latitude"]) + "/" + str(result["longitude"])
    response += map_link
    response = "\x033" + response + "]"
    return response
