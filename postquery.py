import requests
import json
import sys
import websockets
import asyncio
import config
from urllib.parse import quote
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

def get_ws_url(roomid):
    s="roomid={}&fkey={}".format(roomid, fkey)
    header={
        "Content-Length": str(len(fkey)),
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie
    }

    x = requests.post(
        "http://chat.stackoverflow.com/ws-auth", 
        headers=header,
        data=s
    )
    if x.status_code != 200:
        raise Exception("Got status code {} {}".format(x.status_code, x.reason))

    url = json.loads(x.text)["url"] + "?l=99999999"
    return url

def query_messages_test(roomid):
    s = "since=0&mode=Messages&msgCount=100&fkey=" + fkey
    x = requests.post(
        "http://chat.stackoverflow.com/chats/{}/events".format(roomid),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(s)),
            "Cookie": cookie
        },
        data = s
    )

    if x.status_code != 200:
        raise Exception("Got status code {} {}".format(x.status_code, x.reason))

    data = json.loads(x.content.decode("utf-8"))
    for event in data["events"]:
        try:
            print("{}: {}".format(event["user_name"], event["content"]))
        except KeyError:
            print("Whoops, not a message")

def post_message_test(roomid, text):
    s = "text={}&fkey={}".format(quote(text), fkey)

    x = requests.post(
        "https://chat.stackoverflow.com/chats/{}/messages/new".format(roomid),
        headers={
            "Content-Length": str(len(s)),
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": cookie,
        },
        data=s
    )

    print(x.status_code, x.reason)

def post_join_test(roomid):
    query_messages_test(roomid)

    s = "fkey={}".format(fkey)
    x = requests.post("http://chat.stackoverflow.com/chats/join/favorite",
            headers={
            "Content-Length": str(len(s)),
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": cookie,
        },
        data=s
    )
    print("Join test result: ", x.status_code, x.reason)
    #print(x.content)

def post_leave_test(roomid):
    s = "fkey={}".format(fkey)
    x = requests.post("http://chat.stackoverflow.com/chats/leave/{}".format(roomid),
            headers={
            "Content-Length": str(len(s)),
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": cookie,
        },
        data=s
    )
    print("Leave test result: ", x.status_code, x.reason)