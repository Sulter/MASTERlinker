
#!/usr/bin/env python

import socket
import re
import collections
import logging
import threading
import time
import ssl
import sys
import getopt
import importlib
import traceback
import includes.helpers as helpers


class botframe():
  terminator = '\r\n'
  single_user = True

  def __init__(self, config):
    self.config = config
    self.commands = collections.deque()
    self.data_buffer = ""
    self.rexp_general = re.compile(r'^(:[^ ]+)?[ ]*([^ ]+)[ ]+([^ ].*)?$')
    self.connected = False

    self.msg_buffer = collections.deque()
    self.msg_send_time = 0

    self.channels = {chan: set() for chan in config['connection']['channel_list']}

    self.loaded_plugins = {}
    self.load_plugins()

    self.core_handlers = {
      'PING': self.handle_ping,
      'PRIVMSG': self.handle_privmsg,
      '353': self.handle_userlist,
      'JOIN': self.handle_join,
      'PART': self.handle_part,
      'NICK': self.handle_nick,
      'QUIT': self.handle_quit,
      'BURST': self.handle_burst,
    }
    self.burst = False  # Command syntax changes during burst mode

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
      self.irc.send('{}{}'.format(string, self.terminator).encode('utf-8'))
    except:
      logging.error('Send error')

  def connect(self):
    conf = self.config['connection']
    self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.irc.settimeout(conf['timeout'])
    if conf['ssl']:
      self.irc = ssl.wrap_socket(self.irc)
    try:
      self.irc.connect((conf['server'], conf['port']))
      self.connect_handshake()
      self.connected = True
    except socket.timeout as e:
      self.connected = False
      logging.warning(e)
      logging.info('Trying to reconnect')
      self.connect()

  def connect_handshake(self):
    conf = self.config['connection']
    self.send('NICK {nick}'.format(**conf))
    self.send('USER {nick} muh python bot'.format(**conf))
    if conf['identifymsg_enabled']:
      self.send('CAP REQ identify-msg')
      self.send('CAP END')
    if conf['nickserv_enabled']:
      self.send('PRIVMSG NickServ :IDENTIFY {nickserv_nick} {nickserv_pass}'.format(**conf))
      logging.info('Waiting for login...')
      time.sleep(15)  # this should be replaced by waiting for " 396 YourNick unaffiliated/youraccount :is now your hidden host (set by services.)", but that is not standard, so I'm not sure.
    time.sleep(2)
    # Join all channels
    for channel in conf['channel_list']:
      self.send('JOIN ' + channel)
    logging.info('Joining channels')

  def parse_command(self, data):
    rex = re.search(self.rexp_general, data)
    if rex is None:
      return
    command = rex.groups()
    logging.debug(command)
    try:
      sender, cmd, *params = command
      if sender:
        sender = sender[1:]
      if len(cmd) == 1 and params[0] == 'ENDBURST':  # For whatever reason inspircd has a space in the sender, making a mess of us
        self.burst = False
      elif cmd in self.core_handlers:
        self.core_handlers[cmd](sender, params[0])
    except BaseException as e:
      print('Handler error on command {} - {}'.format(command, e))
      traceback.print_exc()

  def handle_userlist(self, sender, params):
    nick, _, chan, *ul = params.split()
    if chan in self.channels:
      self.channels[chan] = set()
      for u in ul:
        n = u.lstrip(helpers.USER_CHARS)
        if n != self.config['connection']['nick']:
          self.channels[chan].add(n)
      self.call_plugin_handlers('handle_userlist', {'channel': chan, 'userlist': self.channels[chan]})

  def handle_join(self, sender, params):
    chan = params.lstrip(':')
    nick = sender.partition("!")[0]
    if chan in self.channels and nick != self.config['connection']['nick']:
      self.channels[chan].add(nick)
      self.call_plugin_handlers('handle_join', {'nick': nick, 'channel': chan})

  def handle_part(self, sender, params):
    chan, _, reason = params.partition(' ')
    if chan in self.channels:
      if reason:
        reason = reason[2:-1]
      nick = sender.partition("!")[0]
      try:
        self.channels[chan].remove(nick)
        self.call_plugin_handlers('handle_part', {'nick': nick, 'channel': chan, 'reason': reason})
      except KeyError:
        pass

  def handle_nick(self, sender, params):
    oldnick = sender.partition("!")[0].lstrip(helpers.USER_CHARS)
    nick = params.lstrip(helpers.USER_CHARS)
    for chan in self.channels:
      try:
        self.channels[chan].remove(oldnick)
        self.channels[chan].add(nick)
      except KeyError:
        pass
    self.call_plugin_handlers('handle_nick', {'nick': nick, 'oldnick': oldnick})

  def handle_quit(self, user, params):
    _, reason = params.split(' ', 1)  # Starts with ':Quit:', not wrapped in quotes
    nick = user.partition("!")[0]
    self.call_plugin_handlers('handle_quit', {'nick': nick, 'reason': reason})  # Plugins may want to check if the user was in channels
    for chan in self.channels:
      try:
        self.channels[chan].remove(nick)
      except KeyError:
        pass

  def handle_burst(self, sender, params):
    self.burst = True

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
    nick = sender.partition("!")[0]
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
      self.call_plugin_handlers('handle_pm', msg_data)
    else:
      self.call_plugin_handlers('handle_message', msg_data)

  def nick_in_channel(self, nick, channel):
    return nick in self.channels[channel]

  def send_msg(self, recipient, msg, sender=None):  # method for sending privmsg, takes care of timing etc. to prevent flooding
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
    parsed_msg = string.lstrip(current_channel).lstrip().lstrip(':')
    return helpers.sanitise_string(parsed_msg)

  def receive_com(self):
    # Parse commands from our command-buffer if *not* empty
    if self.commands:
      return self.commands.popleft()

    # Read data from the socket
    try:
      data = self.irc.recv(4096).decode('utf-8', errors="replace")
    except socket.error as e:
      logging.warning('Error receiving: {}'.format(e))
      return None

    # If the data is empty, the connection must be broken, we should reconnect
    if not len(data):
      logging.warning("Error with socket, pipe must be broken.")
      self.irc.close()
      logging.info('Trying to reconnect')
      self.connect()

    self.data_buffer = ''.join([self.data_buffer, data])
    # Each IRC command ends with "\r\n", so we split the whole string at those points
    self.commands = collections.deque(self.data_buffer.split(self.terminator))
    self.data_buffer = self.commands.pop()
    if not self.commands:
      return None
    return self.commands.popleft()

  def call_plugin_handlers(self, handler, data=None):
    for plugin_name, (instance, module) in self.loaded_plugins.items():
      try:
        if data:
          getattr(instance, handler)(data)
        else:
          getattr(instance, handler)()
      except BaseException as e:
        logging.error('Error in {} for plugin {}: {}'.format(handler, plugin_name, e))
        traceback.print_exc()

  def add_pseudouser(self, nick):
    return None

  def rename_pseudouser(self, oldnick, newnick):
    return None

  def remove_pseudouser(self, nick):
    pass

  def get_userlist(self, channel):
    if channel in self.channels:
      return self.channels[channel]

  def main(self):
    self.connect()
    while True:
      parsed_command = self.receive_com()
      while parsed_command is None:
        parsed_command = self.receive_com()
      self.parse_command(parsed_command)
