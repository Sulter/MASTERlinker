#plugin that supports DCC, still unsecure, and only works with clients using reverse DCC (mIRC, xchat, hexchat [...])

import settings
import re
import socket
import threading
import random
import time

bot_dec_IP = "XXXXX"

class DCC():

    def DCC(self, main_ref, msg_info):
        if msg_info["channel"] == settings.NICK:
            r = re.search("DCC SEND (\S+) (\d+) 0 (\d+) (\d+)", msg_info["message"])

            if r: #reverse DCC detected
                self.main_ref = main_ref
                self.msg_info = msg_info
                t = threading.Thread(target=self.r_dcc, args=(r,msg_info["nick"]))
                t.start()

    def r_dcc(self, r, nick):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while 1: #keep trying random ports until it finds a open one
            port = random.randint(10000, 25000) 
            try:
                s.bind(("", port))
                break
            except:
                print "port was occupied, we try again"

        s.listen(5)
        
        #send the accepting message back
        self.send_response(r, port, nick)
        (clientsocket, address) = s.accept()
    
        data = ""
        filesize = int(r.group(3), 10)

        f = open("download/" + r.group(1), 'wb')
        while 1:
            new_data = clientsocket.recv(4096)
            if not len(new_data):
                break
            
            f.write(new_data)
            filesize = filesize - len(new_data)
            if filesize <= 0:
                break

        clientsocket.close()
        f.close()
        
    def send_response(self, r, port, nick):
        
        filename = r.group(1)
        filesize = r.group(3)
        token = r.group(4)

        response = "\001DCC SEND " + filename + bot_dec_IP + str(port) + " " + filesize + " " + token + "\001"
        self.main_ref.send_msg(nick, response)
