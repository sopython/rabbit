import sys
if sys.version_info < (3,0,0):
    print("Please run me in Python 3.")
    sys.exit(0)

from stackoverflowchatsession import StackOverflowChatSession
import config

import asyncio
import json
import html
from queue import Queue

PERSONAL_SANDBOX_ROOMID = 118024
ROTATING_KNIVES_ROOMID = 71097

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

class Rabbit(StackOverflowChatSession):
    """
        Simple example implementation of a StackOverflowChatSession.
        Features:
        - Prints information about each chat event that occurs
        - Responds to commands sent in chat:
            - "!ping" - replies with "pong"
        - Responds to administrator commands sent to its message queue (i.e. typed into the Tkinter window on its local machine):
            - "say [text]" - sends text to the room
            - "shutdown" - terminates this process
            - "cancel [message id]" - cancels the stars of a message, if bot has RO rights
            - "kick [user id]" - kicks the user, if bot has RO rights
            - "move [message id,message id,message id]" - moves one or more messages to the Rotating Knives room, if bot has RO rights
    """
    def __init__(self, email, password, admin_message_queue): 
        StackOverflowChatSession.__init__(self, email, password)
        self.admin_message_queue = admin_message_queue
        self.authorized_users = {"Kevin"}

    def onConnect(self, response):
        print('Connected:', response.peer)

    def onOpen(self):
        print("Opened.")

    def onMessage(self, payload):
        d = json.loads(payload.decode("utf-8"))
        for roomid, data in d.items():
            if "e" not in data: #some kind of keepalive message that we don't care about
                continue
            for event in data["e"]:
                event_type = event["event_type"]
                if event_type == 1: #ordinary user message
                    content = html.unescape(event["content"])
                    print(abbreviate("{}: {}".format(event["user_name"], content), 119))
                    if event["user_name"] in self.authorized_users: #possible administrator command
                        if content == "!ping":
                            print("Detected a command. Replying...")
                            self.send_message(PERSONAL_SANDBOX_ROOMID, "pong")
                elif event_type in (3,4): #user entered/left
                    action = {3:"entered", 4:"left"}[event_type]
                    print("user {} {} room {}".format(repr(event["user_name"]), action, repr(event["room_name"])))
                else:
                    print(event_type_names[event_type])

    def onClose(self, was_clean, code, reason):
          print('Closed:', reason)
          import sys; sys.exit(0)

    def onIdle(self):
        while not self.admin_message_queue.empty():
            msg = self.admin_message_queue.get()
            self.onAdminMessage(msg)

    def onAdminMessage(self, msg):
        print("Got admin message: {}".format(msg))
        if msg == "shutdown":
            print("Shutting down...")
            import sys; sys.exit(0)
        elif msg.startswith("say"):
            self.send_message(PERSONAL_SANDBOX_ROOMID, msg.partition(" ")[2])
        elif msg.startswith("cancel"):
            messageId = msg.partition(" ")[2]
            self.cancel_stars(messageId)
        elif msg.startswith("kick"):
            userId = msg.partition(" ")[2]
            self.kick(PERSONAL_SANDBOX_ROOMID, userId)
        elif msg.startswith("move"):
            messageIds = msg.partition(" ")[2].split()
            self.move_messages(PERSONAL_SANDBOX_ROOMID, messageIds, ROTATING_KNIVES_ROOMID)
        else:
            print("Sorry, didn't understand that command.")


#connect to the SO chat server. This function never returns.
def create_and_run_chat_session(admin_message_queue = None):
    if admin_message_queue is None:
        admin_message_queue = Queue()

    session = Rabbit(config.email, config.password, admin_message_queue)
    session.join_and_run_forever(PERSONAL_SANDBOX_ROOMID)

import threading

#create a GUI the user can use to send admin commands. This function never returns.
#(hint: use threads if you want to run both this and `create_and_run_chat_session`)
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

create_and_run_chat_session(message_queue)