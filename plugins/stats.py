#this plugin tacks number of lines written by users, on the channels the bot is connected to

import sqlite3
import settings
import time
import re

class stats():
    def stats(self, main_ref, msg_info):
        #we igonre prvt. messages
        if msg_info["channel"] == settings.NICK:
            return None

        #count up the number of lines and words
        self.add_line_n_words(msg_info["nick"], msg_info["message"])
        
    def update_req_time(self, nick):
        self.cursor.execute("UPDATE nickstats SET time_last_req=? WHERE nickname=?", (int(time.time()), nick))
        self.connection.commit()

    def add_line_n_words(self, nick, msg):
        self.cursor.execute("INSERT OR IGNORE INTO nickstats(nickname, init_time) VALUES(?,?)", (nick, int(round(time.time(),0))))
        self.cursor.execute("UPDATE nickstats SET lines = lines + 1 WHERE nickname=?", (nick,))
        #count words
        words = len(re.findall("\S+", msg))
        self.cursor.execute("UPDATE nickstats SET words = words + ? WHERE nickname=?", (words, nick))
        self.connection.commit()
        
    def __init__(self):
        db_path="plugins/stats.db"
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        #we first establish the table
        self.cursor.execute('CREATE TABLE if not exists nickstats (Id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, lines INT DEFAULT(0), words INT DEFAULT(0), init_time INT)')
        self.connection.commit()
