# A plugin that rolls a random number based on a user-defined range.
from random import randrange


class roll():
  def roll(self, main_ref, msg_info):
    # Ignore private messages
    if msg_info["channel"] == main_ref.config['connection']['nick']:
      return None
    # Ignore if message does not contain module name
    if not msg_info["message"].startswith("!roll"):
      return None
    roll_number = msg_info["message"].replace("!roll", "")
    if not self.is_number(roll_number):
      main_ref.send_msg(msg_info["channel"], "Invalid syntax. Please call '!roll n' where n is an integer.")
      return None
    number = int(roll_number)
    if number < 2:
      return None
    response = msg_info["nick"] + " rolled a "
    response += str(randrange(number) + 1)
    response += "."
    main_ref.send_msg(msg_info["channel"], response)

  def is_number(self, s):
    try:
      int(s)
      return True
    except ValueError:
      return False
