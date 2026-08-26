import os

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

os.makedirs("html/database", exist_ok=True)
DATABASE_URL = "sqlite:///./html/database/voice_assistant.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(String)
    label = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    recurring = Column(Boolean, default=False)
    recurrence_type = Column(String, nullable=True)
    created_at = Column(DateTime)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Таблицы
Base.metadata.create_all(bind=engine)