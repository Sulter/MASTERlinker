#!/usr/bin/env python

import socket
import re
import time
import collections
import logging
import settings
    
class botframe():

    def __init__(self):
        self.commands = collections.deque(".")
        self.data_buffer = ''
        self.rexp_general = re.compile(r'^(:[^ ]+)?[ ]*([^ ]+)[ ]+([^ ].*)?$')
        self.loaded_plugins = []
        self.load_plugins()

    def load_plugins(self):
        for plugin in settings.plugins:
            self.import_plugin(plugin)

    def import_plugin(self, plugin):
        name = "plugins." + plugin
        ref = __import__(name)
        module_ref = getattr(ref, plugin)
        clsobj_ref = getattr(module_ref, plugin)
        inst_ref = clsobj_ref()
        self.loaded_plugins.append(inst_ref)
            
    def connect(self):
        self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc.connect((settings.SERVER, settings.PORT))
        self.irc.send('NICK ' + settings.NICK + '\r\n')
        self.irc.send('USER ' + settings.NICK + ' muh python bot\r\n')
        if settings.nick_serv_on is True:
            self.irc.send('PRIVMSG ' + "NickServ" + ' :IDENTIFY %s %s\r\n' % (settings.nick_serv_nick, settings.nick_serv_pass))
            logging.info('Waiting for login...')
            time.sleep(15) #this should be replaced by waiting for " 396 YourNick unaffiliated/youraccount :is now your hidden host (set by services.)", but that is not standard, so I'm not sure.
        #join all channels
        logging.info('Joining channels')
        for channel in settings.channel_list:
            self.irc.send('JOIN ' + channel + '\r\n')

    def parse_command(self, data):

        rex = re.search(self.rexp_general, data)
        if rex is None:
            return

        command = rex.groups()
        sender = command[0]
        cmd = command[1]
        params = command[2]
        logging.debug(command)
        
        if cmd == 'PING':
            self.irc.send('PONG ' + params + '\r\n')
            return
        elif cmd == 'PRIVMSG':
            #get the nick, channel (doesn't have to be channel) and message.
            nick = self.get_nick(sender)
            channel = self.get_channel(params, nick)
            msg = self.get_msg(params, channel)
            msg_info = {"message": msg, "nick": nick, "channel": channel}
            
            #don't do anything if nick is on ignore list
            if nick in settings.ignore_list:
                return
            
            #call all the modules
            for plugin in self.loaded_plugins:
                plugin_name = plugin.__class__.__name__
                getattr(plugin, plugin_name)(self, msg_info)
            return

    def send_msg(self, recipient, msg):
        command = 'PRIVMSG %s :%s\r\n' % (recipient, msg)
        self.irc.send(command)
        
    def get_channel(self, string, nick):
        channel = re.search(r"^[\S]+", string).group()
        return channel

    def get_msg(self, string, current_channel):
        #remove channel name, and the : that is the prefix of the message
        parsed_msg = string.lstrip(current_channel)
        parsed_msg = parsed_msg.lstrip()
        parsed_msg = parsed_msg.lstrip(":")
        #sanitize from formatting (color codes etc.) - thank you Kuraitou
        parsed_msg = re.sub('(\x02)|(\x07)|(\x0F)|(\x16)|(\x1F)|(\x03(\d{1,2}(,\d{1,2})?)?)', '', parsed_msg)
        return parsed_msg

    def get_nick(self, string):
        nick = string.lstrip(":")
        nick = nick.partition("!")
        return nick[0]

    def receive_com(self):
        
        #parse commands from our command-buffer if empty
        if self.commands:
            return self.commands.popleft()
        
        #read data from the socket
        data = self.irc.recv(4096)
        self.data_buffer = ''.join([self.data_buffer, data])
        #each IRC command ends with "\r\n", so we split the whole string at those points
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

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='ircbot.log',level=getattr(logging, settings.logging_level))
    ircbot = botframe()
    ircbot.main()

