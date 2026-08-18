from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Installment(Base):
    __tablename__ = "installments"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"))
    installment_number = Column(Integer)
    due_date = Column(Date)
    amount = Column(Float)
    status = Column(String, default="pending")
    late_fee = Column(Float, default=0.0)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="installments")
    student = relationship("Student", back_populates="installments")
    payments = relationship("Payment", back_populates="installment")