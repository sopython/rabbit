import asyncio
import asyncio_redis
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory
import json
from pprint import pprint
from datetime import datetime
from elasticsearch import Elasticsearch
from redis import Redis

from test import mlt

es = Elasticsearch()
redis_con = Redis()

class StackActivity(WebSocketClientProtocol):

   def onConnect(self, response):
      # signal elsewhere later
      print('Connected:', response.peer)

   def onOpen(self):
      # request SO questions
      # (use 155-questions-active) for ALL SE sites)
      # (also should be able to put '1-questions-active-tag-python*' or similar)
      self.sendMessage(b'155-questions-active')
      # ^^^ might want to `call_later` this for a few seconds...

   def onMessage(self, payload, is_binary):
      # not sure if binary should technically happen?
      print('Message received')
      event = json.loads(payload.decode('utf-8'))
      data = json.loads(event['data'])
      # it's a question, so subscribe to its events...
      if event['action'] == '155-questions-active':
         data['user_id'] = int(data.pop('ownerUrl').rsplit('/', 2)[1])
         data['datetime'] = datetime.fromtimestamp(data['lastActivityDate'])
         res = es.index(index='summary', doc_type='s', body=data)
         obj = es.get(index='summary', id=res['_id'])['_source']
         related = mlt(obj['bodySummary'], size=5)
         obj['type'] = 'data'
         pprint(obj)
         obj['related'] = [r['_source']['Title'] for r in related['hits']['hits']]
         redis_con.publish('live', json.dumps(obj))

   def onClose(self, was_clean, code, reason):
      print('Closed:', reason)


factory = WebSocketClientFactory('ws://qa.sockets.stackexchange.com')
factory.protocol = StackActivity

loop = asyncio.get_event_loop()
coro = loop.create_connection(factory, 'qa.sockets.stackexchange.com', 80)
loop.run_until_complete(coro)
loop.run_forever()
loop.close()