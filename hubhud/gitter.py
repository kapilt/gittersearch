from collections.abc import Iterator
from dataclasses import dataclass
import logging
import operator
import os
import requests
import time
from urllib.parse import urlencode

import sqlalchemy as rdb

from .schema import mapper_registry, F, Array, ISODate


TOKEN_PARAMETER = os.environ.get("GITTER_TOKEN")


@mapper_registry.mapped
@dataclass
class Room:

    __tablename__ = "gitter_room"
    __sa_dataclass_metadata_key__ = "sa"

    # Room ID.
    id: str = F(rdb.Column(rdb.String, primary_key=True))

    # Room name.
    name: str = F(rdb.String)
    # Room picture
    avatarUrl: str = F(rdb.String)
    # Room topic. (default: GitHub repo description)
    topic: str = F(rdb.String)
    # Indicates if the room is a one-to-one chat.
    oneToOne: bool = F(rdb.Boolean)
    # Count of users in the room.
    userCount: int = F(rdb.SmallInteger)
    # Number of unread messages for the current user.
    unreadItems: int = F(rdb.SmallInteger)
    # Number of unread mentions for the current user.
    mentions: int = F(rdb.SmallInteger)
    # Indicates if the current user has disabled notifications.
    lurk: bool = F(rdb.Boolean)
    # Path to the room on gitter.
    url: str = F(rdb.String)
    # Type of the room.
    githubType: str = F(rdb.String)  # enum?
    # Tags that define the room.
    tags: list[str] = F(Array(rdb.String))
    # Index via gitter search
    noindex: bool = F(rdb.Boolean)
    # Current user permissions in room
    permissions: dict = F(rdb.JSON)
    # is current user member of room
    roomMember: bool = F(rdb.Boolean)
    # is this a public room
    public: bool = F(rdb.Boolean)

    # Room URI on Gitter.
    uri: str = F(rdb.String, None)
    # Room version.
    v: int = F(rdb.Integer, None)
    # Security
    security: str = F(rdb.String, None)
    # Group Id
    groupId: str = F(rdb.String, None)
    # Matrix URL
    matrixRoomLink: str = F(rdb.String, None)
    # List of users in the room. (Deprecated? subresource actually)
    users: list = F(rdb.String, None)
    # Last time the current user accessed the room in ISO format.
    lastAccessTime: str = F(ISODate, None)
    # Direct messaging User
    user: dict = F(rdb.JSON, None)
    # Indicates if the room is on of your favourites.
    favourite: int = F(rdb.Integer, None)
    # Activity.. dunno
    activity: bool = F(rdb.Boolean, True)
    # Providers... github
    providers: list = F(Array(rdb.String), None)


@mapper_registry.mapped
@dataclass
class Message:

    __tablename__ = "gitter_messages"
    __sa_dataclass_metadata_key__ = "sa"

    # ID of the message.
    id: str = F(rdb.Column(rdb.String, primary_key=True))
    # Track which github project we're referencing
    project: str = F(rdb.String)
    # Original message in plain-text/markdown.
    text: str = F(rdb.String)
    # HTML formatted message.
    html: str = F(rdb.String)
    # ISO formatted date of the message.
    sent: str = F(ISODate)

    # (User)[user-resource] that sent the message.
    fromUser: dict = F(rdb.JSON)
    # Boolean that indicates if the current user has read the message.
    unread: bool = F(rdb.Boolean)
    # Number of users that have read the message.
    readBy: int = F(rdb.SmallInteger)
    # List of URLs present in the message.
    urls: list = F(rdb.JSON)
    # List of @Mentions in the message.
    mentions: list = F(rdb.JSON)
    # List of #Issues referenced in the message.
    issues: list = F(rdb.JSON)
    # Metadata. This is currently not used for anything.
    meta: dict = F(rdb.JSON)
    # Version.
    v: int = F(rdb.SmallInteger)

    # Stands for "Gravatar version" and is used for cache busting.
    gv: int = F(rdb.SmallInteger, None)
    # Boolean that indicates whether the message is a status update (a
    # /me command)
    status: bool = F(rdb.Boolean, None)
    # Thread Message Count
    threadMessageCount: int = F(rdb.SmallInteger, None)
    # Virtual User from matrix
    virtualUser: dict = F(rdb.JSON, None)
    # If message was edited
    editedAt: str = F(ISODate, None)


@dataclass
class User:
    # Gitter User ID.
    id: str
    # Gitter/GitHub username.
    username: str
    # Gitter/GitHub user real name.
    displayName: str
    # Path to the user on Gitter.
    url: str
    # User avatar URI (small).
    avatarUrlSmall: str
    # User avatar URI (medium).
    avatarUrlMedium: str


