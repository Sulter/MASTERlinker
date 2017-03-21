# A plugin that counts csgobetting mentions

import settings
import sqlite3


class csgobetting():
    def csgobetting(self, main_ref, msg_info):
        # Ignore private messages
        if msg_info["channel"] == settings.NICK:
            return None
        # Ignore if message does not contain module name
        if "csgobetting" not in msg_info["message"].lower():
            return None

        # Print all stats if called as module, else print short response for counter
        if msg_info["message"].startswith("!csgobetting"):
            self.print_user_stats(main_ref, msg_info)
        else:
            self.increment_couter(main_ref, msg_info)

    def __init__(self):
        db_path = "database/csgobetting.db"
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            'CREATE TABLE IF NOT EXISTS csgobetting (id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, count INT)')
        self.connection.commit()

    def increment_couter(self, main_ref, msg_info):
        nick = msg_info["nick"].lower()
        try:
            self.cursor.execute("SELECT count FROM csgobetting WHERE nickname=?", (nick,))
        except:  # catch non utf8 errors
            return None
        row = self.cursor.fetchone()
        if not row:
            count = 0
            self.cursor.execute("INSERT OR IGNORE INTO csgobetting(nickname, count) VALUES(?,?)", (nick, count))
        else:
            count = row[0] + 1
            self.cursor.execute("UPDATE csgobetting SET count=? WHERE nickname=?", (count, nick))
        self.connection.commit()

        response = "Counting " + str(self.get_total()) + " total http://csgobetting.com/ mentions"
        main_ref.send_msg(msg_info["channel"], response)

    def print_user_stats(self, main_ref, msg_info):
        nick = msg_info["nick"]
        try:
            self.cursor.execute("SELECT count FROM csgobetting WHERE nickname=?", (nick,))
        except:
            return None
        row = self.cursor.fetchone()
        if not row:
            response = "You did not mention csgobetting not even once, better start working on it!"
        else:
            response = "Counting " + str(row[0]) + " http://csgobetting.com/ mentions from " + nick

        main_ref.send_msg(msg_info["channel"], response)

    def get_total(self):
        try:
            self.cursor.execute("SELECT SUM(count) AS total FROM csgobetting")
        except:
            return None
        row = self.cursor.fetchone()
        if not row:
            total = 0
        else:
            total = row[0] + 1
        return total
