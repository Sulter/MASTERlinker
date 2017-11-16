# A plugin that rolls a random number based on a user-defined range.
import includes.helpers as helpers
from random import randrange


class roll(helpers.Plugin):
  def handle_pm(self, msg_data):
    # Ignore private messages
    pass

  def handle_message(self, msg_data):
    # Ignore if message does not contain module name
    if not msg_data["message"].startswith("!roll"):
      return None
    roll_number = msg_data["message"].replace("!roll", "")
    if not self.is_number(roll_number):
      self.parent.send_msg(msg_data["channel"], "Invalid syntax. Please call '!roll n' where n is an integer.")
      return None
    number = int(roll_number)
    if number < 2:
      return None
    response = msg_data["nick"] + " rolled a "
    response += str(randrange(number) + 1)
    response += "."
    self.parent.send_msg(msg_data["channel"], response)

  def is_number(self, s):
    try:
      int(s)
      return True
    except ValueError:
      return False
