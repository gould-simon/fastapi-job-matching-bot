from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    job_preferences = Column(String, nullable=True)
    subscribed_to_alerts = Column(Boolean, default=False)
    messages_sent = Column(Integer, default=0)
    last_active = Column(DateTime, default=datetime.utcnow)
