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
thread = threading.Thread(target=dummy_queue_populator)
thread.daemon = True
thread.start()

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

async def negotiate_connection(websocket):
    """
    verifies that the client we're talking to has proper credentials and is using the appropriate protocols.
    returns True if handshake succeeds, False otherwise.
    """

    #first message sent by the client should be a handshake with a dict containing their user id and token and protocol version.
    response = await websocket.recv()
    print("parsing handshake...")
    try:
        handshake = json.loads(response)
    except json.decoder.JSONDecodeError:
        print("Could not parse handshake: {}".format(repr(handshake)))
        await websocket.send(json.dumps({"event_type": "dropped", "reason": "message was not recognizable JSON"}))
        return False
    print("parsed.")

    print("validating handshake...")
    for key in ("protocol_version", "user_id", "token"):
        if key not in handshake:
            print("key {} not present.".format(repr(key)))
            await websocket.send(json.dumps({"event_type": "dropped", "reason": "handshake missing parameter {}".format(repr(key))}))
            return False
    if int(handshake["protocol_version"]) < CURRENT_PROTOCOL_VERSION:
        await websocket.send(json.dumps({"event_type": "dropped", "reason": "outdated protocol version"}))
        return False
    if handshake["token"] != "deadbeef": #todo: fetch actual token from db
        await websocket.send(json.dumps({"event_type": "dropped", "reason": "invalid token"}))
        return False

    await websocket.send(json.dumps({"event_type": "validated"}))
    print("Validated. Awaiting client requests.")

    #handshake validated. Stream is now open for client requests and server responses.
    return True

async def handler(websocket, path):
    my_queue = queue.Queue()
    with listener_queue_lock:
        listener_queues.append(my_queue)
    async def producer():
        while my_queue.empty():
            await asyncio.sleep(0.1)
        return my_queue.get()

    print("Connection opened.")
    handshake_verified = await negotiate_connection(websocket)
    if not handshake_verified:
        return

    #set of user ids that the client is interested in getting updates for.
    interests = set()

    listener_task = asyncio.ensure_future(websocket.recv())
    producer_task = asyncio.ensure_future(producer())
    while True:
        done, pending = await asyncio.wait(
            [listener_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED)

        if listener_task in done:
            print("Got message from client.")
            message = listener_task.result()
            await handle_user_request(websocket, message)
            listener_task = asyncio.ensure_future(websocket.recv())

        if producer_task in done:
            print("Got message from producer queue.")
            message = producer_task.result()
            print(message)
            producer_task = asyncio.ensure_future(producer())

start_server = websockets.serve(handler, 'localhost', 8000)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()