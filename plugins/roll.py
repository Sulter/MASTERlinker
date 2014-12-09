# A plugin that rolls a random number based on a user-defined range.
from random import randrange
import settings

class roll():
	# Main function.
	def roll(self, main_ref, msg_info):
		# We'll guard against PMs.
		if msg_info["channel"] == settings.NICK:
			return None
		#We'll also ignore any calls not starting with !roll.
		if not msg_info["message"].startswith("!roll"):
			return None
		#We'll get the string without the !roll call...
		input = msg_info["message"].replace("!roll", "")
		#If the string is not a number, we'll ignore the call.
		if not self.is_number(input):
			main_ref.send_msg(msg_info["channel"], "Invalid syntax. Please call '!roll n' where n is an integer.")
			return None
		number = int(input)
		#Check if the number is over 1.
		if (number < 2):
			return None
		#Generate a random number and output it.
		response = msg_info["nick"] + " rolled a "
		response += str(randrange(number) + 1)
		response += "."
		main_ref.send_msg(msg_info["channel"], response)

	# Returns whether or not the string is a number based on if the cast errors.
	def is_number(self, s):
		try:
			int(s)
			return True
		except ValueError:
			return False
