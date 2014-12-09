# A plugin that gives when the bot last saw the user.
import settings
from datetime import datetime
from time import gmtime, strftime

class seen():
	# Main function.
	def seen(self, main_ref, msg_info):
		# We'll guard against PMs.
		if msg_info["channel"] == settings.NICK:
			return None
		#We'll also ignore any calls not starting with !seen.
		if not msg_info["message"].startswith("!seen"):
			return None
		#Call the respective functions.
		self.managedict(main_ref, msg_info)
		self.handleseen(main_ref, msg_info)
		
	#Manages the dictionary.
	def managedict(self, main_ref, msg_info):
		#Check to see if the dictionary is properly loaded.
		self.checkdict()
		#Update the data.
		self.userdict[msg_info["nick"]] = datetime.now()
		
	#Handles !seen
	def handleseen(self, main_ref, msg_info):
		#Check to see if the dictionary is properly loaded.
		self.checkdict()
		#We'll ignore any calls not starting with !seen.
		if not msg_info["message"].startswith("!seen"):
			return None
		#Get the nick and strip its spaces.
		nick = msg_info["message"].replace("!seen", "")
		nick = nick.replace(" ", "")
		#Determine the response.
		if nick in self.userdict:
			response = nick + " was last seen: "	+ strftime("%H:%M:%S %m-%d-%Y", gmtime())
		else:
			response = "I haven't seen " + nick + "."
		#Output response
		main_ref.send_msg(msg_info["channel"], response)

	#Saves the list to file.
	def savelist(self):
		#I don't know enough python to figure out the best way to handle this right now. A database may be the best solution as far as performance is concerned.
		dummy = 0 #To solve the crashes

	#Loads the list from file.
	def loadlist(self):
		#See savelist.
		dummy = 0 #To solve the crashes

	#Checks if the dict exists, and if it doesn't, create and load it.
	def checkdict(self):
		try:
  			self.userdict = self.userdict
		except AttributeError:
  			self.userdict = {}
			self.loadlist()

