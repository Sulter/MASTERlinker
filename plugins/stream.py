# Sends a message to channels, when someone starts streaming. Currently supports twitch.tv and justin.tv

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
        self.streamer_list = []
        for stream in settings.streamers:
            self.streamer_list.append(streamer(stream[0], stream[1], stream[2]))

    def check_streams(self):
        for streamer in self.streamer_list:
            self.check_stream(streamer)

    def check_stream(self, streamer):
        # check if we have a reference to the main module

        if not hasattr(self, 'main_ref'):
            return None

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
                    for chan in settings.stream_channels:
                        self.main_ref.send_msg(chan, string[0:450])
                else:
                    print "some error with stream: on user: " + streamer.name
            elif streamer.online is True and not result["stream"]:
                streamer.online = False

        elif "justin.tv" in streamer.api_url:
            if result and streamer.online is False:
                streamer.online = True
                string = "\x033|STREAM| " + streamer.name + " is streaming " + (result[0])[
                    "title"] + " at " + streamer.link
                for chan in settings.stream_channels:
                    self.main_ref.send_msg(chan, string[0:450])
            elif streamer.online is True and not result:
                streamer.online = False

    def stream(self, main_ref, msg_info):
        self.main_ref = main_ref
        return None
