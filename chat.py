import asyncio
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime
from elasticsearch import Elasticsearch
import functools
import html
import json
import random
import re
import requests
import websockets

USERS = {
    1252759: {'admin'}
}

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
            'https://chat.stackoverflow.com/chats/{}'
            '/messages/new'.format(self.room_id),
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
            f._access = access
            self.commands[name] = f
            def wrapped(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapped
        return wrapper

    def __call__(self, msg, name, *args, **kwargs):
        print('func:', name)
        func = self.commands[name]
        permissions = USERS.get(msg['user_id'], set())
        if {'admin', func._access} & permissions:
            return func(self, msg, *args, **kwargs)
        else:
            print('not allowed to call {}'.format(name))
   
    @asyncio.coroutine
    def dispatch(self, msg):
        data = json.loads(msg)
        print(data)
        for room, data in data.items():
            if 'r{}'.format(self.room_id) != room:
                continue
            for event in data.get('e', []):
                for handler in self.handlers.get(event['event_type'], []):
                    handler(self, event)
        return data


room = ChatSession(6)

@room.register_event(1, 2, 10)
def logger(session, msg):
    session.es_index(id=msg['id'], body=msg)


@room.register_event(1)
def on_message(session, msg):
    if msg['content'].startswith('!!'):
        try:
            command, *args = msg['content'].split()
            session(msg, command[2:], *args)
        except Exception as e:
            print(e)

@room.register_event(1)
def check_last_question(session, msg):
    user_perms = USERS.get(int(msg['user_id']))
    #if {'admin', 'whitelist'} & user_perms:
    #    return
    q_re = re.search('stackoverflow.com/q(?:uestions?)?/(\d+)', msg['content'])
    if q_re:
        q_id = q_re.group(1)
        print('clq:', q_id)
        q = requests.get(
            'http://api.stackexchange.com/2.2/questions/{}'.format(q_id),
            {'order': 'desc', 'sort': 'activity', 'site': 'stackoverflow'}
        ).json()
        if q['items']:
            session.send_message(
                '{} just posted a link to *{}* by {} first posted {}'.format(
                    msg['user_name'],
                    html.unescape(q['items'][0]['title']),
                    q['items'][0]['owner']['display_name'],
                    datetime.fromtimestamp(q['items'][0]['creation_date'])
                )
            )

@room.register_event(3)
def check_last_question_on_join(session, msg):
    print('user joined')
    q = requests.get(
        'http://api.stackexchange.com/2.2/users/{}/questions'.format(msg['user_id']),
        {'order': 'desc', 'sort': 'activity', 'site': 'stackoverflow'}
    ).json()
    if q['items']:
        session.send_message(
            '*{}* was the last posted Q by {} at {}'.format(
                html.unescape(q['items'][0]['title']),
                q['items'][0]['owner']['display_name'],
                datetime.fromtimestamp(q['items'][0]['creation_date'])
            )
        )


        



@room.register_command('rabbit', access='rabbit')
def show_rabbit(session, msg):
    rabbits = [
        'http://i.imgur.com/kw9y8.jpg',
        'http://i.imgur.com/670Cq.jpg',
        'http://i.imgur.com/NbGiSmd.jpg',
        'http://i.imgur.com/2ZYlX.jpg'
    ]
    session.send_message(random.choice(rabbits))

@room.register_command('clearup', access='trusted')
def move_messages(session, msg, wildcard):
    res = session.es_search(
        q='content:{}'.format('*' + wildcard + '*'), 
        fields=['message_id'], 
        sort='time_stamp:desc',
        expand_wildcards='all'
    )    
    ids = [id['fields']['message_id'][0] for id in res['hits']['hits']]
    session.post(
        'http://chat.stackoverflow.com/admin/movePosts/{}'.format(session.room_id),
        {'ids': ','.join(str(id) for id in ids), 'to': 71097}
    )

@room.register_command('listperm', access='admin')
def list_permissions(session, msg, user_id, *perms):
    user_perms = USERS.get(int(user_id), set())
    available_funcs = [name for name, fn in session.commands.items() if {'admin', fn._access} & user_perms]
    session.send_message(
        'id:{} current permissions:{} available commands:{}'.format(
        user_id,
        ','.join(sorted(user_perms)),
        ','.join(sorted(available_funcs))
        )
    )

@room.register_command('addperm', access='admin')
def add_permissions(session, msg, user_id, *perms):
    user_perms = USERS.setdefault(int(user_id), set())
    user_perms.update(perms)
    session.send_message('id:{} permissions set to:{}'.format(user_id, ','.join(sorted(user_perms))))

@room.register_command('delperm', access='admin')
def add_permissions(session, msg, user_id, *perms):
    user_perms = USERS.setdefault(int(user_id), set())
    user_perms.difference_update(perms)
    session.send_message('id:{} permissions set to:{}'.format(user_id, ','.join(sorted(user_perms))))


@asyncio.coroutine
def chat_handler(session):
    ws = yield from websockets.connect(
        session.ws_url + '?l=99999999', 
        origin='http://chat.stackoverflow.com'
    )
    while True:
        msg = yield from ws.recv()
        data = yield from session.dispatch(msg)

asyncio.get_event_loop().run_until_complete(chat_handler(room))