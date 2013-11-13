MASTERlinker
============

python irc-bot

plugins info:
MODULES MUST HAVE SAME NAME AS THEIR MAIN FUNCTTION, that function is the only one that will get called. 
That functions also needs to take two arguments, the first will be a instance of the mainframe, the other will be a dictionary with three key/variables:
"channel" = who/what the message is from (it can both be a channel, or a nickname of a user, if it was a private message)
"nick" = the nickname of the person who send the message
"message" = the message 
check the plugin "respond" for an easy ovierview.
