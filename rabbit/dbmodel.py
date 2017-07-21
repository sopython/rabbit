import config
from datetime import datetime, timedelta
import functools
import requests
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm.util import has_identity

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, index=True)
    display_name = Column(String, default='')
    reputation = Column(Integer)
    profile_image = Column(String)

    is_banned = Column(Boolean, default=False)
    kick_count = Column(Integer, default=0)
    trash_count = Column(Integer, default=0)
    flag_count = Column(Integer, default=0)

    gold_tag_badges = Column(String, default='')
    user_type = Column(String)
    created = Column(DateTime, default=datetime.utcnow)
    updated = Column(DateTime, default=datetime.utcnow)
    notes = relationship('Annotation', foreign_keys='Annotation.user_id')
    messages = relationship('Message', foreign_keys='Message.user_id')
    permissions = relationship('Permission')

    def update_from_SE(self, force=False, cache=timedelta(86400)):
        if (
            has_identity(self) and self.user_id and not force
            and (datetime.utcnow() - self.updated) < cache
        ):
            return self

        user = requests.get(
            'http://api.stackexchange.com/2.2/users/{}'.format(self.user_id),
            {'site': 'stackoverflow'}
        ).json()['items'][0]

        self.display_name = user['display_name']
        self.reputation = user['reputation']
        self.profile_image = user['profile_image']
        self.user_type = user['user_type']

        gold_badges = requests.get(
            'http://api.stackexchange.com/2.2/users/{}/badges'.format(self.user_id),
            {'site': 'stackoverflow', 'max': 'gold', 'sort': 'rank'}
        ).json()

        self.gold_tag_badges = ' '.join(
            badge['name'] for badge in gold_badges['items']
            if badge['badge_type'] == 'tag_based'
        )

        self.updated = datetime.utcnow()

    @classmethod
    def get_or_create(cls, session, user_id, force=False):
        qry = session.query(cls).filter_by(user_id=user_id)
        user = qry.first()
        if user:
            user.update_from_SE(force)
        else:
            user = cls(user_id=user_id)
            user.update_from_SE(True)
            session.add(user)
            session.commit() #not sure if this is a great idea, but it seems to be necessary in order for the default values to populate themselves properly
        return user

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    event_type = Column(Integer)
    room_id = Column(Integer)
    user_id = Column(ForeignKey('users.user_id'))
    reply_to = Column(ForeignKey('users.user_id'))
    text = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Permission(Base):
    __tablename__ = 'users_permissions'
    id = Column(Integer, primary_key=True)
    user = Column(ForeignKey('users.id'))
    permission = Column(String(30))
    type = Column(Boolean, default=True)


class Annotation(Base):
    __tablename__ = 'users_annotations'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    author_id = Column(ForeignKey('users.id'))
    created = Column(DateTime, default=datetime.utcnow)
    type = Column(String)
    text = Column(Text, nullable=False)


@functools.lru_cache()
def get_session():
    engine = create_engine(config.database_connection_string)
    Base.metadata.create_all(engine)
    return sessionmaker(engine)()