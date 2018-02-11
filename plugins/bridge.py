# A plugin that sends and receives messages over a unix socket. Nominally used for bridging chat channels.
import includes.helpers as helpers
import logging
import os
import socket
import threading
import re


class bridge(helpers.Plugin):
  delimiter = '\n'
  def __init__(self, parent):
    super().__init__(parent)
    config_file = 'settings_bridge.json'
    try:
      config_file = parent.config['plugin_configs']['bridge']
    except:
      pass
    default_config = {
      'blacklist': [],
      'delimiter': None,
      'channel': '#ufeff',
      'hostmask': None,
      'in_prefix': '[R]',
      'remote_name': 'Remote',
      'server': True,
      'socket': 'bridge_socket',
    }
    self.config = helpers.parse_config(config_file, default_config)

    self.suffix_regex = re.compile('(\S){}'.format(re.escape(self.config['in_prefix'])))

    self.remote_channel = set()  # For now only consider one userlist
    self.pseudousers = {}

    if not self.parent.single_user:
      self.parent.Qlines.append(('*{}'.format(self.config['in_prefix']), 'Reserved for {} users'.format(self.config['remote_name'])))

    self.bridge_handlers = {
      #'PING': self.handle_ping,
      'MSG': self.b_handle_msg,
      '353': self.b_handle_userlist,
      'JOIN': self.b_handle_join,
      'NICK': self.b_handle_nick,
      'PART': self.b_handle_part,
      'QUIT': self.b_handle_quit,
    }

    self.connections = []
    if self.config['server']:
      self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      if os.path.exists(self.config['socket']):
        os.unlink(self.config['socket'])
      self.socket.bind(self.config['socket'])
      logging.debug('bridge: server started at {}'.format(self.config['socket']))
      threading.Thread(target=self.server_loop).start()
    else:
      threading.Thread(target=self.client_loop).start()

  def __del__(self):
    # Clean up socket
    del self.socket
    if self.config['server']:
      del self.connections
      os.unlink(self.config['socket'])

  def handle_userlist(self, params):
    if params['channel'] == self.config['channel']:
      self.send_b_message_all('353 {}'.format(' '.join(params['userlist'])))

  def handle_join(self, params):
    if params['channel'] == self.config['channel']:
      self.send_b_message_all('JOIN {nick}'.format(**params))

  def handle_part(self, params):
    if params['channel'] == self.config['channel']:
      self.send_b_message_all('PART {nick} {reason}'.format(**params))

  def handle_nick(self, params):
    if self.parent.nick_in_channel(params['nick'], self.config['channel']):
      self.send_b_message_all('NICK {oldnick} {nick}'.format(**params))

  def handle_quit(self, params):
    if self.parent.nick_in_channel(params['nick'], self.config['channel']):
      self.send_b_message_all('QUIT {nick} {reason}'.format(**params))

  def handle_pm(self, msg_data):
    if msg_data['message'] == '!userlist':
      userlist = ' '.join(sorted(self.remote_channel))
      self.send_msg(msg_data['nick'], '{} users: {}'.format(self.config['remote_name'], userlist))

  def handle_message(self, msg_data):
    if msg_data['channel'] == self.config['channel']:
      if msg_data['message'] == '!userlist':
        userlist = ' '.join(sorted(self.remote_channel))
        self.send_msg(msg_data['channel'], '{} users: {}'.format(self.config['remote_name'], userlist))
        return
      if self.config['delimiter']:
        # Ignore if message does not start with delimiter
        if not msg_data['message'].startswith(self.config['delimiter']):
          return None
        else:
          msg_data['message'] = msg_data['message'][len(self.config['delimiter']):]
      msg_data['message'] = self.sanitise_message(msg_data['message'])
      message = 'MSG {nick}:{message}'.format(**msg_data)
      self.send_b_message_all(message)

  def sanitise_message(self, msg):
    return re.sub(self.suffix_regex, r'\1', msg)

  def b_handle_userlist(self, params):
    old_list = self.remote_channel
    self.remote_channel = set(params.split(' '))
    joined = self.remote_channel - old_list
    left = old_list - self.remote_channel
    for nick in joined:
      self.add_pseudouser(nick)
    for nick in left:
      self.remove_pseudouser(nick)

  def b_handle_join(self, params):
    self.remote_channel.add(params)
    self.add_pseudouser(params)

  def b_handle_part(self, params):
    nick, _, reason = params.partition(' ')
    try:
      self.remote_channel.remove(nick)
      self.remove_pseudouser(nick, reason)
    except KeyError:
      pass

  def b_handle_nick(self, params):
    oldnick, _, nick = params.partition(' ')
    try:
      self.remote_channel.remove(oldnick)
      self.remote_channel.add(nick)
      self.rename_pseudouser(oldnick, nick)
    except KeyError:
      pass

  def b_handle_quit(self, params):
    nick, _, reason = params.partition(' ')
    try:
      self.remote_channel.remove(nick)
      self.remove_pseudouser(nick, reason)
    except KeyError:
      pass

  def b_handle_msg(self, params):
    nick, _, msg = params.partition(':')
    self.send_message(msg, nick)

  def add_pseudouser(self, nick):
    if not self.parent.single_user:
      p_nick = '{}{}'.format(nick, self.config['in_prefix'])
      uid = self.parent.add_pseudouser(p_nick, [self.config['channel']], self.config['hostmask'], nick, '{} user'.format(self.config['remote_name']))
      self.pseudousers[nick] = uid

  def rename_pseudouser(self, oldnick, newnick):
    if not self.parent.single_user:
      p_oldnick = '{}{}'.format(oldnick, self.config['in_prefix'])
      p_newnick = '{}{}'.format(newnick, self.config['in_prefix'])
      uid = self.pseudousers.pop(oldnick)
      self.pseudousers[newnick] = uid
      self.parent.rename_pseudouser(p_oldnick, p_newnick)

  def remove_pseudouser(self, nick, quit_reason='Quitting'):
    if not self.parent.single_user:
      p_nick = '{}{}'.format(nick, self.config['in_prefix'])
      self.parent.remove_pseudouser(p_nick, quit_reason)
      self.pseudousers.pop(nick)

  def send_message(self, msg, nick):
    if self.parent.single_user:
      nick = helpers.colorize_nick(helpers.dehighlight_nick(nick))
      message = '{}<{}> {}'.format(self.config['in_prefix'], nick, msg)
      self.send_msg(self.config['channel'], message)
    else:
      if nick in self.pseudousers:
        self.send_msg(self.config['channel'], msg, self.pseudousers[nick])

  def send_b_message_all(self, message):
    if self.config['server']:
      for c in self.connections:
        self.send_b_message(c, message)
    else:
      self.send_b_message(self.socket, message)

  def send_b_message(self, sock, message):
    message = '{}{}'.format(message, self.delimiter)
    try:
      sock.send(message.encode('utf-8'))
    except BaseException as e:
      logging.debug('bridge: handle_message exception {}'.format(e))

  def parse_message(self, m):
    try:
      cmd, _, params = m.partition(' ')
      if cmd in self.bridge_handlers:
        self.bridge_handlers[cmd](params)
    except ValueError:
      # Erroneous data on the socket
      pass

  def client_loop(self):
    while True:
      connected = False
      self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      self.socket.settimeout(5)
      try:
        self.socket.connect(self.config['socket'])
        logging.debug('bridge: client connected to {}'.format(self.config['socket']))
        self.socket.settimeout(None)
        connected = True
      except socket.timeout as e:
        logging.debug('bridge: failed to connect to server, retrying')

      while connected:
        try:
          data = self.socket.recv(4096)
          messages = data.decode('utf-8').split(self.delimiter)
          for m in messages:
            if m:
              self.parse_message(m)
        except socket.timeout:
          logging.debug('bridge: client_loop timed out')
          self.socket.close()
          connected = False
        except socket.error:
          pass

  def server_conn_loop(self, sock):
    while True:
      try:
        self.send_b_message(sock, '353 {}'.format(' '.join(self.parent.get_userlist(self.config['channel']))))
        data = sock.recv(4096)
        messages = data.decode('utf-8').split(self.delimiter)
        for m in messages:
          if m:
            self.parse_message(m)
      except socket.timeout:
        logging.debug('bridge: server_conn_loop timed out')
        sock.close()
        self.connections.remove(sock)
        return
      except socket.error:
        pass

  def server_loop(self):
    self.socket.listen()
    while True:
      conn = self.socket.accept()
      if conn[0]:
        logging.debug('bridge: server accepted connection from {}'.format(conn[1]))
        self.connections.append(conn[0])
        threading.Thread(target=self.server_conn_loop, args=(conn[0],)).start()
