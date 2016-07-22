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
from queue import Queue

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
                if event_type == 1: #ordinary user message
                    content = html.unescape(event["content"])
                    print(abbreviate("{}: {}".format(event["user_name"], content), 119))
                    if event["user_name"] == "Kevin": #possible administrator command
                        if content == "!shutdown":
                            postquery.post_message_test(1, "bye")
                            import sys; sys.exit(0)
                        if content == "!ping":
                            print("Detected a command. Replying...")
                            postquery.post_message_test(1, "pong")
                elif event_type in (3,4): #user entered/left
                    action = {3:"entered", 4:"left"}[event_type]
                    print("user {} {} room {}".format(repr(event["user_name"]), action, repr(event["room_name"])))
                else:
                    print(event_type_names[event_type])

    def onClose(self, was_clean, code, reason):
          print('Closed:', reason)
          import sys; sys.exit(0)

def create_websocket(message_queue = None):
    def onIdle(x=[]):
        while not message_queue.empty():
            onAdminMessage(message_queue.get())
        loop.call_later(1, onIdle)

    def onAdminMessage(msg):
        print("Got admin message: {}".format(msg))
        if msg == "shutdown":
            print("Shutting down...")
            import sys; sys.exit(0)
        elif msg == "join":
            postquery.post_join_test(118024)
        elif msg.startswith("say"):
            postquery.post_message_test(118024, msg.partition(" ")[2])
        elif msg.startswith("leave"):
            roomid = msg.partition(" ")[2]
            postquery.post_leave_test(roomid)
        elif msg.startswith("cancel"):
            messageId = msg.partition(" ")[2]
            postquery.post_cancel_stars(messageId)
        else:
            print("Sorry, didn't understand that command.")

    if message_queue is None:
        message_queue = Queue()

    url = postquery.get_ws_url(roomid=118024)
    host = "chat.sockets.stackexchange.com"

    print("Establishing web socket...")

    factory = WebSocketClientFactory(url, headers={"Origin":"http://chat.stackoverflow.com"})
    factory.protocol = StackActivity

    loop = asyncio.get_event_loop()

    loop.call_later(1, onIdle)

    coro = loop.create_connection(factory, host, 80)
    loop.run_until_complete(coro)
    loop.run_forever()
    loop.close()

import threading

def create_admin_window(message_queue):
    from tkinter import Tk, Entry, Button

    def clicked():
        message_queue.put(box.get())

    def on_closing():
        message_queue.put("shutdown")
        root.destroy()

    root = Tk()
    box = Entry(root, width=100)
    box.pack()
    button = Button(root, text="submit", command=clicked)
    button.pack()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()

message_queue = Queue()
t = threading.Thread(target=create_admin_window, args=(message_queue,))
t.start()

create_websocket(message_queue)