#annouces when one of the "streamers" starts streaming.

import time
import threading
import simplejson
import urllib2
import settings

def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

class streamer():
    def __init__(self, api_url, name, link):
        self.api_url = api_url
        self.name = name
        self.online = False
        self.link = link

class stream():

    def __init__(self):
        set_interval(self.check_streams, 60) 
        self.channel = "#vidyadev"   #!should take all this info from settings.py!********
        self.streamer_list = [streamer("https://api.twitch.tv/kraken/streams/argoneus", "argoneus", "http://www.twitch.tv/argoneus"), streamer("https://api.twitch.tv/kraken/streams/satatami", "Plesioth", "http://www.twitch.tv/satatami"), streamer("http://api.justin.tv/api/stream/list.json?channel=streamingstrandberg", "ssstrandberg", "http://www.justin.tv/streamingstrandberg"), streamer("https://api.twitch.tv/kraken/streams/mechacrash", "MechaCrash", "http://www.twitch.tv/mechacrash"), streamer("https://api.twitch.tv/kraken/streams/mortvert_", "Mortvert", "http://twitch.tv/mortvert_")]

    def check_streams(self):
        for streamer in self.streamer_list:
            self.check_stream(streamer)        
    
    def check_stream(self, streamer):
        try:
            result = simplejson.load(urllib2.urlopen(streamer.api_url))
        except:
            return None
        
        if "twitch.tv" in streamer.api_url:
            if result["stream"] and streamer.online is False:
                streamer.online = True
                title = ""
                if (result["stream"])["game"]:
                    title = (result["stream"])["game"]
                string = "\x033|STREAM| " + streamer.name + " is streaming " + title + " at " + streamer.link
                self.main_ref.send_msg(self.channel, string[0:450]) 
            elif streamer.online is True and not result["stream"]:
                streamer.online = False
                
        elif "justin.tv" in streamer.api_url:
            if result and streamer.online is False:
                streamer.online = True
                string = "\x033|STREAM| " + streamer.name + " is streaming " + (result[0])["title"] + " at " + streamer.link
                self.main_ref.send_msg(self.channel, string[0:450]) 
            elif streamer.online is True and not result:
                streamer.online = False

    def stream(self, main_ref, msg_info):
        self.main_ref = main_ref
        if msg_info["channel"] == settings.NICK:
            self.parse_msg(msg_info)
            return None

    def parse_msg(self, msg_info): #WIP
        if "!stream" in msg_info["message"]:
            return None
