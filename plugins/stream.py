#simple example of how a plugin should look like
#this plugin simply makes the bot responde with a simple string to every message received.

import time
import threading
import simplejson
import urllib2

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
        self.channel = "#vidyadev"
        self.streamer_list = [streamer("https://api.twitch.tv/kraken/streams/argoneus", "argoneus", "http://www.twitch.tv/argoneus"), streamer("https://api.twitch.tv/kraken/streams/satatami", "Plesioth", "http://www.twitch.tv/satatami"), streamer("http://api.justin.tv/api/stream/list.json?channel=streamingstrandberg", "sstrandberg", "http://www.justin.tv/streamingstrandberg"), streamer("https://api.twitch.tv/kraken/streams/mechacrash", "MechaCrash", "http://www.twitch.tv/mechacrash"), streamer("https://api.twitch.tv/kraken/streams/mortvert_", "Mortvert", "http://twitch.tv/mortvert_")]

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
                if string:
                    self.main_ref.send_msg(self.channel, string[0:450]) 
                else:
                    print "some error with stream: on user: " + streamer.name
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
        return None
