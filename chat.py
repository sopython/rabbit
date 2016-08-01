import asyncio
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime
from elasticsearch import Elasticsearch
import functools
import json
import re
import requests
import websockets

class ChatSession(requests.Session):
    def __init__(self, room_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = room_id
        self.handlers = defaultdict(list)
        self.commands = {}
        self.es = Elasticsearch()
        self.es_index = functools.partial(self.es.index, index='chat', doc_type=room_id)
        self.es_search = functools.partial(self.es.search, index='chat', doc_type=room_id)
        self.post(
            'https://stackoverflow.com/users/login',
            {'email': 'XXX', 'password': 'YYY'}
        )
        self.get('http://chat.stackoverflow.com')

    def request(self, *args, **kwargs):
        if 'data' in kwargs:
            kwargs['data'].update(fkey=getattr(self, 'fkey', ''))
        self.lastreq = super().request(*args, **kwargs)
        self.soup = BeautifulSoup(self.lastreq.content, 'html.parser')
        try:
            self.fkey = self.soup.find(id='fkey')['value']
        except (TypeError, KeyError):
            pass
        return self.lastreq

    def send_message(self, text):
        self.post(
            'https://chat.stackoverflow.com/chats/{}/messages/new'.format(self.room_id),
            {'text': text}
        )

    @property
    def ws_url(self):
        return self.post(
            'http://chat.stackoverflow.com/ws-auth', 
            {'roomid': self.room_id}
        ).json()['url']

    def __repr__(self):
        return 'Room {}'.format(self.room_id)

    def register_event(self, *event_types):
        def wrapper(f):
            for event_type in event_types:
                self.handlers[event_type].append(f)
            def wrapped(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapped
        return wrapper

    def register_command(self, name, access=None):
        def wrapper(f):
            self.commands[name] = f
            def wrapped(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapped
        return wrapper

    def __call__(self, name, *args):
        return self.commands[name](self, *args)
   
    @asyncio.coroutine
    def dispatch(self, msg):
        data = json.loads(msg)
        for room, data in data.items():
            if 'r{}'.format(self.room_id) != room:
                continue
            for event in data.get('e', []):
                for handler in self.handlers.get(event['event_type'], []):
                    print('doing', handler)
                    handler(self, event)


sandbox = ChatSession(6)

@sandbox.register_event(1, 2, 10)
def logger(session, msg):
    session.es_index(id=msg['id'], body=msg)

@sandbox.register_event(1, 2)
def new_question(session, msg):
    q_re = re.search('stackoverflow.com/(?:q(?:uestions?)?)/(\d+)', msg['content'])
    if q_re:
        q_id = q_re.group(1)
        print('qid', q_id)
        q = requests.get(
            'http://api.stackexchange.com/2.2/questions/{}'.format(q_id),
            {'site': 'stackoverflow'}
        )
        move_messages(session, 23262, msg['message_id'])


@sandbox.register_event(1)
def on_message(session, msg):
    if msg['content'].startswith('!!') and msg['user_id'] == 1252759:
        try:
            command, *args = msg['content'].split()
            session(command[2:], *args)
        except Exception as e:
            print(e)

@sandbox.register_command('rabbit')
def show_rabbit(session):
    from random import choice
    rabbits = [
        'http://i.imgur.com/kw9y8.jpg',
        'http://i.imgur.com/670Cq.jpg',
        'http://i.imgur.com/NbGiSmd.jpg',
        'http://i.imgur.com/2ZYlX.jpg'
    ]
    session.send_message(choice(rabbits))

@sandbox.register_command('clearup')
def move_messages(session, wildcard):
    res = session.es_search(q='content:{}'.format(wildcard), fields=['message_id'], sort='time_stamp:desc')    
    ids = [id['fields']['message_id'][0] for id in res['hits']['hits']]
    session.post(
        'http://chat.stackoverflow.com/admin/movePosts/{}'.format(session.room_id),
        {'ids': ','.join(str(id) for id in ids), 'to': 71097}
    )

@asyncio.coroutine
def chat_handler(session):
    ws = yield from websockets.connect(session.ws_url + '?l=99999999', origin='http://chat.stackoverflow.com')
    while True:
        msg = yield from ws.recv()
        data = yield from session.dispatch(msg)

asyncio.get_event_loop().run_until_complete(chat_handler(sandbox))