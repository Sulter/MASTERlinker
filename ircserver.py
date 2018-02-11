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
from botframe import botframe

User = collections.namedtuple('User', ['UID', 'nick', 'mask', 'modes'])
Pseudoclient = collections.namedtuple('Pseudoclient', ['UID', 'nick', 'usermask', 'hostmask', 'desc', 'channels'])


class ircserver(botframe):
  terminator = '\n'
  single_user = False

  def __init__(self, config):
    self.pseudoclients = {}
    self.pseudoclient_nicks = {}
    conf = config['connection']
    self.users = {}
    self.available_UIDs = set()
    self.generate_uid = helpers.generate_uid(conf['max_pseudoclients'], self.available_UIDs, conf['SID'])
    self.version = 'MASTERlinker {server_name}'.format(**conf)
    self.Qlines = []

    super().__init__(config)
    self.core_handlers['UID'] = self.handle_uid
    self.core_handlers['FJOIN'] = self.handle_join


  def recycle_UID(self, UID):
    self.available_UIDs.add(UID)

  def send(self, string):
    super().send(':{}'.format(string))

  def connect_handshake(self):
    conf = self.config['connection']
    self.irc.connect((conf['end_server'], conf['port']))
    data = self.irc.recv(4096).decode('utf-8', errors="replace")
    print(data)
    if data == 'CAPAB START 1202\r\n':
      print('Sending CAPs')
      self.send('{SID} CAPAB START 1202'.format(**conf))
      self.send('{SID} CAPAB CAPABILITIES :PROTOCOL=1202'.format(**conf))
      self.send('{SID} CAPAB END'.format(**conf))
      self.send('{SID} SERVER {server_name} {server_password} 0 {SID} :{server_desc}'.format(**conf))
      print('Sending Burst')
      t = int(time.time())
      self.send('{SID} BURST {t}'.format(t=t, **conf))
      self.send('{SID} VERSION {version}'.format(version=self.version, **conf))
      for line, reason in self.Qlines:
        self.send('{SID} ADDLINE Q {line} {server_name} {t} 172800000 :{reason}'.format(line=line, reason=reason, t=t, **conf))
      self.send('{SID} ADDLINE Q *Serv {server_name} {t} 172800000 :Reserved for Services'.format(t=t, **conf))
      for pseudoclient in self.pseudoclients.values():
        self.uid_pseudouser(pseudoclient, t=t)
      self.send('{SID} ENDBURST'.format(**conf))

  def handle_uid(self, sender, params):
    # A user connects or is otherwise defined by the network
    UID, conn_time, nick, host1, host2, name, ip, time_2, modes, *realname = params.split(' ')
    self.users[UID] = User(UID, nick, host1, modes)  # Probably change this later
    print('Added user {} as {}.'.format(UID, nick))

  def handle_nick(self, sender, params):
    # A user changes their nickname
    nick, cmd_time = params.split(' ')
    user = self.users[sender]
    oldnick = user.nick
    self.users[sender] = User(*((sender, nick)+user[2:]))
    print('User {} changed nick from {} to {}.'.format(sender, oldnick, nick))
    self.call_plugin_handlers('handle_nick', {'nick': nick, 'oldnick': oldnick})

  def handle_quit(self, user, params):
    _, reason = params.split(' ', 1)  # Starts with ':Quit:', not wrapped in quotes
    user = self.users[user]
    self.call_plugin_handlers('handle_quit', {'nick': user.nick, 'reason': reason})
    for chan in self.channels:
      try:
        self.channels[chan].remove(user)
      except KeyError:
        pass
    try:
      self.users.pop(user.UID)
    except KeyError:
      traceback.print_exc()

  def handle_join(self, sender, params):
    print('Handling FJOIN - {} {}'.format(sender, params))
    if self.burst or params[-1] == '\r':  # yay syntax change
      params = params.rpartition(':')
      chan, timestamp, *modes = params[0].split(' ')
      users = [user.partition(',') for user in params[2].rstrip('\r').split(' ')]
    else:
      chan, timestamp, *modes, user = params.split(' ')
      users = [user.partition(',')]
    if chan in self.channels:
      for modes, _, uid in users:
        user = self.users[uid]
        self.channels[chan].add(user)
        print('\t{} joined channel {}'.format(user, chan))
        self.call_plugin_handlers('handle_join', {'nick': user.nick, 'channel': chan})

  def handle_part(self, user, params):
    print('Parting', user, params)
    chan, reason = params.split(' ', 1)
    user = self.users[user]
    reason = reason[2:-1]  # Starts with :, wrapped in double quotes.
    if chan in self.channels:
      try:
        self.channels[chan].remove(user)
        self.call_plugin_handlers('handle_part', {'nick': user.nick, 'channel': chan, 'reason': reason})
      except KeyError:
        pass

  def handle_ping(self, sender, params):
    try:
        self.send('{SID} PONG {SID} {sender}'.format(sender=sender, **self.config['connection']))
    except:
        self.irc.close()
        logging.warning("Error with sockets: ", sys.exc_info()[0])
        logging.info('Trying to reconnect')
        self.connect()

  def handle_privmsg(self, sender, params):
    '''
    In server-server comms, users are referred to by their ID, which we will need to (de)reference.
    '''
    # Get the nick, channel (doesn't have to be channel) and message.
    conf = self.config['connection']
    nick = self.users.get(sender, (None, 'Not found'))[1]
    #t = int(time.time())
    target, _, msg = params.partition(' ')
    msg = msg[1:]  # remove leading :
    msg_data = {'message': msg, 'nick': nick, 'channel': target}
    ## Don't do anything if nick is on ignore list
    #if nick in self.config['connection']['ignore_list']:
      #return
    ## Call all the modules
    if target in self.channels:
      self.call_plugin_handlers('handle_message', msg_data)
    else:  # Only PRIVMSGs we get that aren't directed to channels are to our pseudoclients
      self.call_plugin_handlers('handle_pm', msg_data)

  def nick_in_channel(self, nick, channel):
    if channel in self.channels:
      if nick in [user.nick for user in self.channels[channel]]:
        return True
    return False

  def get_userlist(self, channel):
    if channel in self.channels:
      return [user.nick for user in self.channels[channel]]

  def send_msg(self, recipient, msg, sender=None):  # Need to be U-lined anyway, so don't bother with flood control
    if sender is None:
      sender = self.config['connection']['SID']
    command = '{} PRIVMSG {} :{}'.format(sender, recipient, msg)
    try:
      self.send(command)
    except BaseException as e:
      self.irc.close()
      logging.warning('Error with sockets: {}'.format(e))
      logging.info('Trying to reconnect')
      self.connect()

  def uid_pseudouser(self, pseudoclient, t=None):
    if not t:
      t = time.time()
    self.send('{SID} UID {UID} {t} {nick} {server_name} {hostmask} {usermask} 0.0.0.0 {t} +I :{desc}'.format(t=t, **pseudoclient._asdict(), **self.config['connection']))
    for chan in pseudoclient.channels:
      self.send('{SID} FJOIN {chan} {t} + ,{UID}'.format(chan=chan, t=t, UID=pseudoclient.UID, **self.config['connection']))

  def add_pseudouser(self, nick, channels=[], hostmask=None, usermask=None, desc='MASTERlinker plugin'):
    if nick in self.pseudoclient_nicks:
      return self.pseudoclient_nicks[nick]
    else:
      UID = self.generate_uid.__next__()
      if not usermask:
        usermask = nick
      if not hostmask:
        hostmask = self.config['connection']['server_name']
      pseudoclient = Pseudoclient(UID, nick, usermask, hostmask, desc, channels)
      self.pseudoclients[UID] = pseudoclient
      self.pseudoclient_nicks[nick] = UID
      if self.connected:
        print('Sending: Adding pseudouser {} as {}'.format(nick, UID))
        self.uid_pseudouser(pseudoclient)
      else:
        print('Not sending: Adding pseudouser {} as {}'.format(nick, UID))
      return UID

  def rename_pseudouser(self, oldnick, newnick):
    if oldnick in self.pseudoclient_nicks:
      UID = self.pseudoclient_nicks.pop(oldnick)
      self.pseudoclient_nicks[newnick] = UID
      user = self.pseudoclients[UID]
      self.pseudoclients[UID] = Pseudoclient(*((UID, newnick)+user[2:]))
      self.send('{} NICK {} {}'.format(UID, newnick, time.time()))

  def remove_pseudouser(self, nick, quit_reason='Quitting'):
    if nick in self.pseudoclient_nicks:
      UID = self.pseudoclient_nicks.pop(nick)
      self.send('{} QUIT :{}'.format(UID, quit_reason))
      self.pseudoclients.pop(UID)
      self.recycle_UID(UID)


