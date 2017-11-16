# simple example of how a plugin should look like, this plugin simply makes the bot respond with a simple string to every message received.
import includes.helpers as helpers


class respond(helpers.Plugin):
  def handle_message(self, msg_data):
    response = "What did you say to me, " + msg_data["nick"] + "?!"
    self.parent.send_msg(msg_data["channel"], response)
