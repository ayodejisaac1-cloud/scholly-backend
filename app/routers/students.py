from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date, timedelta
from ..database import get_db
from ..models import Student, Installment, Payment, User, School
from ..schemas import (
    StudentCreate, StudentUpdate, StudentResponse,
    InstallmentCreate, InstallmentResponse
)
from ..dependencies import get_current_user, require_role, require_school_access
from ..models import UserRole

router = APIRouter(prefix="/api/students", tags=["students"])

# ============================================
# TEST ENDPOINT
# ============================================

@router.get("/test")
async def test_endpoint():
    return {"message": "Students router is working!"}

# ============================================
# GET ENDPOINTS
# ============================================

@router.get("", response_model=List[StudentResponse])
async def get_students(
    skip: int = 0,
    limit: int = 100,
    class_name: Optional[str] = None,
    term: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all students with filters"""
    query = db.query(Student)
    
    # Filter by school (multi-tenant)
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        query = query.filter(Student.school_id == current_user.school_id)
    
    if class_name:
        query = query.filter(Student.class_name == class_name)
    if term:
        query = query.filter(Student.term == term)
    if is_active is not None:
        query = query.filter(Student.is_active == is_active)
    
    # Search functionality
    if search:
        query = query.filter(
            (Student.first_name.ilike(f"%{search}%")) |
            (Student.last_name.ilike(f"%{search}%")) |
            (Student.email.ilike(f"%{search}%")) |
            (Student.admission_number.ilike(f"%{search}%"))
        )
    
    students = query.offset(skip).limit(limit).all()
    return students

@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific student"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return student

@router.get("/{student_id}/installments", response_model=List[InstallmentResponse])
async def get_installments(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get student installments"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    installments = db.query(Installment).filter(
        Installment.student_id == student_id
    ).order_by(Installment.installment_number).all()
    return installments

@router.get("/{student_id}/financial-status")
async def get_student_financial_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get student financial status"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    installments = db.query(Installment).filter(
        Installment.student_id == student_id
    ).all()
    
    total_paid = db.query(func.sum(Payment.amount)).filter(
        Payment.student_id == student_id,
        Payment.status == "completed"
    ).scalar() or 0
    
    total_fees = student.total_fees
    balance = total_fees - total_paid
    
    today = date.today()
    overdue_amount = 0
    for inst in installments:
        if inst.status == "pending" and inst.due_date < today:
            overdue_amount += inst.amount + (inst.late_fee or 0)
    
    return {
        "student": student,
        "total_fees": total_fees,
        "total_paid": total_paid,
        "balance": balance,
        "overdue_amount": overdue_amount,
        "installments": installments
    }

# ============================================
# POST ENDPOINTS
# ============================================

@router.post("", response_model=StudentResponse)
async def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Create a new student"""
    # Check if student exists
    existing = db.query(Student).filter(
        (Student.email == student.email) | 
        (Student.admission_number == student.admission_number)
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Student with this email or admission number already exists"
        )
    
    # Set school_id
    school_id = current_user.school_id
    if current_user.role == UserRole.SUPER_ADMIN:
        school = db.query(School).first()
        if school:
            school_id = school.id
        else:
            raise HTTPException(status_code=400, detail="No school available")
    
    db_student = Student(
        **student.model_dump(),
        school_id=school_id,
        balance=student.total_fees
    )
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student

@router.post("/{student_id}/installments", response_model=List[InstallmentResponse])
async def create_installments(
    student_id: int,
    installments: List[InstallmentCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Create installments for a student"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Remove existing installments
    db.query(Installment).filter(Installment.student_id == student_id).delete()
    
    db_installments = []
    total_fees = 0
    for inst in installments:
        db_inst = Installment(
            student_id=student_id,
            school_id=student.school_id,
            **inst.model_dump()
        )
        db.add(db_inst)
        db_installments.append(db_inst)
        total_fees += inst.amount
    
    # Update student total fees
    student.total_fees = total_fees
    student.balance = total_fees
    db.commit()
    
    for inst in db_installments:
        db.refresh(inst)
    
    return db_installments

@router.post("/check-overdue")
async def check_overdue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check and update overdue installments with late fees"""
    today = date.today()
    
    # If Super Admin, check all schools
    if current_user.role == UserRole.SUPER_ADMIN:
        overdue_installments = db.query(Installment).filter(
            Installment.status == "pending",
            Installment.due_date < today
        ).all()
    else:
        # Regular users only check their school
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        overdue_installments = db.query(Installment).filter(
            Installment.status == "pending",
            Installment.due_date < today,
            Installment.school_id == current_user.school_id
        ).all()
    
    updated = []
    for inst in overdue_installments:
        days_overdue = (today - inst.due_date).days
        months_overdue = max(1, days_overdue // 30)
        late_fee = inst.amount * 0.10 * months_overdue
        
        inst.status = "overdue"
        inst.late_fee = late_fee
        updated.append(inst)
    
    db.commit()
    return {"updated": len(updated)}

# ============================================
# PUT ENDPOINTS
# ============================================

@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    student_update: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Update a student"""
    db_student = db.query(Student).filter(Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if db_student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields
    update_data = student_update.model_dump(exclude_unset=True)
    
    # ✅ Handle total_fees update - recalculate balance
    if 'total_fees' in update_data:
        # Get total paid amount
        total_paid = db.query(func.sum(Payment.amount)).filter(
            Payment.student_id == student_id,
            Payment.status == "completed"
        ).scalar() or 0
        
        # Update balance
        db_student.balance = update_data['total_fees'] - total_paid
    
    # Apply all updates
    for key, value in update_data.items():
        setattr(db_student, key, value)
    
    db.commit()
    db.refresh(db_student)
    return db_student

# ============================================
# DELETE ENDPOINTS
# ============================================

@router.delete("/{student_id}")
async def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Delete a student"""
    db_student = db.query(Student).filter(Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if db_student.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(db_student)
    db.commit()
    return {"message": "Student deleted successfully"}

# ============================================
# BULK OPERATIONS
# ============================================

@router.post("/bulk")
async def create_bulk_students(
    students_data: List[StudentCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Create multiple students at once"""
    if not students_data:
        raise HTTPException(status_code=400, detail="No student data provided")
    
    results = []
    errors = []
    
    for idx, student_data in enumerate(students_data):
        try:
            # Check if student exists
            existing = db.query(Student).filter(
                (Student.email == student_data.email) | 
                (Student.admission_number == student_data.admission_number)
            ).first()
            if existing:
                errors.append({
                    "index": idx,
                    "error": "Student with this email or admission number already exists",
                    "data": student_data
                })
                continue
            
            # Set school_id
            school_id = current_user.school_id
            if current_user.role == UserRole.SUPER_ADMIN:
                school = db.query(School).first()
                if school:
                    school_id = school.id
                else:
                    errors.append({
                        "index": idx,
                        "error": "No school available",
                        "data": student_data
                    })
                    continue
            
            db_student = Student(
                **student_data.model_dump(),
                school_id=school_id,
                balance=student_data.total_fees
            )
            db.add(db_student)
            
            results.append({
                "index": idx,
                "student_id": db_student.id,
                "status": "success"
            })
            
        except Exception as e:
            errors.append({
                "index": idx,
                "error": str(e),
                "data": student_data
            })
    
    db.commit()
    
    return {
        "total": len(students_data),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }

# ============================================
# EXPORT ENDPOINTS
# ============================================

@router.get("/export/csv")
async def export_students_csv(
    class_name: Optional[str] = None,
    term: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export students to CSV format"""
    import csv
    from io import StringIO
    from fastapi.responses import Response
    
    query = db.query(Student)
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        query = query.filter(Student.school_id == current_user.school_id)
    
    if class_name:
        query = query.filter(Student.class_name == class_name)
    if term:
        query = query.filter(Student.term == term)
    
    students = query.order_by(Student.created_at.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Admission Number", "First Name", "Last Name", "Email", "Phone",
        "Class", "Term", "Total Fees", "Balance", "Status", "Created At"
    ])
    
    # Write data
    for student in students:
        writer.writerow([
            student.admission_number,
            student.first_name,
            student.last_name,
            student.email,
            student.phone,
            student.class_name,
            student.term,
            student.total_fees,
            student.balance,
            "Active" if student.is_active else "Inactive",
            student.created_at.strftime("%Y-%m-%d %H:%M:%S") if student.created_at else ""
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=students_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

print("✅ Students router loaded successfully!")