#plugin that uses the wolfram alpha api to solve equations etc.

import xml.etree.ElementTree as xml
import urllib2
import settings
import logging
import threading

class wolfram():

    def wolfram(self, main_ref, msg_info):
        #we block private msg, to prevent from flooding/api usage etc.
        if msg_info["channel"] == settings.NICK:
            return None
        
        if msg_info["message"].startswith("!WA "):
            #start thread
            t = threading.Thread(target=self.wolfram_thread, args=(main_ref, msg_info))
            t.start()

    def wolfram_thread(self, main_ref, msg_info):
            phrase = msg_info["message"].replace("!WA ","", 1).replace(" ", "%20").replace("&", "")
            if phrase:
                url = "http://api.wolframalpha.com/v2/query?input=" + phrase + "&appid=" + settings.wa_api_key
                try:
                    string = urllib2.urlopen(url).read(10000000)
                except:
                    logging.debug("wolfram alpha error could not open: %s", url)
                    return

                logging.debug("wolfram alpha, opened: %s send by the user:%s", url, msg_info["nick"])
                
                try:
                    xml_response = xml.fromstring(string)
                except:
                    logging.debug("wolfram alpha error could not parse with xml: %s", url)
                    return
                 
                #finding the right xml elements. (sigh....)
                if "success" in xml_response.attrib:
                    if "true" in xml_response.attrib["success"]:                #check if succeeded:
                        for pod in xml_response.findall("pod"):
                            if "Result" in pod.attrib["title"] or "Solution" in pod.attrib["title"] or "Definition" in pod.attrib["title"] or "Basic properties" in pod.attrib["title"] or "Basic information" in pod.attrib["title"] or "Value" in pod.attrib["title"] or "Name" in pod.attrib["title"] or "Average result" in pod.attric["title"]: #fix this
                                response = pod.find("subpod").find("plaintext").text
                                response = response.encode('utf-8')
                                if response:
                                    #sanitze (better safe then sorry!)
                                    forbidden = ["\n", "\r", "\t", "\f", "\v"]
                                    for i in forbidden:
                                        response = response.replace(i, " ")
                                    response = response[0:300]
                                    response = "\x033[WOLFRAM ALPHA | " + response + "]" 
                                    main_ref.send_msg(msg_info["channel"], response)
                                    return
