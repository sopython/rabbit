import asyncio
import websockets

import queue
import threading
import time

import json

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
listener_queue_lock = threading.Lock()
def listener_queue_populator():
    while True:
        item = master_message_queue.get()
        with listener_queue_lock:
            for listener_queue in listener_queues:
                listener_queue.put(item)
thread = threading.Thread(target=listener_queue_populator)
thread.daemon = True
thread.start()

async def handle_user_request(websocket, message):
    print("Got message from client.")
    print(repr(message))
    d = json.loads(message)
    if d["event_type"] == "register_interest":
        interests.add(d["user_id"])
    elif d["event_type"] == "create_annotation":
        print("create_annotation. Echoing...")
        #todo: insert data from d into database.
        #for now, let's just echo the data back to the user.
        await websocket.send(json.dumps(d))
        print("echoed.")


async def handler(websocket, path):
    my_queue = queue.Queue()
    with listener_queue_lock:
        listener_queues.append(my_queue)
    async def producer():
        return my_queue.get()

    print("Connection opened.")

    #first message sent by the client should be a handshake with a dict containing their user id and token and protocol version.
    response = await websocket.recv()
    print("parsing handshake...")
    try:
        handshake = json.loads(response)
    except json.decoder.JSONDecodeError:
        print("Could not parse handshake: {}".format(repr(handshake)))
        await websocket.send(json.dumps({"event_type": "dropped", "reason": "handshake missing parameter {}".format(repr(key))}))
        return
    print("parsed.")

    print("validating handshake...")
    for key in ("protocol_version", "user_id", "token"):
        if key not in handshake:
            print("key {} not present.".format(repr(key)))
            await websocket.send(json.dumps({"event_type": "dropped", "reason": "handshake missing parameter {}".format(repr(key))}))
            return
    if int(handshake["protocol_version"]) < CURRENT_PROTOCOL_VERSION:
        await websocket.send(json.dumps({"event_type": "dropped", "reason": "outdated protocol version"}))
        return
    if handshake["token"] != "deadbeef": #todo: fetch actual token from db
        await websocket.send(json.dumps({"event_type": "dropped", "reason": "invalid token"}))
        return

    await websocket.send(json.dumps({"event_type": "validated"}))
    print("Validated. Awaiting client requests.")
    #handshake validated. Stream is now open for client requests and server responses.

    #set of user ids that the client is interested in getting updates for.
    interests = set()

    while True:
        message = await websocket.recv()
        await handle_user_request(websocket, message)

start_server = websockets.serve(handler, 'localhost', 8000)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()