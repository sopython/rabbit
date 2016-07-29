import sqlalchemy
from sqlalchemy import create_engine
engine = create_engine(config.database_connection_string)
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import Column, Integer, String, Boolean
class User(Base):
    __tablename__ = 'users'

    surrogate_id = Column(Integer, primary_key=True)
    so_user_id = Column(Integer, index=True, unique=True)
    is_banned = Column(Boolean)
    kick_count = Column(Integer)
    trash_count = Column(Integer)
    flag_count = Column(Integer)
    notes = Column(String)

    def __repr__(self):
        names = "id is_banned kick_count trash_count flag_count notes".split()
        return "<User(so_user_id={}, is_banned={}, kick_count={}, trash_count={}, flag_count={}, notes={})>".format(self.so_user_id, self.is_banned, self.kick_count, self.trash_count, self.flag_count, self.notes)

Base.metadata.create_all(engine)

def get_or_create_user(so_user_id):
    user = session.query(User).filter(User.so_user_id == so_user_id).one_or_none()
    if user is None:
        return User(so_user_id=so_user_id, is_banned=False, kick_count=0, trash_count=0, flag_count=0, notes="")
    else:
        return user


from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
session = Session()