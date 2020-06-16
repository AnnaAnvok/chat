from sqlalchemy import Column, ForeignKey, String, create_engine, pool
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship, Session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


def get_session():
    dbs = f"mysql+pymysql://root:@localhost:3306/chat?charset=utf8"
    engine = create_engine(dbs, poolclass=pool.QueuePool, pool_recycle=30)
    Base.metadata.bind = engine

    db_session = sessionmaker(bind=engine, autoflush=True, autocommit=True)
    session = db_session()
    return session


class User(Base):
    __tablename__ = 'user'
    id = Column(INTEGER(11), primary_key=True)
    password = Column(String(32))
    token = Column(String(32))
    username = Column(String(32))


class Message(Base):
    __tablename__ = 'message'
    id = Column(INTEGER(11), primary_key=True)
    text = Column(String(32))
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), index=True, nullable=True)
    user = relationship('User')

    class Meta:
        table_name = 'message'
