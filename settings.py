# Minimal set of config variables
SERVER = "irc.freenode.org"
PORT = 6667                         # SSL freenode: 6697 , default: (6667)
NICK = "BotName"
channel_list = ["#bottest"]
ignore_list = ["VidyaLink", "uglycharlie", "prettybenny", "Moebot"]
logging_level = "DEBUG"             # DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL

# SSL and nickserv config
SSL = False                         # SSL - False = off, True = on
nick_serv_on = False                # Nickserver - False = off, True = on
nick_serv_nick = "nick"
nick_serv_pass = "password"

# Plugins to load
plugins = ["csgobetting", "url_info_finder", "roll", "about", "seen", "stats"]

# API keys
yt_api_key = "Youtube Data API key"
wa_api_key = "Wolfram Alpha API key"

stream_channels = channel_list
streamers = [
("https://api.twitch.tv/kraken/streams/ChannelName", "Nickname", "http://www.twitch.tv/ChannelName"),
("http://api.justin.tv/api/stream/list.json?channel=ChannelName", "Nickname", "http://www.justin.tv/ChannelName"),
]
