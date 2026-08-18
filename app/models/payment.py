from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"))
    installment_id = Column(Integer, ForeignKey("installments.id"), nullable=True)
    amount = Column(Float)
    payment_date = Column(DateTime(timezone=True), server_default=func.now())
    payment_method = Column(String)
    reference = Column(String, unique=True)
    status = Column(String, default="completed")
    paystack_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    school = relationship("School", back_populates="payments")
    student = relationship("Student", back_populates="payments")
    installment = relationship("Installment", back_populates="payments")