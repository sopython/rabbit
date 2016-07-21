import requests
import json
import sys
import websockets
import asyncio
import config

def get_ws_url(roomid):
    s="roomid={}&fkey={}".format(roomid, config.fkey)
    header={
        "Content-Length": str(len(config.fkey)),
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": config.cookie
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

def query_messages_test():
    x = requests.post(
        "http://chat.stackoverflow.com/chats/6/events",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data = "since=0&mode=Messages&msgCount=10&fkey=" + config.fkey
    )

    if x.status_code != 200:
        raise Exception("Got status code {} {}".format(x.status_code, x.reason))

    data = json.loads(x.content.decode("utf-8"))
    for event in data["events"]:
        print("{}: {}".format(event["user_name"], event["content"]))

def post_message_test():
    s = "text=test&fkey=" + config.fkey

    x = requests.post(
        "https://chat.stackoverflow.com/chats/1/messages/new",
        headers={
            "Content-Length": str(len(s)),
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": config.cookie,
        },
        data=s
    )

    print(x.status_code, x.reason)