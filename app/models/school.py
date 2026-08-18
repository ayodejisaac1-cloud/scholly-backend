from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Date, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum

class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class SchoolStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"

class School(Base):
    __tablename__ = "schools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    address = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    
    # Subscription
    subscription_plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    subscription_status = Column(String, default="active")
    max_students = Column(Integer, default=500)
    max_admins = Column(Integer, default=3)
    
    # Status
    status = Column(Enum(SchoolStatus), default=SchoolStatus.PENDING)
    settings = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")
    installments = relationship("Installment", back_populates="school", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="school", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="school", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="school", cascade="all, delete-orphan")