class MessageIterator(object):

    Forward = (-1, "afterId")
    Backward = (-1, "beforeId")
    BatchSize = 100

    _date_field = operator.itemgetter("sent")

    def __init__(self, client, room: Room, direction=None, lastSeen=None):
        self.client = client
        self.room = room
        self.params = {"roomId": self.room.id, "limit": self.BatchSize}
        self.project = room.uri

        if direction is None:
            direction = self.Backward
        assert direction == self.Forward or direction == self.Backward, (
            "Unknown direction" % direction
        )

        self.dir_index, self.dir_key = direction
        if lastSeen:
            self.params[self.dir_key] = lastSeen
        self._buf = None

    def __iter__(self):
        while True:
            if not self._buf:
                self._buf = self._msort(self.client.messages(**self.params))
            for m in self._buf:
                m["project"] = self.project
                yield Message(**m)
            if not self._buf:
                break
            self.params[self.dir_key] = self._buf[self.dir_index]["id"]
            self._buf = None

    def _msort(self, messages):
        if self.dir_key == "beforeId":
            return sorted(messages, key=self._date_field, reverse=True)
        return messages


class GitterClient(object):

    log = logging.getLogger("gitter")
    default_request_interval = 1

    def __init__(self, token=TOKEN_PARAMETER, endpoint="https://api.gitter.im/v1"):
        self.endpoint = endpoint
        self.token = token
        assert token, "set GITTER_TOKEN environment variable"
        self._interval_requests = 0

    def get_room(self, project: str) -> Room:
        found = False
        for r in self.rooms():
            if r.uri == project:
                found = r
                break
        if not found:
            raise ValueError("project %s room not found" % project)
        return found

    def rooms(self) -> list[Room]:
        return [Room(**r) for r in self._request("/rooms")]

    def messages(self, roomId, afterId=None, beforeId=None, limit=100):
        params = {"limit": limit}
        if afterId and afterId != "True":
            params["afterId"] = afterId
        elif beforeId:
            params["beforeId"] = beforeId
        response = self._request("/rooms/%s/chatMessages" % roomId, **params)
        return response

    def _throttle_rate(self, r):
        remaining = int(r.headers.get("X-RateLimit-Remaining", 1000))
        if remaining > 10:
            time.sleep(self.default_request_interval)
            return
        sleep_interval = int(r.headers["X-RateLimit-Reset"]) / 1000.0 - time.time()
        self.log.info(
            "slowing down... remaining:%d requests:%d sleep:%0.2f",
            remaining,
            self._interval_requests,
            sleep_interval,
        )
        time.sleep(sleep_interval)
        self._interval_requests = 0

    def _request(self, path, **params):
        qs = urlencode(params)
        uri = self.endpoint + path
        if qs:
            uri += "?%s" % qs
        auth = {"Authorization": "Bearer %s" % self.token}
        self._interval_requests += 1
        r = requests.get(uri, headers=auth)
        r.raise_for_status()
        self._throttle_rate(r)
        return r.json()


def get_messages(client: GitterClient, room: Room, since=None) -> Iterator[Message]:
    direction = since and MessageIterator.Forward or MessageIterator.Backward
    for m in MessageIterator(client, room, direction=direction, lastSeen=since):
        yield m


def sync(session, project: str) -> int:

    # sync everything, we have to walk pointers from latest to oldest, which
    # means we'll be layering in to storage new, new-1,.. old.. when we
    # sync later we'll be in forward order with old, newer, latest.
    client = GitterClient()
    room = client.get_room(project)

    last = (
        session.query(Message).order_by(rdb.desc(Message.sent)).limit(1).one_or_none()
    )
    since = last and last.id or None

    count = 0
    seen = set()
    earliest, latest = None, None
    time_buffer = time.time()

    for m in get_messages(client, room, since):
        if m.id in seen:
            continue
        else:
            seen.add(m.id)
        if earliest and m.sent < earliest.sent:
            earliest = m
        elif earliest is None:
            earliest = m

        if latest and m.sent > latest.sent:
            latest = m
        elif latest is None:
            latest = m

        session.add(m)
        count += 1
        if count % 100 == 0:
            print(
                "sync from %s to %s in %0.2f"
                % (earliest.sent, latest.sent, time.time() - time_buffer)
            )
            session.commit()
            earliest, latest = None, None
            time_buffer = time.time()

    session.commit()
    return count
