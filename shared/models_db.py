from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from shared.database import Base

class Plan(enum.Enum):
    FREE = "free"
    PRO = "pro"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255))
    plan = Column(SQLEnum(Plan), default=Plan.FREE)
    plan_expires_at = Column(DateTime, nullable=True)
    ai_generations_today = Column(Integer, default=0)
    ai_last_reset = Column(DateTime, default=datetime.utcnow)
    referral_code = Column(String(20), unique=True, index=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    filters = relationship("Filter", back_populates="user", cascade="all, delete-orphan")
    prompts = relationship("AIPrompt", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notification_settings = relationship("NotificationSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    upwork_user_id = Column(String(50), nullable=True)
    proxy_url = Column(String(255), nullable=True)
    upwork_email = Column(String(255), nullable=True)
    upwork_password_encrypted = Column(Text, nullable=True)
    upwork_2fa_secret = Column(String(255), nullable=True)
    cookies = Column(Text, nullable=True)
    cookies_updated_at = Column(DateTime, nullable=True)
    login_status = Column(String(20), default="not_configured")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="sessions")

class Filter(Base):
    __tablename__ = "filters"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), default="Default")
    categories = Column(Text, default="[]")
    keywords_include = Column(Text, default="[]")
    keywords_exclude = Column(Text, default="[]")
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="filters")

class AIPrompt(Base):
    __tablename__ = "ai_prompts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    system_prompt = Column(Text, default="")
    style_example = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="prompts")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    budget_type = Column(String(20), nullable=True)
    deadline = Column(DateTime, nullable=True)
    category = Column(String(100), nullable=True)
    skills = Column(Text, default="[]")
    url = Column(String(500), nullable=False)
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SeenProject(Base):
    __tablename__ = "seen_projects"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __unique_constraint__ = ("user_id", "project_id")

class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    enabled = Column(Boolean, default=True)
    schedule = Column(String(20), default="immediate")
    last_notification = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notification_settings")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="RUB")
    method = Column(String(20), nullable=False)
    external_id = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
