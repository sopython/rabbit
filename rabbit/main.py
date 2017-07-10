import sys
import os
import json
import html
import logging
import random
import threading
import re
from .dbmodel import User, get_session
from .sochat import StackOverflowChatSession, EventType

import config

PYTHON_ROOM_ID = 6
PERSONAL_SANDBOX_ROOM_ID = 118024
ROTATING_KNIVES_ROOM_ID = 71097
AUTHORIZED_USERS = {
            953482, #Kevin
            6621329 #Terry
        }

PRIMARY_ROOM_ID = PYTHON_ROOM_ID

logger = logging.getLogger('rabbit')

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
    def __init__(self, email, password, room, trash_room, authorized_users):
        StackOverflowChatSession.__init__(self, email, password)
        self.room = room
        self.trash_room = trash_room
        self.authorized_users = authorized_users

    def onConnect(self, response):
        print('Connected:', response.peer)

    def onOpen(self):
        print("Opened.")

    def onMessage(self, payload):
        d = json.loads(payload.decode("utf-8"))
        logger.debug("Payload: {}".format(d))
        for room_id, data in d.items():
            if "e" not in data: #some kind of keepalive message that we don't care about
                continue
            for event in data["e"]:
                try:
                    event_type = event["event_type"]
                    event_type = EventType(event_type)
                except ValueError:
                    raise Exception("Unrecognized event type: {} \nWith event data: {}".format(event_type, event))
                if event_type == 1: #ordinary user message
                    self._on_regular_message(event)
                elif event_type in (3,4): #user entered/left
                    action = {3:"entered", 4:"left"}[event_type]
                    print("user {} {} room {}".format(repr(event["user_name"]), action, repr(event["room_name"])))
                elif event_type == 15: #account level changed
                    if "created" in event["content"]: #kicked. (this may also catch other kinds of account level changed events, but they seem rare enough, and the side effects are innocuous enough, that I can debug them as I encounter them.
                        #record event.
                        user = User.get_or_create(get_session(), event["user_id"])
                        user.kick_count += 1
                        get_session().commit()

                        #now post a picture of a bunny.
                        bunny_url = random.choice(config.kick_reply_images)
                        self.send_message(self.room, bunny_url)
                    else:
                        print("Info: Unknown event content {} in account level changed event.".format(repr(event["content"])))
                        print(event)
                else:
                    logger.info("Event: {}".format(event_type))

    def _on_regular_message(self, event):
        # TODO: never ever react to self messages
        content = html.unescape(event["content"])
        print(abbreviate("{}: {}".format(event["user_name"], content), 119))
        if event["user_id"] in self.authorized_users: #possible administrator command
            if content == "!ping":
                print("Detected a command. Replying...")
                self.send_message(self.room, "pong")
        if self._is_misformatted_code(content):
            # TODO: ping the user (but keep track of it so we only remind once. perhaps count anyway, but notify only once)
            msg = (
                "That looks like improperly formatted code. "
                "You should check the "
                "[Illustrated Guide To Formatting Code In Chat](https://sopython.com/wiki/An_Illustrated_Guide_To_Formatting_Code_In_Chat), "
                "and make sure you've read the [room rules](https://sopython.com/chatroom) since it's mentioned there."
            )
            self.send_message(self.room, msg)


    def _is_misformatted_code(self, content):
        """
        Determine if the given message content contains unformatted python code.
        Currently, only the triple-backtick multiline case is handled.
        """
        # in the future, perhaps some library that guesses langs could help
        # (similar to how pygments does it.)
        # Or we could just search for python keywords / popular module names
        match = re.match(
            r"<div class='full'>.*```.* <br>.*<br> ```.*</div>$",
            content)
        logger.debug("{} {} match the bad code regex".format(content, "did" if match is not None else "didn't"))
        return match is not None

    def onClose(self, was_clean, code, reason):
        print('Closed:', reason)
        sys.exit(0)

    def onAdminMessage(self, msg):
        print("Got admin message: {}".format(msg))
        if msg == "shutdown":
            print("Shutting down...")
            sys.exit(0)
        elif msg.startswith("say"):
            self.send_message(self.room, msg.partition(" ")[2])
        elif msg.startswith("cancel"):
            messageId = msg.partition(" ")[2]
            self.cancel_stars(messageId)
        elif msg.startswith("kick"):
            userId = msg.partition(" ")[2]
            self.kick(self.room, userId)
        elif msg.startswith("move"):
            messageIds = msg.partition(" ")[2].split()
            self.move_messages(self.room, messageIds, self.trash_room)
        else:
            print("Sorry, didn't understand that command.")



#create a GUI the user can use to send admin commands. This function never returns.
#(hint: use threads if you want to run both this and `create_and_run_chat_session`)
def create_admin_window(bot):
    from tkinter import Tk, Entry, Button

    def clicked():
        bot.loop.call_soon_threadsafe(bot.onAdminMessage, box.get())

    def on_closing():
        bot.loop.call_soon_threadsafe(bot.onAdminMessage, "shutdown")
        root.destroy()

    root = Tk()
    box = Entry(root, width=100)
    box.pack()
    button = Button(root, text="submit", command=clicked)
    button.pack()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()


def main():
    session = Rabbit(config.email, config.password, PRIMARY_ROOM_ID, ROTATING_KNIVES_ROOM_ID, AUTHORIZED_USERS)
    t = threading.Thread(target=create_admin_window, args=(session,))
    t.start()

    session.join_and_run_forever(PRIMARY_ROOM_ID)


def debug():
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    session = Rabbit(config.email, config.password,
        os.environ['room'], os.environ['trash'], set(int(x) for x in os.environ['users'].split(':')))

    if 'tk' in os.environ:
        t = threading.Thread(target=create_admin_window, args=(session,))
        t.start()
    session.join_and_run_forever(os.environ['room'])
