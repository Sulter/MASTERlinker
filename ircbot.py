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
import includes.helpers as helpers
from botframe import botframe


class ircbot(botframe):
  pass
  #def connect(self):
    #conf = self.config['connection']
    #self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #if conf['ssl']:
      #self.irc = ssl.wrap_socket(self.irc)
    #try:
      #self.irc.connect((conf['server'], conf['port']))
      #self.send('NICK {nick}'.format(**conf))
      #self.send('USER {nick} muh python bot'.format(**conf))
      #if conf['identifymsg_enabled']:
        #self.send('CAP REQ identify-msg')
        #self.send('CAP END')
      #if conf['nickserv_enabled']:
        #self.send('PRIVMSG NickServ :IDENTIFY {nickserv_nick} {nickserv_pass}'.format(**conf))
        #logging.info('Waiting for login...')
        #time.sleep(15)  # this should be replaced by waiting for " 396 YourNick unaffiliated/youraccount :is now your hidden host (set by services.)", but that is not standard, so I'm not sure.
      ## Join all channels
      #logging.info('Joining channels')
      #for channel in conf['channel_list']:
        #self.send('JOIN ' + channel)
    #except socket.timeout as e:
      #logging.warning(e)
      #logging.info('Trying to reconnect')
      #self.connect()


default_config = {
  'connection': {
    'server': 'irc.freenode.org',
    'port': 6667,  # SSL freenode: 6697 , default: (6667)
    'timeout': 200,
    'ssl': False,  # SSL - False = off, True = on
    'nick': 'MASTERlinker',
    'nickserv_enabled': False,  # Nickserv authentification - False = off, True = on
    'nickserv_nick': 'MASTERlinker',
    'nickserv_pass': 'password',
    'identifymsg_enabled': True,  # Prefixes messages with + if the user is identified, - if not. Does not work outside Freenode.
    'channel_list': ['#ufeff'],
    'ignore_list': ['VidyaLink', 'Moebot', 'pikatwo'],
    'admin_list': ['Birdulon'],
  },
  'logging_level': 'DEBUG',  # DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL

  # Plugins to load on startup
  'plugins': ['url_info_finder', 'about', 'seen', 'stats', 'BTC'],
  'plugin_configs': {'bridge': 'settings_bridge.json'},
}


if __name__ == '__main__':
  config_file = 'settings.json'
  log_file = 'ircbot.log'
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
  ircbot = ircbot(config)
  ircbot.main()
