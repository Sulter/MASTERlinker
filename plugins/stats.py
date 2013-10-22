import sqlite3
import re
import settings
import time

class stats():
    def stats(self, main_ref, msg_info):
        #we check for commands in private messages
        if msg_info["channel"] == settings.NICK:
            self.parse_msg(msg_info, main_ref)
            return None

        #count up the number of lines
        self.add_line(msg_info["nick"])
        
    def parse_msg(self, msg_info, main_ref):
        #first we make sure the string is encoded, if it can't be, we just ignore this private message
        try:
            msg = msg_info["message"]
            msg = msg.encode('utf-8')
        except:
            return None

        #make sure that this user hasn't made request in the last, couple of seconds (to prevent flooding)
        self.cursor.execute("INSERT OR IGNORE INTO nickstats(nickname) VALUES(?)", (msg_info["nick"],))
        self.connection.commit()
        result = self.cursor.execute("SELECT time_last_req FROM nickstats WHERE nickname =?", (msg_info["nick"],))
        result = result.fetchall()
        if result[0][0]+5 > int(time.time()):
            return None
        
        top5 = re.search("^\^top3", msg)
        if top5 is not None:
            result = self.cursor.execute("SELECT nickname,lines FROM nickstats ORDER BY lines DESC")
            string = ""
            for i, row in enumerate(result.fetchall()[:3]):
                string = string + str(i+1) + ") " + row[0] + " lines:" + str(row[1]) + " | "
                
            main_ref.send_msg(msg_info["nick"], string)
            self.update_req_time(msg_info["nick"])
            return None
        
        nick_stat = re.search("^(\^nick) (\S+)", msg)
        if nick_stat is not None:
            result = self.cursor.execute("SELECT nickname,lines FROM nickstats WHERE nickname=?", (nick_stat.group(2),))
            if result:
                for row in result.fetchall():
                    string = row[0] + ": " + str(row[1]) + "lines"
                    main_ref.send_msg(msg_info["nick"], string)
                    self.update_req_time(msg_info["nick"])
                    return None


        info = re.search("^(info)", msg)
        if info is not None:
            string = "************************ THIS IS THE STATS PLUGIN OF " + settings.NICK  + " ************************"
            main_ref.send_msg(msg_info["nick"], string)
            string = "All commands start with ^"
            main_ref.send_msg(msg_info["nick"], string)
            string = "^top3 - get top 3 of people with most lines"
            main_ref.send_msg(msg_info["nick"], string)
            string = "^nick <nickname> - get the current ranking of <nickname>"
            main_ref.send_msg(msg_info["nick"], string)
            self.update_req_time(msg_info["nick"])
            return None

    def update_req_time(self, nick):
        self.cursor.execute("UPDATE nickstats SET time_last_req=? WHERE nickname=?", (int(time.time()), nick))
        self.connection.commit()

    def add_line(self, nick):
        self.cursor.execute("INSERT OR IGNORE INTO nickstats(nickname) VALUES(?)", (nick,))
        self.cursor.execute("UPDATE nickstats SET lines = lines + 1 WHERE nickname=?", (nick,))
        self.connection.commit()
        
    def __init__(self):
        db_path="plugins/stats.db"
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        #we first establish the table
        self.cursor.execute('CREATE TABLE if not exists nickstats (Id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, lines INT DEFAULT(0), time_last_req INT DEFAULT(0))')
        self.connection.commit()
