# Requires Python 3.4 and a `pip install autobahn`

import sys
if sys.version_info < (3,0,0):
    print("Please run me in Python 3.")
    sys.exit(0)

import postquery

import asyncio
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory
import json
import html
import time
from pprint import pprint

event_type_names = [
    "placeholder because ids are 1-indexed",
    "message posted",
    "message edited",
    "user entered",
    "user left",
    "room name changed",
    "message starred",
    "UNKNOWN",
    "user mentioned",
    "message flagged",
    "message deleted",
    "file added",
    "moderator flag",
    "user settings chagned",
    "global notification",
    "account level changed",
    "user notification",
    "invitation",
    "message reply",
    "message moved out",
    "message moved in",
    "time break",
    "feed ticker",
    "user suspended",
    "user merged",
]

def abbreviate(msg, maxlen=25):
    if len(msg) < maxlen: return msg
    return msg[:maxlen-3] + "..."

class StackActivity(WebSocketClientProtocol):

    def onConnect(self, response):
        print('Connected:', response.peer)

    def onOpen(self):
        print("Opened.")

    def onMessage(self, payload, is_binary):
        d = json.loads(payload.decode("utf-8"))
        for roomid, data in d.items():
            if "e" not in data: #some kind of keepalive message that we don't care about
                continue
            for event in data["e"]:
                event_type = event["event_type"]
                print(event_type_names[event_type])
                if event_type == 1: #ordinary user message
                    content = html.unescape(event["content"])
                    print(abbreviate("{}: {}".format(event["user_name"], content), 119))
                    if event["user_name"] == "Kevin" and content == "!ping":
                        print("Detected a command. Replying...")
                        postquery.post_message_test("pong")

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