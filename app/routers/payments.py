from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
import uuid
import requests
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from ..database import get_db
from ..models import Payment, Student, Installment, User, School
from ..schemas import PaymentCreate, PaymentResponse, PaymentUpdate
from ..dependencies import get_current_user, require_role, require_proprietor
from ..models import UserRole
from ..config import settings
from ..utils.paystack import initialize_payment, verify_payment

router = APIRouter(prefix="/api/payments", tags=["payments"])

# ============================================
# GET ENDPOINTS
# ============================================

@router.get("", response_model=List[PaymentResponse])  # ✅ No trailing slash
async def get_payments(
    student_id: Optional[int] = None,
    installment_id: Optional[int] = None,
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all payments with optional filters"""
    query = db.query(Payment)
    
    # Filter by school (multi-tenant)
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        query = query.filter(Payment.school_id == current_user.school_id)
    
    if student_id:
        query = query.filter(Payment.student_id == student_id)
    if installment_id:
        query = query.filter(Payment.installment_id == installment_id)
    if status:
        query = query.filter(Payment.status == status)
    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    
    payments = query.order_by(Payment.payment_date.desc()).offset(skip).limit(limit).all()
    return payments

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific payment by ID"""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.get("/student/{student_id}")
async def get_student_payments(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all payments for a specific student with financial summary"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    payments = db.query(Payment).filter(
        Payment.student_id == student_id
    ).order_by(Payment.payment_date.desc()).all()
    
    total_paid = db.query(func.sum(Payment.amount)).filter(
        Payment.student_id == student_id,
        Payment.status == "completed"
    ).scalar() or 0
    
    total_pending = db.query(func.sum(Payment.amount)).filter(
        Payment.student_id == student_id,
        Payment.status == "pending"
    ).scalar() or 0
    
    return {
        "student": student,
        "payments": payments,
        "summary": {
            "total_paid": float(total_paid),
            "total_pending": float(total_pending),
            "total_fees": student.total_fees,
            "balance": student.total_fees - float(total_paid),
            "payment_count": len(payments)
        }
    }

@router.get("/recent/{limit}")
async def get_recent_payments(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent payments with student information"""
    query = db.query(
        Payment,
        Student.first_name,
        Student.last_name,
        Student.admission_number
    ).join(
        Student, Payment.student_id == Student.id
    ).filter(
        Payment.status == "completed"
    )
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            query = query.filter(Payment.school_id == current_user.school_id)
    
    payments = query.order_by(Payment.payment_date.desc()).limit(limit).all()
    
    result = []
    for payment, first_name, last_name, admission_number in payments:
        result.append({
            "id": payment.id,
            "student_id": payment.student_id,
            "student_name": f"{first_name} {last_name}",
            "admission_number": admission_number,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "payment_date": payment.payment_date,
            "status": payment.status,
            "reference": payment.reference
        })
    
    return result

@router.get("/summary/daily")
async def get_daily_payment_summary(
    date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get payment summary for a specific day"""
    if not date:
        date = datetime.now().date()
    
    start_of_day = datetime.combine(date, datetime.min.time())
    end_of_day = datetime.combine(date, datetime.max.time())
    
    query = db.query(Payment).filter(
        Payment.payment_date >= start_of_day,
        Payment.payment_date <= end_of_day,
        Payment.status == "completed"
    )
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            query = query.filter(Payment.school_id == current_user.school_id)
    
    payments = query.all()
    
    total_amount = sum(p.amount for p in payments)
    by_method = {}
    for p in payments:
        by_method[p.payment_method] = by_method.get(p.payment_method, 0) + p.amount
    
    return {
        "date": date,
        "total_transactions": len(payments),
        "total_amount": float(total_amount),
        "by_method": by_method,
        "payments": payments
    }

@router.get("/summary/monthly")
async def get_monthly_payment_summary(
    year: int = Query(None, description="Year (default: current year)"),
    month: int = Query(None, description="Month (1-12, default: current month)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get payment summary for a specific month"""
    now = datetime.now()
    if not year:
        year = now.year
    if not month:
        month = now.month
    
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    query = db.query(Payment).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date < end_date,
        Payment.status == "completed"
    )
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            query = query.filter(Payment.school_id == current_user.school_id)
    
    payments = query.all()
    
    total_amount = sum(p.amount for p in payments)
    
    daily = {}
    for p in payments:
        day = p.payment_date.day
        daily[day] = daily.get(day, 0) + p.amount
    
    return {
        "year": year,
        "month": month,
        "total_transactions": len(payments),
        "total_amount": float(total_amount),
        "daily_breakdown": daily,
        "payments": payments
    }

# ============================================
# POST ENDPOINTS
# ============================================

@router.post("", response_model=PaymentResponse)  # ✅ No trailing slash
async def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Create a new payment record (manual entry)"""
    student = db.query(Student).filter(Student.id == payment.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if payment.installment_id:
        installment = db.query(Installment).filter(
            Installment.id == payment.installment_id,
            Installment.student_id == payment.student_id
        ).first()
        if not installment:
            raise HTTPException(status_code=404, detail="Installment not found")
        
        if installment.status == "paid":
            raise HTTPException(status_code=400, detail="Installment already paid")
        
        installment.status = "paid"
        installment.paid_at = datetime.now()
    
    if payment.amount > student.balance:
        raise HTTPException(
            status_code=400, 
            detail=f"Payment amount (${payment.amount}) exceeds student balance (${student.balance})"
        )
    
    reference = f"PAY-{uuid.uuid4().hex[:8].upper()}-{datetime.now().strftime('%Y%m%d')}"
    
    db_payment = Payment(
        student_id=payment.student_id,
        installment_id=payment.installment_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference=reference,
        status="completed",
        school_id=student.school_id,
        payment_date=datetime.now()
    )
    db.add(db_payment)
    
    student.balance -= payment.amount
    
    db.commit()
    db.refresh(db_payment)
    
    return db_payment

@router.post("/manual", response_model=PaymentResponse)
async def create_manual_payment(
    payment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Record a manual payment (cash, bank transfer, etc.)"""
    required_fields = ['student_id', 'amount', 'payment_method']
    for field in required_fields:
        if field not in payment_data:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required field: {field}"
            )
    
    student = db.query(Student).filter(Student.id == payment_data["student_id"]).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    amount = float(payment_data["amount"])
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    
    if amount > student.balance:
        raise HTTPException(
            status_code=400,
            detail=f"Amount (${amount}) exceeds student balance (${student.balance})"
        )
    
    if payment_data.get("installment_id"):
        installment = db.query(Installment).filter(
            Installment.id == payment_data["installment_id"],
            Installment.student_id == payment_data["student_id"]
        ).first()
        if not installment:
            raise HTTPException(status_code=404, detail="Installment not found")
        
        if installment.status == "paid":
            raise HTTPException(status_code=400, detail="Installment already paid")
        
        installment.status = "paid"
        installment.paid_at = datetime.now()
    
    reference = payment_data.get("reference") or f"MANUAL-{uuid.uuid4().hex[:8].upper()}"
    payment_date = datetime.now()
    if payment_data.get("payment_date"):
        try:
            payment_date = datetime.fromisoformat(payment_data["payment_date"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payment date format")
    
    db_payment = Payment(
        student_id=payment_data["student_id"],
        installment_id=payment_data.get("installment_id"),
        amount=amount,
        payment_method=payment_data["payment_method"],
        reference=reference,
        status="completed",
        school_id=student.school_id,
        payment_date=payment_date
    )
    db.add(db_payment)
    
    student.balance -= amount
    
    if payment_data.get("notes"):
        db_payment.paystack_response = json.dumps({"notes": payment_data["notes"]})
    
    db.commit()
    db.refresh(db_payment)
    
    return db_payment

# ============================================
# PAYSTACK INTEGRATION
# ============================================

@router.post("/initialize-paystack")
async def initialize_paystack_payment(
    email: str,
    amount: float,
    student_id: int,
    installment_id: Optional[int] = None,
    callback_url: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initialize a payment with Paystack"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    
    if installment_id:
        installment = db.query(Installment).filter(
            Installment.id == installment_id,
            Installment.student_id == student_id
        ).first()
        if not installment:
            raise HTTPException(status_code=404, detail="Installment not found")
        
        if installment.status == "paid":
            raise HTTPException(status_code=400, detail="Installment already paid")
    
    reference = f"PS-{uuid.uuid4().hex[:8].upper()}"
    
    db_payment = Payment(
        student_id=student_id,
        installment_id=installment_id,
        amount=amount,
        payment_method="card",
        reference=reference,
        status="pending",
        school_id=student.school_id,
        payment_date=datetime.now()
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    
    try:
        result = initialize_payment(email, amount, reference)
        
        if not result.get("status"):
            db.delete(db_payment)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Payment initialization failed")
            )
        
        db_payment.paystack_response = json.dumps(result)
        db.commit()
        
        return {
            "authorization_url": result["data"]["authorization_url"],
            "reference": reference,
            "payment_id": db_payment.id,
            "amount": amount,
            "student_id": student_id
        }
        
    except Exception as e:
        db.delete(db_payment)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Payment initialization failed: {str(e)}")

@router.post("/verify-paystack")
async def verify_paystack_payment(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify a Paystack payment"""
    payment = db.query(Payment).filter(Payment.reference == reference).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status == "completed":
        return {"status": "already_completed", "payment": payment}
    
    try:
        result = verify_payment(reference)
        
        if result.get("status") and result["data"]["status"] == "success":
            payment.status = "completed"
            payment.paystack_response = json.dumps(result)
            
            if payment.installment_id:
                installment = db.query(Installment).filter(
                    Installment.id == payment.installment_id
                ).first()
                if installment:
                    installment.status = "paid"
                    installment.paid_at = datetime.now()
            
            student = db.query(Student).filter(
                Student.id == payment.student_id
            ).first()
            if student:
                student.balance -= payment.amount
            
            db.commit()
            db.refresh(payment)
            
            return {
                "status": "success",
                "payment": payment,
                "verification": result["data"]
            }
        else:
            payment.status = "failed"
            payment.paystack_response = json.dumps(result)
            db.commit()
            
            return {
                "status": "failed",
                "message": result.get("message", "Payment verification failed"),
                "payment": payment
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Payment verification failed: {str(e)}"
        )

@router.post("/paystack-webhook")
async def paystack_webhook(
    request: dict,
    db: Session = Depends(get_db)
):
    """Paystack webhook endpoint"""
    event = request.get("event")
    data = request.get("data", {})
    
    if event == "charge.success":
        reference = data.get("reference")
        payment = db.query(Payment).filter(Payment.reference == reference).first()
        if payment:
            payment.status = "completed"
            payment.paystack_response = json.dumps(data)
            
            if payment.installment_id:
                installment = db.query(Installment).filter(
                    Installment.id == payment.installment_id
                ).first()
                if installment and installment.status != "paid":
                    installment.status = "paid"
                    installment.paid_at = datetime.now()
            
            student = db.query(Student).filter(
                Student.id == payment.student_id
            ).first()
            if student:
                student.balance -= payment.amount
            
            db.commit()
            return {"status": "success", "message": "Payment processed"}
    
    return {"status": "received"}

# ============================================
# STATISTICS ENDPOINTS
# ============================================

@router.get("/stats/overview")
async def get_payment_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get payment statistics overview"""
    query = db.query(Payment).filter(Payment.status == "completed")
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            query = query.filter(Payment.school_id == current_user.school_id)
    
    total_payments = query.count()
    total_amount = query.with_entities(func.sum(Payment.amount)).scalar() or 0
    
    by_method = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total")
    ).filter(Payment.status == "completed")
    
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            by_method = by_method.filter(Payment.school_id == current_user.school_id)
    
    by_method = by_method.group_by(Payment.payment_method).all()
    
    return {
        "total_payments": total_payments,
        "total_amount": float(total_amount),
        "by_method": [
            {"method": m.payment_method, "count": m.count, "total": float(m.total)}
            for m in by_method
        ]
    }

print("✅ Payments router loaded successfully!")