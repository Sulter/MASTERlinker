# simple example of how a plugin should look like, this plugin simply makes the bot respond with a simple string to every message received.
class respond():
    def respond(self, main_ref, msg_info):
        response = "What did you say to me, " + msg_info["nick"] + "?!"
        main_ref.send_msg(msg_info["channel"], response)
