#!/usr/bin/env python

import socket
import re
import collections
import logging
import settings
import threading
import time
import ssl
import sys


class botframe():
    def __init__(self):
        self.commands = collections.deque()
        self.data_buffer = ""
        self.rexp_general = re.compile(r'^(:[^ ]+)?[ ]*([^ ]+)[ ]+([^ ].*)?$')

        self.msg_buffer = collections.deque()
        self.msg_send_time = 0

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

    def send(self, string):
        try:
            self.irc.send(bytes(string, 'utf-8'))
        except:
            logging.error('Send error')

    def connect(self):
        self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if settings.SSL:
            self.irc = ssl.wrap_socket(self.irc)
        try:
            self.irc.connect((settings.SERVER, settings.PORT))
        except socket.error as err:
            if err.errno != 110:  # 110 is time-out errno
                raise err
            else:
                logging.warning(format(err.errno, err.strerror))
                logging.info('Trying to reconnect')
                self.connect()

        self.send('NICK ' + settings.NICK + '\r\n')
        self.send('USER ' + settings.NICK + ' muh python bot\r\n')
        if settings.nick_serv_on:
            self.send(
                'PRIVMSG ' + "NickServ" + ' :IDENTIFY %s %s\r\n' % (settings.nick_serv_nick, settings.nick_serv_pass))
            logging.info('Waiting for login...')
            time.sleep(
                15)  # this should be replaced by waiting for " 396 YourNick unaffiliated/youraccount :is now your hidden host (set by services.)", but that is not standard, so I'm not sure.
        # Join all channels
        logging.info('Joining channels')
        for channel in settings.channel_list:
            self.send('JOIN ' + channel + '\r\n')

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
            try:
                self.send('PONG ' + params + '\r\n')
            except:
                self.irc.close()
                logging.warning("Error with sockets: ", sys.exc_info()[0])
                logging.info('Trying to reconnect')
                self.connect()

            return
        elif cmd == 'PRIVMSG':
            # Get the nick, channel (doesn't have to be channel) and message.
            nick = self.get_nick(sender)
            channel = self.get_channel(params, nick)
            msg = self.get_msg(params, channel)
            msg_info = {"message": msg, "nick": nick, "channel": channel}

            # Don't do anything if nick is on ignore list
            if nick in settings.ignore_list:
                return

            # Call all the modules
            for plugin in self.loaded_plugins:
                plugin_name = plugin.__class__.__name__
                getattr(plugin, plugin_name)(self, msg_info)
            return

    def send_msg(self, recipient, msg):  # method for sending privmsg, takes care of timing etc. to prevent flooding
        command = 'PRIVMSG %s :%s\r\n' % (recipient, msg)
        self.msg_buffer.append(command)

        # Schedule the message to be send, depending on the buffer size, 1message each 2 seconds.
        buffer_size = len(self.msg_buffer)
        if buffer_size < 2:
            self.msg_time_diff = 2 - (time.time() - self.msg_send_time)
            if self.msg_time_diff > 0:
                self.send_from_buffer()  # send the message momentary
            else:
                t = threading.Timer(self.msg_time_diff,
                                    self.send_from_buffer)  # schedule for sending later (at least 2 seconds since last message)
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

    def get_channel(self, string, nick):
        channel = re.search(r"^[\S]+", string).group()
        return channel

    def get_msg(self, string, current_channel):
        # Remove channel name, and the : that is the prefix of the message
        parsed_msg = string.lstrip(current_channel)
        parsed_msg = parsed_msg.lstrip()
        parsed_msg = parsed_msg.lstrip(":")
        # Sanitize from formatting (color codes etc.) - thank you Kuraitou
        parsed_msg = re.sub('(\x02)|(\x07)|(\x0F)|(\x16)|(\x1F)|(\x03(\d{1,2}(,\d{1,2})?)?)', '', parsed_msg)
        return parsed_msg

    def get_nick(self, string):
        nick = string.lstrip(":")
        nick = nick.partition("!")
        return nick[0]

    def receive_com(self):
        # Parse commands from our command-buffer if *not* empty
        if self.commands:
            return self.commands.popleft()

        # Read data from the socket
        data = self.irc.recv(4096).decode('utf-8')

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


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='ircbot.log',
                        level=getattr(logging, settings.logging_level))
    ircbot = botframe()
    ircbot.main()
