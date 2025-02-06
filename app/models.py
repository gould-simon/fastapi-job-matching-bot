from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, Float, ForeignKey, func, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
import json
from app.database import Base, get_environment_info
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

# Get database type
env_info = get_environment_info()
IS_SQLITE = env_info['database_type'] == 'sqlite'
IS_POSTGRES = not IS_SQLITE

# Use Text for SQLite, JSONB for PostgreSQL
JsonType = Text if IS_SQLITE else JSONB

def serialize_json(data: Union[dict, list, None]) -> Optional[str]:
    """Serialize data to JSON string for database storage."""
    if data is None:
        return None
    try:
        # For PostgreSQL, return the data as is if it's already the right type
        if IS_POSTGRES:
            if isinstance(data, (dict, list)):
                return data
            raise ValueError(f"Data must be dict or list for PostgreSQL, got {type(data)}")
        
        # For SQLite, convert to JSON string
        if isinstance(data, str):
            # Verify it's valid JSON if it's already a string
            json.loads(data)
            return data
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error serializing JSON data: {str(e)}", extra={
            'error_type': type(e).__name__,
            'data_type': type(data).__name__,
            'database_type': 'postgresql' if IS_POSTGRES else 'sqlite'
        })
        raise ValueError(f"Invalid data for JSON serialization: {str(e)}")

def deserialize_json(data: Union[str, dict, list, None]) -> Union[dict, list, None]:
    """Deserialize JSON data from database."""
    if data is None:
        return None
    try:
        # For PostgreSQL, return the data as is if it's already the right type
        if IS_POSTGRES:
            if isinstance(data, (dict, list)):
                return data
            raise ValueError(f"Expected dict or list from PostgreSQL, got {type(data)}")
        
        # For SQLite, parse JSON string
        if not isinstance(data, str):
            raise ValueError(f"Expected string from SQLite, got {type(data)}")
        return json.loads(data)
    except Exception as e:
        logger.error(f"Error deserializing JSON data: {str(e)}", extra={
            'error_type': type(e).__name__,
            'data_type': type(data).__name__,
            'database_type': 'postgresql' if IS_POSTGRES else 'sqlite'
        })
        return None

class JsonHandlerMixin:
    """Mixin to handle JSON serialization/deserialization."""
    
    def set_json_field(self, field_name: str, value: Union[dict, list, None]) -> None:
        """Set a JSON field with proper serialization."""
        if not hasattr(self, field_name):
            raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{field_name}'")
        try:
            setattr(self, field_name, serialize_json(value))
        except Exception as e:
            logger.error(f"Error setting JSON field {field_name}: {str(e)}", extra={
                'class': self.__class__.__name__,
                'field': field_name,
                'error_type': type(e).__name__,
                'value_type': type(value).__name__
            })
            raise
    
    def get_json_field(self, field_name: str) -> Union[dict, list, None]:
        """Get a JSON field with proper deserialization."""
        if not hasattr(self, field_name):
            raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{field_name}'")
        try:
            value = getattr(self, field_name)
            return deserialize_json(value)
        except Exception as e:
            logger.error(f"Error getting JSON field {field_name}: {str(e)}", extra={
                'class': self.__class__.__name__,
                'field': field_name,
                'error_type': type(e).__name__
            })
            return None

