# A plugin that gives when the bot last saw the user

import settings
import sqlite3
import time
import datetime


class seen():
    def seen(self, main_ref, msg_info):
        # Ignore private messages
        if msg_info["channel"] == settings.NICK:
            return None
        # We update the seen time of this nick
        self.update(msg_info["nick"])
        # Ignore if message does not contain module name
        if not msg_info["message"].startswith("!seen"):
            return None
        self.handle_seen(main_ref, msg_info)

    def __init__(self):
        db_path = "database/seen.db"
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS seen '
                            '(Id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, last_time INT)')
        self.connection.commit()

    def update(self, nick):
        nick = nick.lower()
        t = int(time.time())
        self.cursor.execute("INSERT OR IGNORE INTO seen(nickname, last_time) VALUES(?,?)", (nick, t))
        self.cursor.execute("UPDATE seen SET last_time=? WHERE nickname=?", (t, nick))
        self.connection.commit()

    def handle_seen(self, main_ref, msg_info):
        # Get the nick and strip its spaces.
        nick = msg_info["message"].replace("!seen", "")
        nick = nick.replace(" ", "")
        nick = nick.lower()

        try:
            self.cursor.execute("SELECT last_time FROM seen WHERE nickname=?", (nick,))
        except:
            return None
        row = self.cursor.fetchone()
        if not row:
            response = "I haven't seen " + nick + "."
        else:
            t = row[0]
            time_now = int(time.time())
            diff = time_now - t
            time_string = str(datetime.timedelta(seconds=diff))
            response = "I saw " + nick + " " + time_string + " ago"

        main_ref.send_msg(msg_info["channel"], response)
