# Requires Python 3.4 and a `pip install autobahn`

import sys
if sys.version_info < (3,0,0):
    print("Please run me in Python 3.")
    sys.exit(0)

import postquery

import asyncio
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory
import json
from pprint import pprint

class StackActivity(WebSocketClientProtocol):

    def onConnect(self, response):
        print('Connected:', response.peer)

    def onOpen(self):
        print("Opened.")

    def onMessage(self, payload, is_binary):
          print("Got message.")
          print(payload)
          #loop.stop()

    def onClose(self, was_clean, code, reason):
          print('Closed:', reason)
          import sys; sys.exit(0)

url = postquery.get_ws_url(roomid=1)
host = "chat.sockets.stackexchange.com"

print("Establishing web socket...")

factory = WebSocketClientFactory(url, headers={"Origin":"http://chat.stackoverflow.com"})
factory.protocol = StackActivity

loop = asyncio.get_event_loop()

coro = loop.create_connection(factory, host, 80)
loop.run_until_complete(coro)
loop.run_forever()
loop.close()
print("Bye.")