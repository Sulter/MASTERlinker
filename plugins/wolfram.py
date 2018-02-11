# Plugin that uses the wolfram alpha api to solve equations etc.
import includes.helpers as helpers
import xml.etree.ElementTree as xml
import urllib.request, urllib.error, urllib.parse
import logging
import threading


class wolfram(helpers.Plugin):
  def __init__(self, parent):
    super().__init__(parent)
    default_config = {
      'api_key': "Wolfram Alpha API key",
    }
    self.config = helpers.parse_config('settings_wolfram.json', default_config)

  def handle_pm(self, msg_data):
    # Ignore private messages, to prevent from flooding/api usage etc.
    pass

  def handle_message(self, msg_data):
    if msg_data["message"].startswith("!WA "):
      t = threading.Thread(target=self.wolfram_thread, args=(msg_data,))
      t.start()

  def wolfram_thread(self, msg_data):
    phrase = msg_data["message"].replace("!WA ","", 1).replace(" ", "%20").replace("&", "").replace("/", "%2F")
    if phrase:
      url = 'http://api.wolframalpha.com/v2/query?input={}&appid={}'.format(phrase, self.config['api_key'])
      try:
        string = urllib.request.urlopen(url).read(10000000)
      except:
        logging.debug("wolfram alpha error could not open: %s", url)
        return

      logging.debug("wolfram alpha, opened: %s send by the user:%s", url, msg_data["nick"])

      try:
        xml_response = xml.fromstring(string)
      except:
        logging.debug("wolfram alpha error could not parse with xml: %s", url)
        return

      # Finding the right xml elements
      if "success" in xml_response.attrib:
        if "true" in xml_response.attrib["success"]:
          for pod in xml_response.findall("pod"):
            if "Result" in pod.attrib["title"] or "Solution" in pod.attrib["title"] or "Definition" in pod.attrib["title"] or "Basic properties" in pod.attrib["title"] or "Basic information" in pod.attrib["title"] or "Value" in pod.attrib["title"] or "Name" in pod.attrib["title"] or "Average result" in pod.attrib["title"] or "result" in pod.attrib["title"] or "approximation" in pod.attrib["title"]:
              response = pod.find("subpod").find("plaintext").text
              response = response.encode('utf-8')
              if response:
                # Sanitize
                forbidden = ["\n", "\r", "\t", "\f", "\v"]
                for i in forbidden:
                  response = response.replace(i, " ")
                response = response[0:300]
                response = "\x033[WOLFRAM ALPHA | " + response + "]"
                self.send_msg(msg_data["channel"], response)
