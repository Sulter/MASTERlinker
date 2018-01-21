# A plugin that sends and receives messages over a unix socket. Nominally used for bridging chat channels.
import includes.helpers as helpers
import logging
import os
import socket
import threading


class bridge(helpers.Plugin):
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
      'in_prefix': '',
      'server': True,
      'socket': 'bridge_socket',
    }
    self.config = helpers.parse_config(config_file, default_config)
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

  def handle_pm(self, msg_data):
    # Ignore private messages for now
    pass

  def handle_message(self, msg_data):
    # Ignore if message does not start with delimiter
    if self.config['delimiter']:
      if not msg_data['message'].startswith(self.config['delimiter']):
        return None
      else:
        msg_data['message'] = msg_data['message'][len(self.config['delimiter']):]
    message = '{nick}:{message}\n'.format(**msg_data)
    if self.config['server']:
      for c in self.connections:
        self.send_message(c, message)
    else:
      self.send_message(self.socket, message)

  def send_message(self, sock, message):
    try:
      sock.send(message.encode('utf-8'))
    except BaseException as e:
      logging.debug('bridge: handle_message exception {}'.format(e))

  def parse_message(self, m):
    try:
      nick, msg = m.split(':', 1)
      message = '{}<{}> {}'.format(self.config['in_prefix'], nick, msg)
      self.parent.send_msg(self.config['channel'], message)
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
          messages = data.decode('utf-8').split('\n')
          for m in messages:
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
        data = sock.recv(4096)
        messages = data.decode('utf-8').split('\n')
        for m in messages:
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
