#basic variables required for the bot to connect and work
SERVER = "irc.freenode.org"
PORT = 6667 #ssl freenode: 6697
NICK = "MASTERlinker"
channel_list = ["#testchannel200", "#testchannel201"]
ignore_list = ["VidyaLink", "uglycharlie", "prettybenny"]
logging_level = "DEBUG" #DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL
#SSL - False = off, True = on
SSL = False
#nickserver - False = off, True = on
nick_serv_on = False
nick_serv_nick = "nickname"
nick_serv_pass = "password"
#plugins to load:
# -IMPORTANT NOTICE-
#MODULES MUST HAVE SAME NAME AS THEIR MAIN FUNCTTION, that function is the only one that will get called
#that functions also needs to take two arguments, the first will be a instance of the mainframe, the other will be a dictionary with three key/variables:
#"channel" = who/what the message is from (it can both be a channel, or a nickname of a user, if it was a private message)
#"nick" = the nickname of the person who send the message
#"message" = the message
plugins = ["url_info_finder", "respond"]
#plugin-variables:
yt_api_key = "the google API-key"
wa_api_key = "the wolfram API-key"
url_sqlite3_db = "plugins/url_sql3.db"
