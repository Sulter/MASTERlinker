#!/usr/bin/env python

import socket
import re
import collections
import logging
import threading
import time
import ssl
import sys
import importlib
import unicodedata
import includes.helpers as helpers


class botframe():
  def __init__(self, config):
    self.config = config
    self.commands = collections.deque()
    self.data_buffer = ""
    self.rexp_general = re.compile(r'^(:[^ ]+)?[ ]*([^ ]+)[ ]+([^ ].*)?$')

    self.msg_buffer = collections.deque()
    self.msg_send_time = 0

    self.loaded_plugins = {}
    self.load_plugins()

  def load_plugins(self):
    for plugin in self.config['plugins']:
      self.import_plugin(plugin)

  def reload_plugins(self, plugin_list=None):
    logging.info('Attempting to reload all plugins')
    importlib.invalidate_caches()
    if plugin_list:
      for plugin in plugin_list:
        self.reload_plugin(plugin, True)
    else:
      for plugin in self.loaded_plugins.keys():
        self.reload_plugin(plugin, True)

  def reload_plugin(self, plugin, skip_invalidate=False):
    if not skip_invalidate:
      importlib.invalidate_caches()
    try:
      module_ref = self.loaded_plugins[plugin][1]
      module_ref = importlib.reload(module_ref)
      inst_ref = getattr(module_ref, plugin)(self)
      self.loaded_plugins[plugin] = (inst_ref, module_ref)
      logging.info('Reloaded plugin {}.'.format(plugin))
    except BaseException as e:
      logging.error('Unable to reload plugin {}: {}'.format(plugin, e))

  def unload_plugin(self, plugin):
    if plugin in self.loaded_plugins:
      try:
        del self.loaded_plugins[plugin]
        logging.info('Unloaded plugin {}.'.format(plugin))
      except BaseException as e:
        logging.error('Unable to unload plugin {}: {}'.format(plugin, e))
    else:
      logging.warning('Plugin not loaded: {}'.format(plugin))

  def import_plugin(self, plugin):
    try:
      module_ref = importlib.import_module('plugins.{}'.format(plugin))
      inst_ref = getattr(module_ref, plugin)(self)
      self.loaded_plugins[plugin] = (inst_ref, module_ref)
      logging.info('Loaded plugin {}.'.format(plugin))
    except BaseException as e:
      logging.error('Unable to load plugin {}: {}'.format(plugin, e))

  def send(self, string):
    try:
      self.irc.send(bytes(string+'\r\n', 'utf-8'))
    except:
      logging.error('Send error')

  def connect(self):
    conf = self.config['connection']
    self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if conf['ssl']:
      self.irc = ssl.wrap_socket(self.irc)
    try:
      self.irc.connect((conf['server'], conf['port']))
      self.send('NICK {nick}'.format(**conf))
      self.send('USER {nick} muh python bot'.format(**conf))
      if conf['identifymsg_enabled']:
        self.send('CAP REQ identify-msg')
        self.send('CAP END')
      if conf['nickserv_enabled']:
        self.send('PRIVMSG NickServ :IDENTIFY {nickserv_nick} {nickserv_pass}'.format(**conf))
        logging.info('Waiting for login...')
        time.sleep(15)  # this should be replaced by waiting for " 396 YourNick unaffiliated/youraccount :is now your hidden host (set by services.)", but that is not standard, so I'm not sure.
      # Join all channels
      logging.info('Joining channels')
      for channel in conf['channel_list']:
        self.send('JOIN ' + channel)
    except socket.timeout as e:
      logging.warning(format(e.errno, e.strerror))
      logging.info('Trying to reconnect')
      self.connect()

  def parse_command(self, data):
    rex = re.search(self.rexp_general, data)
    if rex is None:
      return
    command = rex.groups()
    sender, cmd, params, *overflow = command
    logging.debug(command)
    handlers = {
      'PING': self.handle_ping,
      'PRIVMSG': self.handle_privmsg,
    }
    if cmd in handlers:
      handlers[cmd](sender, params)

  def handle_ping(self, sender, params):
    try:
        self.send('PONG ' + params)
    except:
        self.irc.close()
        logging.warning("Error with sockets: ", sys.exc_info()[0])
        logging.info('Trying to reconnect')
        self.connect()

  def handle_privmsg(self, sender, params):
    # Get the nick, channel (doesn't have to be channel) and message.
    nick = sender.lstrip(":").partition("!")[0]
    # Don't do anything if nick is on ignore list
    if nick in self.config['connection']['ignore_list']:
      return
    channel = re.search(r"^[\S]+", params).group()
    msg = self.get_msg(params, channel)
    if self.config['connection']['identifymsg_enabled']:
      ident = (msg[0] == '+')
      msg = msg[1:]
      msg_data = {'message': msg, 'nick': nick, 'channel': channel, 'ident': ident}
      # Admin commands which don't belong in plugins
      if ident and nick in self.config['connection']['admin_list']:
        if msg == '!reload':
          self.reload_plugins()
        elif msg.startswith('!reload '):
          plugin_list = msg[8:].split(', ')
          self.reload_plugins(plugin_list)
    else:
      msg_data = {'message': msg, 'nick': nick, 'channel': channel}

    # Call all the modules
    if msg_data['channel'] == self.config['connection']['nick']:
      handler = 'handle_pm'
    else:
      handler = 'handle_message'
    for plugin_name, (instance, module) in self.loaded_plugins.items():
      try:
        getattr(instance, handler)(msg_data)
      except BaseException as e:
        logging.error('Error in {} for plugin {}: {}'.format(handler, plugin_name, e))

  def send_msg(self, recipient, msg):  # method for sending privmsg, takes care of timing etc. to prevent flooding
    command = 'PRIVMSG {} :{}'.format(recipient, msg)
    self.msg_buffer.append(command)

    # Schedule the message to be send, depending on the buffer size, 1message each 2 seconds.
    buffer_size = len(self.msg_buffer)
    if buffer_size < 2:
      self.msg_time_diff = 2 - (time.time() - self.msg_send_time)
      if self.msg_time_diff > 0:
        self.send_from_buffer()  # send the message momentary
      else:
        t = threading.Timer(self.msg_time_diff, self.send_from_buffer)  # schedule for sending later (at least 2 seconds since last message)
        t.start()
    else:
      t = threading.Timer(self.msg_time_diff + (2 * (buffer_size - 1)), self.send_from_buffer)
      t.start()

  def send_from_buffer(self):
    command = self.msg_buffer.popleft()
    try:
      self.send(command)
    except:
      self.irc.close()
      logging.warning("Error with sockets: ", sys.exc_info()[0])
      logging.info('Trying to reconnect')
      self.connect()
    self.msg_send_time = time.time()

  def get_msg(self, string, current_channel):
    # Remove channel name, and the : that is the prefix of the message
    parsed_msg = string.lstrip(current_channel)
    parsed_msg = parsed_msg.lstrip()
    parsed_msg = parsed_msg.lstrip(":")
    # Sanitize from formatting (color codes etc.) - thank you Kuraitou
    #parsed_msg = re.sub('(\x02)|(\x07)|(\x0F)|(\x16)|(\x1F)|(\x03(\d{1,2}(,\d{1,2})?)?)', '', parsed_msg)
    # Following unicode categories are unwanted:
    #  Cc = Other, control
    #  Cf = Other, format
    #  Cs = Other, surrogate
    #  Co = Other, private use
    #  Cn = Other, not assigned (including noncharacters)
    # Following should be replaced with standard spaces
    #  Zs = Separator, space
    #  Zl = Separator, line
    #  Zp = Separator, paragraph
    parsed_msg = re.sub('(\x03(\d{1,2}(,\d{1,2})?)?)', '', parsed_msg)  # Keep this for stripping colour
    msg_list = []
    for c in parsed_msg:
      category = unicodedata.category(c)[0]  # First letter is enough to judge
      if category == 'C':
        continue  # Filthy nonprintable!
      elif category == 'Z':
        msg_list.append(' ')
      else:
        msg_list.append(c)
    msg = ''.join(msg_list)
    return msg

  def receive_com(self):
    # Parse commands from our command-buffer if *not* empty
    if self.commands:
      return self.commands.popleft()

    # Read data from the socket
    data = self.irc.recv(4096).decode('utf-8', errors="replace")

    # If the data is empty, the connection must be broken, we should reconnect
    if not len(data):
      logging.warning("Error with socket, pipe must be broken.")
      self.irc.close()
      logging.info('Trying to reconnect')
      self.connect()

    self.data_buffer = ''.join([self.data_buffer, data])
    # Each IRC command ends with "\r\n", so we split the whole string at those points
    self.commands = collections.deque(self.data_buffer.split("\r\n"))
    self.data_buffer = self.commands.pop()
    if not self.commands:
      return None

    result = self.commands.popleft()
    return result

  def main(self):
    self.connect()

    while True:
      parsed_command = self.receive_com()
      while parsed_command is None:
        parsed_command = self.receive_com()

      self.parse_command(parsed_command)