# Read-only models for job board tables
class AccountingFirm(Base):
    """
    Represents an accounting firm that posts jobs.
    
    This model stores information about accounting firms, including their
    contact details, location, and metadata.
    """
    __tablename__ = 'JobsApp_accountingfirm'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(1000), nullable=False)
    slug: Mapped[str] = mapped_column(String(1000), nullable=False)
    link: Mapped[str] = mapped_column(String(1000), nullable=False)
    twitter_link: Mapped[Optional[str]] = mapped_column(String(1000))
    linkedin_link: Mapped[Optional[str]] = mapped_column(String(1000))
    location: Mapped[Optional[str]] = mapped_column(String(10000))
    ranking: Mapped[Optional[int]] = mapped_column(Integer)
    about: Mapped[Optional[str]] = mapped_column(Text)
    script: Mapped[Optional[str]] = mapped_column(String(1000))
    logo: Mapped[Optional[str]] = mapped_column(String(1000))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    jobs_count: Mapped[Optional[int]] = mapped_column(Integer)
    last_scraped: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

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
    __tablename__ = 'JobsApp_job'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(Integer, ForeignKey('JobsApp_accountingfirm.id'), nullable=False)
    job_title: Mapped[str] = mapped_column(String(1000), nullable=False)
    seniority: Mapped[Optional[str]] = mapped_column(String(1000))
    service: Mapped[Optional[str]] = mapped_column(String(1000))
    industry: Mapped[Optional[str]] = mapped_column(String(1000))
    location: Mapped[Optional[str]] = mapped_column(String(5000))
    employment: Mapped[Optional[str]] = mapped_column(String(1000))
    salary: Mapped[Optional[str]] = mapped_column(String(1000))
    description: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[Optional[str]] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    date_published: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    req_no: Mapped[Optional[str]] = mapped_column(String(100))

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
class User(Base, JsonHandlerMixin):
    """User model for storing Telegram user information"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String)
    first_name: Mapped[Optional[str]] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String)
    cv_text: Mapped[Optional[str]] = mapped_column(Text)
    cv_embedding: Mapped[Optional[str]] = mapped_column(JsonType)
    preferences: Mapped[Optional[str]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    searches: Mapped[List["UserSearch"]] = relationship("UserSearch", back_populates="user")
    conversations: Mapped[List["UserConversation"]] = relationship("UserConversation", back_populates="user")
    job_matches: Mapped[List["JobMatch"]] = relationship("JobMatch", back_populates="user")

    def set_preferences(self, preferences_dict: dict) -> None:
        """Set user preferences"""
        if not isinstance(preferences_dict, dict):
            raise ValueError("Preferences must be a dictionary")
        self.set_json_field('preferences', preferences_dict)

    def get_preferences(self) -> dict:
        """Get user preferences"""
        return self.get_json_field('preferences') or {}

    def set_cv_embedding(self, embedding: list) -> None:
        """Set CV embedding"""
        if not isinstance(embedding, list):
            raise ValueError("Embedding must be a list")
        self.set_json_field('cv_embedding', embedding)

    def get_cv_embedding(self) -> list:
        """Get CV embedding"""
        return self.get_json_field('cv_embedding') or []

class UserSearch(Base, JsonHandlerMixin):
    """User search history model"""
    __tablename__ = "user_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    search_query: Mapped[str] = mapped_column(String, nullable=False)
    structured_preferences: Mapped[Optional[str]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="searches")

    def set_structured_preferences(self, preferences: dict) -> None:
        """Set structured preferences"""
        if not isinstance(preferences, dict):
            raise ValueError("Preferences must be a dictionary")
        self.set_json_field('structured_preferences', preferences)

    def get_structured_preferences(self) -> dict:
        """Get structured preferences"""
        return self.get_json_field('structured_preferences') or {}

class UserConversation(Base):
    __tablename__ = 'user_conversations'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.telegram_id'), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_user: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

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
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey('JobsApp_job.id'), nullable=False, index=True)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="job_matches")
    job: Mapped[Job] = relationship("Job")

class JobEmbedding(Base, JsonHandlerMixin):
    """Stores the vector embedding representation of a job posting."""
    __tablename__ = "job_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("JobsApp_job.id"), unique=True, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536))  # OpenAI embeddings are 1536 dimensions
    embedding_vector: Mapped[Optional[list]] = mapped_column(Vector(1536))
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship("Job", back_populates="embedding")

    def set_embedding(self, embedding_vector: Optional[list]) -> None:
        """Set the embedding vector"""
        self.embedding = embedding_vector

    def get_embedding(self) -> Optional[list]:
        """Get the embedding vector"""
        return self.embedding

    def set_embedding_vector(self, vector: Optional[list]) -> None:
        """Set the embedding vector"""
        self.embedding_vector = vector

    def get_embedding_vector(self) -> Optional[list]:
        """Get the embedding vector"""
        return self.embedding_vector
