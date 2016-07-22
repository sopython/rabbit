import requests
import json
import sys
import websockets
import asyncio
import config
from urllib.parse import quote_plus
from bs4 import BeautifulSoup as BS


def get_fkey_and_cookie(email, password):
    url = "https://stackoverflow.com/users/login"
    login_data = {"email": email, "password": password}
    session = requests.Session()
    x = session.post(url,login_data)
    #TODO: perform some cursory checking to confirm that logging in actually worked

    x = session.get("http://chat.stackoverflow.com")

    soup = BS(x.content, "html.parser")
    fkey = soup.find(id="fkey")["value"]

    #I wonder if this is the right way to do this?
    cookie = "; ".join("{}={}".format(name,value) for name, value in session.cookies.iteritems())

    return fkey, cookie

fkey, cookie = get_fkey_and_cookie(config.email, config.password)

def stackOverflowPost(url, params=None):
    """
    Send a POST message using some predetermined headers and params that are always necessary when talking to SO.
    using this instead of requests.post will save you the effort of adding the fkey, cookie, etc yourself every time.
    """
    if params is None:
        params = {}
    params["fkey"] = fkey
    print(params)
    s = "&".join("{}={}".format(name, quote_plus(str(value))) for name, value in params.items())
    header={
        "Content-Length": str(len(s)),
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie
    }
    return requests.post(url, headers=header, data=s)

def get_ws_url(roomid):
    x = stackOverflowPost("http://chat.stackoverflow.com/ws-auth", {"roomid":roomid})

    if x.status_code != 200:
        raise Exception("Got status code {} {}".format(x.status_code, x.reason))

    url = json.loads(x.text)["url"] + "?l=99999999"
    return url

def query_messages(roomid):
    x = stackOverflowPost(
        "http://chat.stackoverflow.com/chats/{}/events".format(roomid),
        {"since": 0, "mode": "Messages", "Count": 100}
    )

    if x.status_code != 200:
        raise Exception("Got status code {} {}".format(x.status_code, x.reason))

    data = json.loads(x.content.decode("utf-8"))
    for event in data["events"]:
        try:
            print("{}: {}".format(event["user_name"], event["content"]))
        except KeyError:
            print("Whoops, not a message")

def send_message(roomid, text):
    x = stackOverflowPost(
        "https://chat.stackoverflow.com/chats/{}/messages/new".format(roomid),
        {"text": text}
    )

    print(x.status_code, x.reason)

#not working yet
def join(roomid):
    query_messages_test(roomid)

    s = "fkey={}".format(fkey)
    x = stackOverflowPost("http://chat.stackoverflow.com/chats/join/favorite")
    print("Join test result: ", x.status_code, x.reason)
    #print(x.content)

#not working yet
def leave(roomid):
    s = "fkey={}".format(fkey)
    x = stackOverflowPost("http://chat.stackoverflow.com/chats/leave/{}".format(roomid))
    print("Leave test result: ", x.status_code, x.reason)

def cancel_stars(messageid):
    return stackOverflowPost("http://chat.stackoverflow.com/messages/{}/unstar".format(messageid))

def move_messages(roomId, messageIds, targetRoomId):
    url = "http://chat.stackoverflow.com/admin/movePosts/{}".format(roomId)
    return stackOverflowPost(url, {"ids": ",".join(messageIds), "to": targetRoomId})

def kick(roomId, userId):
    return stackOverflowPost(
        "http://chat.stackoverflow.com/rooms/kickmute/{}".format(roomId),
        {"userId": userId}
    )