import asyncio
import asyncio_redis
import json
import websockets

from datetime import datetime

clients = set()

      
@asyncio.coroutine
def publisher(websocket, path):
    global clients
    clients.add(websocket)
    
    redis_con = yield from asyncio_redis.Connection.create()
    sub = yield from redis_con.start_subscribe()
    yield from sub.subscribe(['live'])
    while True:
        try:
            data = yield from asyncio.wait_for(sub.next_published(), 5)
            data = json.loads(data.value)
            yield from asyncio.wait([ws.send(json.dumps(data)) for ws in clients])
        except asyncio.TimeoutError:
            out = json.dumps({'type': 'keepalive', 'ts': datetime.now().timestamp()})
            yield from asyncio.wait([ws.send(out) for ws in clients])

    redis_con.close()

ws_server = websockets.serve(publisher, 'localhost', 6000)
loop = asyncio.get_event_loop()
loop.run_until_complete(ws_server)
asyncio.get_event_loop().run_forever()