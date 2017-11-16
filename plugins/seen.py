# A plugin that gives when the bot last saw the user
import includes.helpers as helpers
import sqlite3
import time
import datetime
import logging


class seen(helpers.Plugin):
  def __init__(self, parent):
    super().__init__(parent)
    default_config = {
      'name_replacements': {}
    }
    self.config = helpers.parse_config('settings_seen.json', default_config)
    db_path = "database/seen.db"
    self.connection = sqlite3.connect(db_path)
    self.cursor = self.connection.cursor()
    self.cursor.execute('CREATE TABLE IF NOT EXISTS seen '
              '(Id INTEGER PRIMARY KEY, nickname TEXT UNIQUE, last_time INT)')
    self.connection.commit()

  def handle_message(self, msg_data):
    # We update the seen time of this nick
    self.update(msg_data["nick"])
    # Ignore if message does not contain module name
    if not msg_data["message"].startswith("!seen"):
      return None
    self.handle_seen(msg_data)

  def update(self, nick):
    nick = nick.lower()
    t = int(time.time())
    self.cursor.execute("INSERT OR IGNORE INTO seen(nickname, last_time) VALUES(?,?)", (nick, t))
    self.cursor.execute("UPDATE seen SET last_time=? WHERE nickname=?", (t, nick))
    self.connection.commit()

  def handle_seen(self, msg_data):
    # Get the nick and strip its spaces.
    nick = msg_data["message"].replace("!seen", "")
    nick = nick.replace(" ", "")
    matching_nick = nick.lower()
    if matching_nick in self.config['name_replacements']:
      nick = self.config['name_replacements'][nick]
      matching_nick = nick.lower()

    if matching_nick == msg_data['nick'].lower():
      response = "I see you, {}.".format(nick)
    elif matching_nick == self.parent.config['connection']['nick'][:16].lower():
      response = "I see me in every way there is to be seen, perceiving all that is within {}.".format(nick)
    else:
      try:
        self.cursor.execute("SELECT last_time FROM seen WHERE nickname=?", (matching_nick,))
      except BaseException as e:
        logging.error('Error in Seen: {}'.format(e))
        return None
      row = self.cursor.fetchone()
      if not row:
        response = "I haven't seen {}.".format(nick)
      else:
        t = row[0]
        time_now = int(time.time())
        diff = time_now - t
        time_str = helpers.time_string(datetime.timedelta(seconds=diff))
        response = "I saw {} {}".format(nick, time_str)

    self.parent.send_msg(msg_data["channel"], response)
