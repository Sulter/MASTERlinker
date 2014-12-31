# A plugin that gives when the bot last saw the user.
import settings
import sqlite3
import time

class seen():
        # Main function.
        def seen(self, main_ref, msg_info):
                # We'll guard against PMs.
                if msg_info["channel"] == settings.NICK:
                        return None
                #we update the seen time of this nick
                self.update(msg_info["nick"])
                #Don't do anything else for msg not starting with !seen
                if not msg_info["message"].startswith("!seen"):
                        return None
		#handle msg with seen
		self.handleSeen(main_ref, msg_info)

	#update the time for nick
	def update(self, nick):
		nick = nick.lower()
		t = int(time.time())
		#for first time use of nick
		self.cursor.execute("INSERT OR IGNORE INTO seen(nickname, last_time) VALUES(?,?)", (nick, t))
		#nick already there
		self.cursor.execute("UPDATE seen SET last_time=? WHERE nickname=?", (t, nick))
		self.connection.commit()
		
	#Handles !seen
	def handleSeen(self, main_ref, msg_info):
		response = ""
		#Get the nick and strip its spaces.
		nick = msg_info["message"].replace("!seen", "")
		nick = nick.replace(" ", "")
		nick = nick.lower()

		#look for nick in db
		self.cursor.execute("SELECT last_time FROM seen WHERE nickname=?", (nick,))
		row = self.cursor.fetchone()
		if not row:#doesn't exist
                        response = "I haven't seen " + nick + "."
		else:#exists
			t = row[0]
			timeString = time.strftime("%H:%M %d-%m-%y", time.gmtime(t))
                        response = "I saw " + nick + " " + timeString

		#Output response
		main_ref.send_msg(msg_info["channel"], response)

	#creates 
	def __init__(self):
		db_path="plugins/seen.db"
		self.connection = sqlite3.connect(db_path)
		self.cursor = self.connection.cursor()
                #we first establish the table
		self.cursor.execute('CREATE TABLE IF NOT EXISTS seen '
				    '(Id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, last_time INT)')
		self.connection.commit()

