from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    job_preferences = Column(String, nullable=True)
    subscribed_to_alerts = Column(Boolean, default=False)
    messages_sent = Column(Integer, default=0)
    last_active = Column(DateTime, default=datetime.utcnow)
    created_at = Column(Date)

class UserSearch(Base):
    __tablename__ = "user_searches"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer)
    search_query = Column(Text)
    structured_preferences = Column(Text, nullable=True)  # Store JSON as text
    created_at = Column(Date, default=datetime.utcnow().date())

class AccountingFirm(Base):
    __tablename__ = "JobsApp_accountingfirm"

    id = Column(Integer, primary_key=True)
    name = Column(String(1000))
    slug = Column(String(1000))
    link = Column(String(1000))
    twitter_link = Column(String(1000))
    linkedin_link = Column(String(1000))
    location = Column(String(10000))
    ranking = Column(Integer)
    about = Column(Text)
    script = Column(String(1000))  # Path to script file
    logo = Column(String(1000))    # Path to logo file
    country = Column(String(100))
    jobs_count = Column(Integer, default=0)
    last_scraped = Column(DateTime, nullable=True)
    
    created_at = Column(Date)
    updated_at = Column(Date)

    # Relationship
    jobs = relationship("Job", back_populates="firm")

class Job(Base):
    __tablename__ = "JobsApp_job"

    id = Column(Integer, primary_key=True)
    firm_id = Column(Integer, ForeignKey("JobsApp_accountingfirm.id"))
    job_title = Column(String(1000))
    slug = Column(String(6000))
    seniority = Column(String(1000))
    service = Column(String(1000))
    industry = Column(String(1000))
    location = Column(String(5000))
    employment = Column(String(1000))
    salary = Column(String(1000))
    description = Column(Text)
    link = Column(String(400))
    req_no = Column(String(1000))
    date_published = Column(String(1000))
    is_indexed = Column(Boolean, default=False)

    scrapped_service = Column(String(1000))
    scrapped_seniority = Column(String(1000))
    scrapped_industry = Column(String(1000))
    location_coordinates = Column(String(5000))

    created_at = Column(Date)
    updated_at = Column(Date)

    # Relationship
    firm = relationship("AccountingFirm", back_populates="jobs")
