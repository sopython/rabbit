import asyncio
import websockets

import queue
import threading
import time
import datetime

import json

import dbmodel

CURRENT_PROTOCOL_VERSION = 1

#placeholder for an interprocess Queue-like object meant to recieve messages from sources that update the database, such as the bot.
master_message_queue = queue.Queue()
def dummy_queue_populator():
    while True:
        master_message_queue.put(time.time())
        time.sleep(5)
#thread = threading.Thread(target=dummy_queue_populator)
#thread.daemon = True
#thread.start()

#queues that each populate themselves using items from the master message queue. Each websocket connection gets one of these, and can consume them as they see fit.
listener_queues = []
listener_queue_lock = threading.Lock() #not sure if this is actually necessary?
def listener_queue_populator():
    while True:
        item = master_message_queue.get()
        with listener_queue_lock:
            for listener_queue in listener_queues:
                listener_queue.put(item)
thread = threading.Thread(target=listener_queue_populator)
thread.daemon = True
thread.start()

class UserScriptConnection:
    def __init__(self, websocket):
        self.websocket = websocket
        self.interests = set()
        self.queue = queue.Queue()
        self.user_id = 0 #todo: pull this from the db
        self.display_name = "Amanda Hugginkiss" #todo: pull this from the db

    def create_annotation_message(self, annotation):
        return {
            "event_type": "create_annotation",
            "user_id": annotation.user_id,
            "created": annotation.created.timestamp(),
            "text": annotation.text,
            "author_name": self.display_name
        }

    async def producer(self):
        while self.queue.empty():
            await asyncio.sleep(0.1)
        return self.queue.get()        

    async def send_initial_user_info(self, user_id):
        #fetch relevant information about user and send it to client.
        user = dbmodel.User.get_or_create(dbmodel.db_session, user_id)

        user_info_response = {
            "event_type": "update_user_info",
            "user_id": user_id,
            "updates": [
                {"update_type": "kicks", "value": user.kick_count},
                {"update_type": "flags", "value": user.flag_count}
            ]
        }

        #todo: check database for previous names.
        #for now we'll test functionality with some fake names.
        for name in ("Chicago Ted", "I.C. Weiner", user.display_name):
            user_info_response["updates"].append({"update_type": "name", "value": name})

        #todo: check database for previous avatars.
        user_info_response["updates"].append({"update_type": "avatar", "value": user.profile_image})

        print("Sending response: {}".format(user_info_response))
        await self.websocket.send(json.dumps(user_info_response))

        annotations = dbmodel.db_session.query(dbmodel.Annotation).filter_by(user_id=user_id).all() #todo: is an "order by" needed here?
        for annotation in annotations:
            await self.websocket.send(json.dumps(self.create_annotation_message(annotation)))

    async def handle_user_request(self, message):
        print("Got message from client.")
        print(repr(message))
        d = json.loads(message)
        if d["event_type"] == "register_interest":
            print("register_interest. Adding...")
            self.interests.add(d["user_id"])
            await self.send_initial_user_info(d["user_id"])

        elif d["event_type"] == "create_annotation":
            print("create_annotation. Adding to db...")
            annotation = dbmodel.Annotation(
                user_id = d["user_id"],
                author_id = self.user_id,
                created = datetime.datetime.now(),
                type = "comment",
                text= d["text"]
            )
            dbmodel.db_session.add(annotation)
            dbmodel.db_session.commit()
            print("Added.")
            master_message_queue.put(self.create_annotation_message(annotation))

    async def handle_queue_message(self, message):
        print("Got message from producer queue.")
        print(repr(message))
        if isinstance(message, dict):
            if message["event_type"] == "create_annotation":
                print("Create annotation.")
                if message["user_id"] in self.interests:
                    print("Sending to user.")
                    await self.websocket.send(json.dumps(message))
                else:
                    print("User not interested.")
            else:
                print("Unrecognized event type {}".format(message["event_type"]))
        else:
            print("Unrecognized message format: {}".format(repr(message)))

    async def negotiate_connection(self):
        """
        verifies that the client we're talking to has proper credentials and is using the appropriate protocols.
        returns True if handshake succeeds, False otherwise.
        """

        async def drop(reason):
            await self.websocket.send(json.dumps({"event_type": "dropped", "reason": reason}))
            return False

        #first message sent by the client should be a handshake with a dict containing their user id and token and protocol version.
        response = await self.websocket.recv()
        print("parsing handshake...")
        try:
            handshake = json.loads(response)
        except json.decoder.JSONDecodeError:
            print("Could not parse handshake: {}".format(repr(handshake)))
            return await drop("message was not recognizable JSON")
        print("parsed.")

        print("validating handshake...")
        for key in ("protocol_version", "user_id", "token"):
            if key not in handshake:
                print("key {} not present.".format(repr(key)))
                return await drop("handshake missing parameter {}".format(repr(key)))

        if int(handshake["protocol_version"]) < CURRENT_PROTOCOL_VERSION:
            return await drop("outdated protocol version")
        if handshake["token"] != "deadbeef": #todo: fetch actual token from db
            return await drop("invalid token")

        await self.websocket.send(json.dumps({"event_type": "validated"}))
        print("Validated. Awaiting client requests.")

        #handshake validated. Stream is now open for client requests and server responses.
        return True

    async def run_forever(self):
        with listener_queue_lock:
            listener_queues.append(self.queue)

        print("Connection opened.")
        handshake_verified = await self.negotiate_connection()
        if not handshake_verified:
            return

        #set of user ids that the client is interested in getting updates for.
        interests = set()

        listener_task = asyncio.ensure_future(self.websocket.recv())
        producer_task = asyncio.ensure_future(self.producer())
        while True:
            done, pending = await asyncio.wait(
                [listener_task, producer_task],
                return_when=asyncio.FIRST_COMPLETED)

            if listener_task in done:
                message = listener_task.result()
                await self.handle_user_request(message)
                listener_task = asyncio.ensure_future(self.websocket.recv())

            if producer_task in done:
                message = producer_task.result()
                await self.handle_queue_message(message)
                producer_task = asyncio.ensure_future(self.producer())

async def handler(websocket, path):
    connection = UserScriptConnection(websocket)
    await connection.run_forever()

start_server = websockets.serve(handler, 'localhost', 8000)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()