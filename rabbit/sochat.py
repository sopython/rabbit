import requests
import json
import asyncio
import logging
import enum
from urllib.parse import quote_plus
from bs4 import BeautifulSoup as BS
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory


logger = logging.getLogger('rabbit')

EventType = enum.IntEnum('EventType', [
    "message_posted",
    "message_edited",
    "user_entered",
    "user_left",
    "room_name_changed",
    "message_starred",
    "UNKNOWN",
    "user_mentioned",
    "message_flagged",
    "message_deleted",
    "file_added",
    "moderator_flag",
    "user_settings_chagned",
    "global_notification",
    "account_level_changed",
    "user_notification",
    "invitation",
    "message_reply",
    "message_moved_out",
    "message_moved_in",
    "time_break",
    "feed_ticker",
    "user_suspended",
    "user_merged",
])

class StackOverflowChatSession:
    def __init__(self, email, password):
        url = "https://stackoverflow.com/users/login"
        login_data = {"email": email, "password": password}
        session = requests.Session()
        logger.debug("Logging in")
        session.post(url,login_data)
        #TODO: perform some cursory checking to confirm that logging in actually worked

        logger.debug("Getting cookie")
        x = session.get("http://chat.stackoverflow.com")

        soup = BS(x.content, "html.parser")
        self.fkey = soup.find(id="fkey")["value"]

        #I wonder if this is the right way to do this?
        self.cookie = "; ".join("{}={}".format(name,value) for name, value in session.cookies.iteritems())

    def join(self, roomid):
        #Not sure how you're actually _supposed_ to join a room, but talking to the web service seems to do it.
        return self._get_webservice_url(roomid)

    def get_recent_events(self, roomid, count=100):
        x = self._post(
            "http://chat.stackoverflow.com/chats/{}/events".format(roomid),
            {"since": 0, "mode": "Messages", "Count": count}
        )

        if x.status_code != 200:
            raise Exception("Got status code {} {}".format(x.status_code, x.reason))

        return json.loads(x.content.decode("utf-8"))

    def send_message(self, roomid, text):
        return self._post(
            "https://chat.stackoverflow.com/chats/{}/messages/new".format(roomid),
            {"text": text}
        )

    #not working yet
    def leave(self, roomid):
        return self._post("http://chat.stackoverflow.com/chats/leave/{}".format(roomid))

    def cancel_stars(self, messageid):
        return self._post("http://chat.stackoverflow.com/messages/{}/unstar".format(messageid))

    def move_messages(self, roomId, messageIds, targetRoomId):
        url = "http://chat.stackoverflow.com/admin/movePosts/{}".format(roomId)
        return self._post(url, {"ids": ",".join(messageIds), "to": targetRoomId})

    def kick(self, roomId, userId):
        #not tested but probably works
        return self._post(
            "http://chat.stackoverflow.com/rooms/kickmute/{}".format(roomId),
            {"userId": userId}
        )

    #event hooks.
    #these abstract methods should be overridden by concrete implementations of this class.
    def onConnect(self, response):
        pass
    def onOpen(self):
        pass
    def onMessage(self, payload):
        pass
    def onClose(self, was_clean, code, reason):
        pass

    def join_and_run_forever(self, roomid):
        session = self
        #yes, I'm putting a class definition inside a method definition. I acknowledge that this is weird.
        #this has to go here because I don't see any other way for the class' methods to refer to `self` properly.
        class SoClient(WebSocketClientProtocol):
            def onConnect(self, response): session.onConnect(response)
            def onOpen(self): session.onOpen()
            def onMessage(self, payload, is_binary): session.onMessage(payload)
            def onClose(self, was_clean, code, reason): session.onClose(was_clean, code, reason)
        url = self.join(roomid)
        host = "chat.sockets.stackexchange.com"
        factory = WebSocketClientFactory(url, headers={"Origin":"http://chat.stackoverflow.com"})
        factory.protocol = SoClient
        self.loop = asyncio.get_event_loop()
        coro = self.loop.create_connection(factory, host, 80)
        self.loop.run_until_complete(coro)
        self.loop.run_forever()
        self.loop.close()

    def _get_webservice_url(self, roomid):
        x = self._post("http://chat.stackoverflow.com/ws-auth", {"roomid":roomid})

        if x.status_code != 200:
            raise Exception("Got status code {} {}".format(x.status_code, x.reason))

        return json.loads(x.text)["url"] + "?l=99999999"

    def _post(self, url, params=None):
        """
        Send a POST message using some predetermined headers and params that are always necessary when talking to SO.
        using this instead of requests.post will save you the effort of adding the fkey, cookie, etc yourself every time.
        """
        logger.debug("Posting to {}".format(url))
        if params is None:
            params = {}
        params["fkey"] = self.fkey
        s = "&".join("{}={}".format(name, quote_plus(str(value))) for name, value in params.items())
        header={
            "Content-Length": str(len(s)),
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": self.cookie
        }
        return requests.post(url, headers=header, data=s)
