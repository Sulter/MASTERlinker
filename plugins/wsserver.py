#plugin that creates a websocket server, and feeds all the messages written to the connected clients

import socket
import re
import base64
import hashlib
import struct
import threading
import select
import settings

class wsserver():
   def __init__(self):
      self.server = WsServerThread(4446)
      self.server.start()

   def wsserver(self, main_ref, msg_info): #main function ran by the bot after receiving each message
      if msg_info["channel"] == settings.NICK: #ignore private msg
            return None

      self.server.send_msg_all(msg_info["nick"] + ":" + msg_info["message"]) #send msg and nick to listening sockets

class WsServerThread(threading.Thread):

   def __init__ (self, port):
      #make server (non-blocking socket)
      self.sserver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.sserver.setblocking(0)
      self.sserver.bind(("", port))
      self.sserver.listen(5)
      self.client_list = []
      threading.Thread.__init__ (self)

   def send_msg_all(self, msg):
      for sock in self.client_list:
         self.send_msg(sock, msg)         
         
   def run (self):
      while 1:
         #we wait until we got something that is ready to read
         ready_to_read, ready_to_write, in_error =  select.select([self.sserver]+self.client_list, [],[self.sserver]+self.client_list,60)
         if in_error:
            print "ERROR! in sockets"
            print in_error
         for reader in ready_to_read:
            if reader == self.sserver: #this will be true if there are sockets that can be accepted
               clientsocket, address = self.sserver.accept()
               if self.handshake(clientsocket) is True: #only add socket to the list if the handshake succeeded
                  self.client_list.append(clientsocket)
            else: #one of the other sockets has a message for us, but we only check if it's empty, because that means the socket closed
               m = ""
               try:
                  m =  reader.recv(4096)
               except:
                  do_noting=0
               if len(m) < 1:
                  self.client_list.remove(reader)
                  reader.close()

   def send_msg(self, sock, message):
      #https://tools.ietf.org/html/rfc6455#page-28
      length = len(message)
      frame = "\x81" #the first byte setting the FIN bit to 1 and sending the opcode 0x1 that tells the clients the payload data is text
      if length > 65025:
         raise Exception("Error - payload to large")
      elif length > 125 :
         frame = frame + chr(126) 
         frame = frame + struct.pack(">H", length) #here we add the hex representation of the length
         frame = frame + message
      else:
         frame = frame + chr(length) + message
      ready_to_read, ready_to_write, in_error =  select.select([], [sock],[],1)
      if sock in ready_to_write:
         try:
            sock.sendall(frame)
         except:
            self.client_list.remove(sock)
            sock.close()
            
   def handshake(self, sock):
      magic_string = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
      #get the header, but only if the socket has anything to say (otherwise just disgard it)
      ready_to_read, ready_to_write, in_error =  select.select([sock],[],[],1)
      if sock in ready_to_read:
         header =  sock.recv(4096)
      else:
         return False
    
      #here we should probably add some more protocol checking stuff. But this should work with any real browsers (chromium/firefox, at least for now)

      #make the key, using the key from the header and the magic string
      key = re.search("(Sec-WebSocket-Key: )(\S+)", header)
      if not key:
         return False #return false if the client didn't provide a key
      key = key.group(2)
      key = key + magic_string
      respond_key = base64.b64encode(hashlib.sha1(key).digest())

      #handshake
      respond_message ="HTTP/1.1 101 Switching Protocols\r\n"
      respond_message = respond_message + "Upgrade: websocket\r\n"
      respond_message = respond_message + "Connection: Upgrade\r\n"
      respond_message = respond_message + "Sec-WebSocket-Accept: %s\r\n\r\n" % respond_key

      ready_to_read, ready_to_write, in_error =  select.select([],[sock],[],1) #make sure it's ready to write
      if sock in ready_to_write:
         sock.sendall(respond_message)
         return True
      else:
         return False
