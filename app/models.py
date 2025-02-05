from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, Float, ForeignKey, func, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column
import json
from app.database import Base

# Read-only models for job board tables
class AccountingFirm(Base):
    """
    Represents an accounting firm that posts jobs.
    
    This model stores information about accounting firms, including their
    contact details, location, and metadata.
    """
    __tablename__ = 'jobsapp_accountingfirm'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(1000))
    slug: Mapped[str] = mapped_column(String(1000))
    link: Mapped[str] = mapped_column(String(1000))
    twitter_link: Mapped[str] = mapped_column(String(1000))
    linkedin_link: Mapped[str] = mapped_column(String(1000))
    location: Mapped[str] = mapped_column(String(10000))
    ranking: Mapped[int] = mapped_column(Integer)
    about: Mapped[str] = mapped_column(Text)
    script: Mapped[str] = mapped_column(String(1000))
    logo: Mapped[str] = mapped_column(String(1000))
    country: Mapped[str] = mapped_column(String(100))
    jobs_count: Mapped[int] = mapped_column(Integer)
    last_scraped: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="firm")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model instance to a dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'link': self.link,
            'twitter_link': self.twitter_link,
            'linkedin_link': self.linkedin_link,
            'location': self.location,
            'ranking': self.ranking,
            'about': self.about,
            'script': self.script,
            'logo': self.logo,
            'country': self.country,
            'jobs_count': self.jobs_count,
            'last_scraped': self.last_scraped.isoformat() if self.last_scraped else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Job(Base):
    """
    Represents a job posting from an accounting firm.
    
    This model stores job details including title, location, requirements,
    and metadata about when it was posted.
    """
    __tablename__ = 'jobsapp_job'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(Integer, ForeignKey('jobsapp_accountingfirm.id'))
    job_title: Mapped[str] = mapped_column(String(1000))
    seniority: Mapped[str] = mapped_column(String(1000))
    service: Mapped[str] = mapped_column(String(1000))
    industry: Mapped[str] = mapped_column(String(1000))
    location: Mapped[str] = mapped_column(String(5000))
    employment: Mapped[str] = mapped_column(String(1000))
    salary: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    date_published: Mapped[datetime] = mapped_column(DateTime)
    req_no: Mapped[str] = mapped_column(String(100))

    firm: Mapped[AccountingFirm] = relationship("AccountingFirm", back_populates="jobs")
    embedding: Mapped["JobEmbedding"] = relationship("JobEmbedding", back_populates="job", uselist=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model instance to a dictionary for JSON serialization."""
        return {
            'id': self.id,
            'firm_id': self.firm_id,
            'job_title': self.job_title,
            'seniority': self.seniority,
            'service': self.service,
            'industry': self.industry,
            'location': self.location,
            'employment': self.employment,
            'salary': self.salary,
            'description': self.description,
            'link': self.link,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'date_published': self.date_published.isoformat() if self.date_published else None,
            'req_no': self.req_no
        }

# Bot-specific models
class User(Base):
    """User model for storing Telegram user information"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    cv_text = Column(Text)
    cv_embedding = Column(Text)  # Stored as JSON string
    preferences = Column(Text)  # Stored as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    searches: Mapped[List["UserSearch"]] = relationship("UserSearch", back_populates="user")
    conversations: Mapped[List["UserConversation"]] = relationship("UserConversation", back_populates="user")
    job_matches: Mapped[List["JobMatch"]] = relationship("JobMatch", back_populates="user")

    def set_preferences(self, preferences_dict: dict):
        """Set user preferences"""
        if not isinstance(preferences_dict, dict):
            raise ValueError("Preferences must be a dictionary")
        self.preferences = json.dumps(preferences_dict)

    def get_preferences(self) -> dict:
        """Get user preferences"""
        if not self.preferences:
            return {}
        return json.loads(self.preferences)

    def set_cv_embedding(self, embedding: list):
        """Set CV embedding"""
        if not isinstance(embedding, list):
            raise ValueError("Embedding must be a list")
        self.cv_embedding = json.dumps(embedding)

    def get_cv_embedding(self) -> list:
        """Get CV embedding"""
        if not self.cv_embedding:
            return []
        return json.loads(self.cv_embedding)

class UserSearch(Base):
    """User search history model"""
    __tablename__ = "user_searches"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    search_query = Column(String, nullable=False)
    structured_preferences = Column(Text)  # Stored as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="searches")

    def set_structured_preferences(self, preferences: dict):
        """Set structured preferences"""
        if not isinstance(preferences, dict):
            raise ValueError("Preferences must be a dictionary")
        self.structured_preferences = json.dumps(preferences)

    def get_structured_preferences(self) -> dict:
        """Get structured preferences"""
        if not self.structured_preferences:
            return {}
        return json.loads(self.structured_preferences)

class UserConversation(Base):
    __tablename__ = 'user_conversations'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.telegram_id'), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_user: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="conversations")

class JobMatch(Base):
    """
    Represents a match between a user and a job posting.
    
    This model stores the similarity score between a user's CV/preferences
    and a job posting, allowing for tracking of potential matches.
    """
    __tablename__ = 'job_matches'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.telegram_id'), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey('jobsapp_job.id'), nullable=False, index=True)
    similarity_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="job_matches")
    job: Mapped[Job] = relationship("Job")

class JobEmbedding(Base):
    """
    Stores the vector embedding representation of a job posting.
    
    This model is used for semantic search functionality, storing the
    embedding vectors as JSON strings for SQLite compatibility.
    """
    __tablename__ = "job_embeddings"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobsapp_job.id"), unique=True, nullable=False)
    embedding = Column(Text)  # Store as JSON string in SQLite
    embedding_vector = Column(Text)  # Store as JSON string in SQLite
    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship("Job", back_populates="embedding")

    def set_embedding(self, embedding_vector):
        """Set embedding as JSON string"""
        if embedding_vector is not None:
            self.embedding = json.dumps(embedding_vector)
        else:
            self.embedding = None

    def get_embedding(self):
        """Get embedding as list"""
        if self.embedding:
            return json.loads(self.embedding)
        return None

    def set_embedding_vector(self, vector):
        """Set embedding vector as JSON string"""
        if vector is not None:
            self.embedding_vector = json.dumps(vector)
        else:
            self.embedding_vector = None

    def get_embedding_vector(self):
        """Get embedding vector as list"""
        if self.embedding_vector:
            return json.loads(self.embedding_vector)
        return None
