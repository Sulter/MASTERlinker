# A plugin that tracks number of lines and words written by users
import sqlite3
import time
import re
import random


class stats():
  def stats(self, main_ref, msg_info):
    # Ignore private messages
    if msg_info["channel"] == main_ref.config['connection']['nick']:
      return None
    # Ignore if message does not contain module name
    if msg_info["message"].startswith("!stats"):
      self.print_user_stats(main_ref, msg_info)
    else:
      self.add_line_n_words(msg_info["nick"], msg_info["message"])

  def __init__(self):
    db_path = "database/stats.db"
    self.connection = sqlite3.connect(db_path)
    self.cursor = self.connection.cursor()
    self.cursor.execute(
      'CREATE TABLE IF NOT EXISTS nickstats (Id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, lines INT DEFAULT(0), words INT DEFAULT(0), init_time INT, random_quote TEXT)')
    self.connection.commit()

  def add_line_n_words(self, nick, msg):
    self.cursor.execute("INSERT OR IGNORE INTO nickstats(nickname, init_time) VALUES(?,?)",
              (nick, int(round(time.time(), 0))))
    self.cursor.execute("UPDATE nickstats SET lines = lines + 1 WHERE nickname=?", (nick,))
    # Count words
    words = len(re.findall("\S+", msg))
    self.cursor.execute("UPDATE nickstats SET words = words + ? WHERE nickname=?", (words, nick))
    self.connection.commit()
    # There is x chance that this phrase will be added as that persons "quote"
    if random.random() > 0.99:
      try:  # catching encoding errors
        self.cursor.execute("UPDATE nickstats SET random_quote=? WHERE nickname=?", (msg, nick))
        self.connection.commit()
      except:
        return None

  def print_user_stats(self, main_ref, msg_info):
    try:
      self.cursor.execute("SELECT words, lines FROM nickstats WHERE nickname=?", (msg_info["nick"],))
    except:
      return None
    row = self.cursor.fetchone()
    if not row:
      words = 0
      lines = 0
    else:
      words = row[0]
      lines = row[1]

    response = "Counting " + str(words) + " words in " + str(lines) + " lines"
    main_ref.send_msg(msg_info["channel"], response)
