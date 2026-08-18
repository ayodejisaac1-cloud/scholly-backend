from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Date, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum

class ExpenseCategory(str, enum.Enum):
    SALARY = "salary"
    UTILITIES = "utilities"
    MAINTENANCE = "maintenance"
    SUPPLIES = "supplies"
    OTHER = "other"

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    description = Column(String)
    category = Column(Enum(ExpenseCategory))
    amount = Column(Float)
    expense_date = Column(Date)
    receipt_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    school = relationship("School", back_populates="expenses")
    user = relationship("User", back_populates="created_expenses")