default_config = {
  'connection': {
    'server': '127.0.0.1',  # Takes on a different connotation, but this is still the server to connect to
    'port': 7000,
    'timeout': 200,
    'ssl': False,  # SSL - False = off, True = on
    'server_name': 'bridge.ufeff.net',
    'server_password': 'penguins',
    'server_desc': 'Bridging Services',
    'SID': '00C',
    'max_pseudoclients': 1000000000,  # We start from AAAAAA which gives us somewhat less than 36^6 UIDs, but that's still an absurd address space
    #'identifymsg_enabled': True,  # Prefixes messages with + if the user is identified, - if not. Does not work outside Freenode.
    'channel_list': ['#ufeff'],
    #'ignore_list': ['VidyaLink', 'Moebot', 'pikatwo'],
    #'admin_list': ['Birdulon'],
  },
  'logging_level': 'DEBUG',  # DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL

  # Plugins to load on startup
  'plugins': ['url_info_finder', 'about', 'seen', 'stats', 'BTC'],
  'plugin_configs': {'bridge': 'settings_bridge.json'},
}


if __name__ == '__main__':
  config_file = 'server_settings.json'
  log_file = 'ircserver.log'
  '''
  TODO: Add per-plugin config selection.
  Maybe by taking the root name of the passed config file, or having keys for their names in the config file.
  '''
  try:
    opts, args = getopt.getopt(sys.argv[1:],"hc:l:",["config=","log="])
    for opt, arg in opts:
      if opt == '-h':
        print('ircbot.py -c <configfile> -l <logfile>')
        sys.exit()
      elif opt in ('-c', '--config'):
        config_file = arg
      elif opt in ('-l', '--log'):
        log_file = arg
  except getopt.GetoptError:
    print('ircbot.py -c <configfile> -l <logfile>')

  config = helpers.parse_config(config_file, default_config)
  logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S', filename=log_file,
                      level=getattr(logging, config['logging_level']))
  ircserver = ircserver(config)
  ircserver.main()