default_config = {
  'connection': {
    'server': "irc.freenode.org",
    'port': 6667,  # SSL freenode: 6697 , default: (6667)
    'ssl': False,  # SSL - False = off, True = on
    'nick': "MASTERlinker",
    'nickserv_enabled': False,  # Nickserv authentification - False = off, True = on
    'nickserv_nick': "MASTERlinker",
    'nickserv_pass': "password",
    'identifymsg_enabled': True,  # Prefixes messages with + if the user is identified, - if not. May not work outside Freenode.
    'channel_list': ["#ufeff"],
    'ignore_list': ["VidyaLink", "uglycharlie", "prettybenny", "Moebot", "pikatwo"],
    'admin_list': ["Birdulon"],
  },
  'logging_level': "DEBUG",  # DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL

  # Plugins to load on startup
  'plugins': ["url_info_finder", "about", "seen", "stats", "BTC"],

  'api_keys': {
    'youtube': "Youtube Data API key",
    'wolfram_alpha': "Wolfram Alpha API key",
  },
}
"""
stream_channels = channel_list
streamers = []
streamers = [
("https://api.twitch.tv/kraken/streams/ChannelName", "Nickname", "http://www.twitch.tv/ChannelName"),
("http://api.justin.tv/api/stream/list.json?channel=ChannelName", "Nickname", "http://www.justin.tv/ChannelName"),
]
"""


if __name__ == '__main__':
  config = helpers.parse_config('settings.json', default_config)
  logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', filename='ircbot.log',
                      level=getattr(logging, config['logging_level']))
  ircbot = botframe(config)
  ircbot.main()
