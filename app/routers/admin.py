from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
from ..database import get_db
from ..models import (
    User, UserRole, School, SchoolStatus, 
    Student, Payment, Expense, Installment,
    SubscriptionPlan, SystemSetting
)
from ..schemas import SchoolResponse, SchoolUpdate, UserResponse  # Fixed!
from ..dependencies import require_super_admin, get_current_user
from ..config import settings
from ..utils.email import EmailService

router = APIRouter(prefix="/api/admin", tags=["admin"])
email_service = EmailService()

# ... rest of your code stays exactly the same

# ============================================
# DASHBOARD STATS
# ============================================

@router.get("/dashboard/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get comprehensive system statistics for super admin dashboard"""
    
    # School stats
    total_schools = db.query(School).count()
    active_schools = db.query(School).filter(School.status == SchoolStatus.ACTIVE).count()
    pending_schools = db.query(School).filter(School.status == SchoolStatus.PENDING).count()
    suspended_schools = db.query(School).filter(School.status == SchoolStatus.SUSPENDED).count()
    
    # User stats
    total_users = db.query(User).filter(User.role != UserRole.SUPER_ADMIN).count()
    proprietors = db.query(User).filter(User.role == UserRole.PROPRIETOR).count()
    admins = db.query(User).filter(User.role == UserRole.ADMIN).count()
    teachers = db.query(User).filter(User.role == UserRole.TEACHER).count()
    
    # Student stats
    total_students = db.query(Student).count()
    active_students = db.query(Student).filter(Student.is_active == True).count()
    
    # Payment stats
    total_payments = db.query(Payment).filter(Payment.status == "completed").count()
    total_revenue = db.query(Payment).filter(Payment.status == "completed").with_entities(
        func.sum(Payment.amount)
    ).scalar() or 0
    
    # Today's stats
    today = datetime.now().date()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_payments = db.query(Payment).filter(
        Payment.payment_date >= today_start,
        Payment.status == "completed"
    ).count()
    today_revenue = db.query(Payment).filter(
        Payment.payment_date >= today_start,
        Payment.status == "completed"
    ).with_entities(func.sum(Payment.amount)).scalar() or 0
    
    # Revenue by plan
    revenue_by_plan = db.query(
        School.subscription_plan,
        func.sum(Payment.amount).label("total")
    ).join(Student, Student.school_id == School.id)\
     .join(Payment, Payment.student_id == Student.id)\
     .filter(Payment.status == "completed")\
     .group_by(School.subscription_plan).all()
    
    # Recent signups (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_signups = db.query(School).filter(
        School.created_at >= thirty_days_ago
    ).count()
    
    # Growth data (last 7 days)
    growth_data = []
    for i in range(7, -1, -1):
        date = datetime.now() - timedelta(days=i)
        day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
        day_end = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        new_schools = db.query(School).filter(
            School.created_at >= day_start,
            School.created_at <= day_end
        ).count()
        
        new_users = db.query(User).filter(
            User.created_at >= day_start,
            User.created_at <= day_end,
            User.role != UserRole.SUPER_ADMIN
        ).count()
        
        new_students = db.query(Student).filter(
            Student.created_at >= day_start,
            Student.created_at <= day_end
        ).count()
        
        growth_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "new_schools": new_schools,
            "new_users": new_users,
            "new_students": new_students
        })
    
    # Subscription breakdown
    subscription_breakdown = db.query(
        School.subscription_plan,
        func.count(School.id).label("count")
    ).group_by(School.subscription_plan).all()
    
    # Status breakdown
    status_breakdown = db.query(
        School.status,
        func.count(School.id).label("count")
    ).group_by(School.status).all()
    
    # School growth (monthly)
    monthly_growth = []
    for i in range(6, -1, -1):
        month_date = datetime.now() - timedelta(days=30 * i)
        month_start = datetime(month_date.year, month_date.month, 1, 0, 0, 0)
        if month_date.month == 12:
            month_end = datetime(month_date.year + 1, 1, 1, 0, 0, 0)
        else:
            month_end = datetime(month_date.year, month_date.month + 1, 1, 0, 0, 0)
        
        schools_count = db.query(School).filter(
            School.created_at >= month_start,
            School.created_at < month_end
        ).count()
        
        monthly_growth.append({
            "month": month_date.strftime("%B %Y"),
            "schools": schools_count
        })
    
    return {
        "schools": {
            "total": total_schools,
            "active": active_schools,
            "pending": pending_schools,
            "suspended": suspended_schools,
            "recent_signups": recent_signups
        },
        "users": {
            "total": total_users,
            "proprietors": proprietors,
            "admins": admins,
            "teachers": teachers
        },
        "students": {
            "total": total_students,
            "active": active_students
        },
        "payments": {
            "total": total_payments,
            "total_revenue": float(total_revenue),
            "today": {
                "count": today_payments,
                "revenue": float(today_revenue)
            }
        },
        "revenue_by_plan": [
            {"plan": p[0] or "free", "total": float(p[1])} 
            for p in revenue_by_plan
        ],
        "subscription_breakdown": [
            {"plan": s[0] or "free", "count": s[1]} 
            for s in subscription_breakdown
        ],
        "status_breakdown": [
            {"status": s[0], "count": s[1]} 
            for s in status_breakdown
        ],
        "growth_data": growth_data,
        "monthly_growth": monthly_growth
    }

@router.get("/dashboard/recent-activity")
async def get_recent_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get recent platform activity"""
    
    activity = []
    
    # Recent schools
    recent_schools = db.query(School).order_by(
        School.created_at.desc()
    ).limit(10).all()
    
    for school in recent_schools:
        activity.append({
            "type": "school_registered",
            "message": f"New school registered: {school.name}",
            "timestamp": school.created_at,
            "data": {"school_id": school.id, "status": school.status}
        })
    
    # Recent users
    recent_users = db.query(User).filter(
        User.role != UserRole.SUPER_ADMIN
    ).order_by(
        User.created_at.desc()
    ).limit(10).all()
    
    for user in recent_users:
        school = db.query(School).filter(School.id == user.school_id).first()
        school_name = school.name if school else "No school"
        activity.append({
            "type": "user_registered",
            "message": f"New user: {user.full_name} ({user.role}) at {school_name}",
            "timestamp": user.created_at,
            "data": {"user_id": user.id, "role": user.role}
        })
    
    # Recent payments
    recent_payments = db.query(
        Payment,
        School.name.label("school_name"),
        Student.first_name,
        Student.last_name
    ).join(Student, Student.id == Payment.student_id)\
     .join(School, School.id == Student.school_id)\
     .filter(Payment.status == "completed")\
     .order_by(Payment.payment_date.desc())\
     .limit(10).all()
    
    for payment, school_name, first_name, last_name in recent_payments:
        activity.append({
            "type": "payment_made",
            "message": f"Payment of ${payment.amount} from {school_name} ({first_name} {last_name})",
            "timestamp": payment.payment_date,
            "data": {"payment_id": payment.id, "amount": payment.amount}
        })
    
    # Sort by timestamp
    activity.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return activity[:limit]

# ============================================
# SCHOOL MANAGEMENT (SUPER ADMIN)
# ============================================

@router.get("/schools")
async def get_all_schools(
    status: Optional[str] = None,
    search: Optional[str] = None,
    plan: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get all schools with filtering"""
    
    query = db.query(School)
    
    if status:
        query = query.filter(School.status == status)
    
    if plan:
        query = query.filter(School.subscription_plan == plan)
    
    if search:
        query = query.filter(
            or_(
                School.name.ilike(f"%{search}%"),
                School.email.ilike(f"%{search}%"),
                School.address.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    schools = query.order_by(School.created_at.desc()).offset(skip).limit(limit).all()
    
    # Get additional stats for each school
    result = []
    for school in schools:
        student_count = db.query(Student).filter(Student.school_id == school.id).count()
        user_count = db.query(User).filter(User.school_id == school.id).count()
        admin_count = db.query(User).filter(
            User.school_id == school.id,
            User.role.in_([UserRole.ADMIN, UserRole.PROPRIETOR])
        ).count()
        revenue = db.query(Payment).filter(
            Payment.school_id == school.id,
            Payment.status == "completed"
        ).with_entities(func.sum(Payment.amount)).scalar() or 0
        
        # Get proprietor
        proprietor = db.query(User).filter(
            User.school_id == school.id,
            User.role == UserRole.PROPRIETOR
        ).first()
        
        result.append({
            **school.__dict__,
            "student_count": student_count,
            "user_count": user_count,
            "admin_count": admin_count,
            "revenue": float(revenue),
            "proprietor": proprietor.full_name if proprietor else None,
            "proprietor_email": proprietor.email if proprietor else None
        })
    
    return {
        "schools": result,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/schools/{school_id}")
async def get_school_details(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get detailed information about a specific school"""
    
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Get school stats
    student_count = db.query(Student).filter(Student.school_id == school_id).count()
    user_count = db.query(User).filter(User.school_id == school_id).count()
    admin_count = db.query(User).filter(
        User.school_id == school_id,
        User.role.in_([UserRole.ADMIN, UserRole.PROPRIETOR])
    ).count()
    
    total_revenue = db.query(Payment).filter(
        Payment.school_id == school_id,
        Payment.status == "completed"
    ).with_entities(func.sum(Payment.amount)).scalar() or 0
    
    # Recent payments
    recent_payments = db.query(Payment).filter(
        Payment.school_id == school_id,
        Payment.status == "completed"
    ).order_by(Payment.payment_date.desc()).limit(5).all()
    
    # Proprietor
    proprietor = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.PROPRIETOR
    ).first()
    
    # All users
    users = db.query(User).filter(User.school_id == school_id).all()
    
    # Students
    students = db.query(Student).filter(
        Student.school_id == school_id
    ).order_by(Student.created_at.desc()).limit(10).all()
    
    # Installments
    installments = db.query(Installment).filter(
        Installment.school_id == school_id,
        Installment.status == "pending"
    ).count()
    
    # Overdue installments
    overdue = db.query(Installment).filter(
        Installment.school_id == school_id,
        Installment.status == "overdue"
    ).count()
    
    return {
        "school": school,
        "stats": {
            "students": student_count,
            "users": user_count,
            "admins": admin_count,
            "revenue": float(total_revenue),
            "max_students": school.max_students,
            "max_admins": school.max_admins,
            "pending_installments": installments,
            "overdue_installments": overdue
        },
        "proprietor": proprietor,
        "users": users,
        "recent_students": students,
        "recent_payments": recent_payments
    }

@router.put("/schools/{school_id}/status")
async def update_school_status(
    school_id: int,
    status: str,
    reason: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Update school status (approve/suspend)"""
    
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    if status not in [SchoolStatus.ACTIVE, SchoolStatus.SUSPENDED]:
        raise HTTPException(
            status_code=400,
            detail="Status must be 'active' or 'suspended'"
        )
    
    old_status = school.status
    school.status = status
    
    # Log the action
    if status == SchoolStatus.ACTIVE:
        message = f"School {school.name} has been approved and activated"
    else:
        message = f"School {school.name} has been suspended"
        if reason:
            message += f" - Reason: {reason}"
    
    db.commit()
    
    # Get proprietor email
    proprietor = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.PROPRIETOR
    ).first()
    
    # Send email notification
    if proprietor and background_tasks:
        background_tasks.add_task(
            email_service.send_school_approval_email,
            to_email=proprietor.email,
            school_name=school.name,
            status=status
        )
    
    return {
        "message": message,
        "school": school,
        "old_status": old_status,
        "new_status": status,
        "proprietor_email": proprietor.email if proprietor else None
    }

@router.post("/schools/{school_id}/upgrade-plan")
async def upgrade_school_plan(
    school_id: int,
    plan: str,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Manually upgrade a school's subscription plan"""
    
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    if plan not in ["free", "premium", "enterprise"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid plan. Must be 'free', 'premium', or 'enterprise'"
        )
    
    old_plan = school.subscription_plan
    school.subscription_plan = plan
    
    # Update limits based on plan
    if plan == "free":
        school.max_students = 500
        school.max_admins = 3
    elif plan == "premium":
        school.max_students = 5000
        school.max_admins = 10
    elif plan == "enterprise":
        school.max_students = 999999
        school.max_admins = 999
    
    db.commit()
    
    # Get proprietor
    proprietor = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.PROPRIETOR
    ).first()
    
    # Send email notification
    if proprietor and background_tasks:
        background_tasks.add_task(
            email_service.send_email,
            to_email=proprietor.email,
            subject=f"Plan Updated: {school.name}",
            html_content=f"""
            <h2>Plan Update Notification</h2>
            <p>Your school <strong>{school.name}</strong> has been upgraded from <strong>{old_plan}</strong> to <strong>{plan}</strong>.</p>
            <p><strong>New Limits:</strong></p>
            <ul>
                <li>Max Students: {school.max_students}</li>
                <li>Max Admins: {school.max_admins}</li>
            </ul>
            <p>If you have any questions, please contact support.</p>
            """
        )
    
    return {
        "message": f"School {school.name} upgraded from {old_plan} to {plan}",
        "school": school,
        "old_plan": old_plan,
        "new_plan": plan
    }

@router.delete("/schools/{school_id}")
async def delete_school(
    school_id: int,
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete a school (super admin only)"""
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm deletion with confirm=true"
        )
    
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    school_name = school.name
    
    # Delete all associated data (cascade will handle this)
    db.delete(school)
    db.commit()
    
    return {"message": f"School {school_name} has been deleted"}

# ============================================
# ANALYTICS & REPORTS
# ============================================

@router.get("/analytics/revenue")
async def get_revenue_analytics(
    period: str = "month",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get revenue analytics with period breakdown"""
    
    if period == "day":
        days = 30
        format_str = "%Y-%m-%d"
    elif period == "week":
        days = 52
        format_str = "%Y-%W"
    elif period == "year":
        days = 365 * 5
        format_str = "%Y"
    else:  # month
        days = 365
        format_str = "%Y-%m"
    
    start_date = datetime.now() - timedelta(days=days)
    
    # SQLite uses strftime, PostgreSQL uses to_char
    # Check database dialect
    dialect = db.bind.dialect.name
    
    if dialect == "sqlite":
        # SQLite version using strftime
        revenue_data = db.query(
            func.strftime(format_str, Payment.payment_date).label("period"),
            func.sum(Payment.amount).label("total")
        ).filter(
            Payment.payment_date >= start_date,
            Payment.status == "completed"
        ).group_by("period").order_by("period").all()
        
        school_growth = db.query(
            func.strftime(format_str, School.created_at).label("period"),
            func.count(School.id).label("count")
        ).filter(
            School.created_at >= start_date
        ).group_by("period").order_by("period").all()
    else:
        # PostgreSQL version using to_char
        revenue_data = db.query(
            func.to_char(Payment.payment_date, format_str).label("period"),
            func.sum(Payment.amount).label("total")
        ).filter(
            Payment.payment_date >= start_date,
            Payment.status == "completed"
        ).group_by("period").order_by("period").all()
        
        school_growth = db.query(
            func.to_char(School.created_at, format_str).label("period"),
            func.count(School.id).label("count")
        ).filter(
            School.created_at >= start_date
        ).group_by("period").order_by("period").all()
    
    # Payment method breakdown
    payment_methods = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total")
    ).filter(
        Payment.status == "completed"
    ).group_by(Payment.payment_method).all()
    
    return {
        "period": period,
        "revenue": [{"period": r[0], "total": float(r[1])} for r in revenue_data],
        "school_growth": [{"period": s[0], "count": s[1]} for s in school_growth],
        "payment_methods": [
            {"method": m[0], "count": m[1], "total": float(m[2])} 
            for m in payment_methods
        ]
    }

@router.get("/analytics/school-performance")
async def get_school_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get top performing schools"""
    
    # Top schools by revenue
    top_revenue = db.query(
        School.id,
        School.name,
        School.status,
        func.sum(Payment.amount).label("revenue"),
        func.count(Student.id).label("students")
    ).join(Student, Student.school_id == School.id)\
     .join(Payment, Payment.student_id == Student.id)\
     .filter(Payment.status == "completed")\
     .group_by(School.id, School.name, School.status)\
     .order_by(func.sum(Payment.amount).desc())\
     .limit(10).all()
    
    # Top schools by students
    top_students = db.query(
        School.id,
        School.name,
        School.status,
        func.count(Student.id).label("count")
    ).join(Student, Student.school_id == School.id)\
     .group_by(School.id, School.name, School.status)\
     .order_by(func.count(Student.id).desc())\
     .limit(10).all()
    
    # Fastest growing schools (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    fastest_growing = db.query(
        School.id,
        School.name,
        func.count(Student.id).label("new_students")
    ).join(Student, Student.school_id == School.id)\
     .filter(Student.created_at >= thirty_days_ago)\
     .group_by(School.id, School.name)\
     .order_by(func.count(Student.id).desc())\
     .limit(10).all()
    
    return {
        "top_by_revenue": [
            {
                "id": s[0], 
                "name": s[1], 
                "status": s[2],
                "revenue": float(s[3]), 
                "students": s[4]
            } 
            for s in top_revenue
        ],
        "top_by_students": [
            {
                "id": s[0], 
                "name": s[1], 
                "status": s[2],
                "count": s[3]
            } 
            for s in top_students
        ],
        "fastest_growing": [
            {
                "id": s[0], 
                "name": s[1], 
                "new_students": s[2]
            } 
            for s in fastest_growing
        ]
    }

@router.get("/analytics/overdue-payments")
async def get_overdue_payments_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get overdue payments report"""
    
    overdue_installments = db.query(
        Installment,
        Student.first_name,
        Student.last_name,
        Student.admission_number,
        School.name.label("school_name")
    ).join(Student, Student.id == Installment.student_id)\
     .join(School, School.id == Student.school_id)\
     .filter(Installment.status == "overdue")\
     .order_by(Installment.due_date.asc()).all()
    
    total_overdue = db.query(Installment).filter(
        Installment.status == "overdue"
    ).with_entities(
        func.sum(Installment.amount + Installment.late_fee)
    ).scalar() or 0
    
    by_school = db.query(
        School.name,
        func.count(Installment.id).label("count"),
        func.sum(Installment.amount + Installment.late_fee).label("total")
    ).join(Student, Student.school_id == School.id)\
     .join(Installment, Installment.student_id == Student.id)\
     .filter(Installment.status == "overdue")\
     .group_by(School.name).all()
    
    return {
        "total_overdue": float(total_overdue),
        "count": len(overdue_installments),
        "by_school": [
            {"school": s[0], "count": s[1], "total": float(s[2])}
            for s in by_school
        ],
        "installments": overdue_installments
    }

# ============================================
# SYSTEM SETTINGS (SUPER ADMIN)
# ============================================

@router.get("/settings")
async def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get all system settings"""
    
    settings = db.query(SystemSetting).all()
    return {s.key: s.value for s in settings}

@router.post("/settings")
async def update_system_settings(
    settings_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Update system settings"""
    
    for key, value in settings_data.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.now()
        else:
            setting = SystemSetting(
                key=key, 
                value=str(value), 
                description="",
                updated_at=datetime.now()
            )
            db.add(setting)
    
    db.commit()
    return {"message": "Settings updated successfully"}

@router.delete("/settings/{key}")
async def delete_system_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete a system setting"""
    
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    db.delete(setting)
    db.commit()
    
    return {"message": f"Setting '{key}' deleted"}

# ============================================
# USER MANAGEMENT (SUPER ADMIN)
# ============================================

@router.get("/users")
async def get_all_users(
    role: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get all users with filtering"""
    
    query = db.query(User).filter(User.role != UserRole.SUPER_ADMIN)
    
    if role:
        query = query.filter(User.role == role)
    
    if search:
        query = query.filter(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    # Get school names for users
    result = []
    for user in users:
        school_name = None
        if user.school_id:
            school = db.query(School).filter(School.id == user.school_id).first()
            school_name = school.name if school else None
        
        result.append({
            **user.__dict__,
            "school_name": school_name
        })
    
    return {
        "users": result,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.put("/users/{user_id}/status")
async def toggle_user_status(
    user_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Super admin: Enable/disable a user"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify super admin"
        )
    
    user.is_active = is_active
    db.commit()
    
    return {
        "message": f"User {user.full_name} {'activated' if is_active else 'deactivated'}",
        "user": user
    }

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete a user permanently"""
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm deletion with confirm=true"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete super admin"
        )
    
    user_name = user.full_name
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user_name} deleted successfully"}

# ============================================
# SYSTEM HEALTH
# ============================================

@router.get("/health")
async def system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Check system health and performance"""
    
    # Database connection
    db_status = "healthy"
    try:
        db.execute("SELECT 1")
    except:
        db_status = "unhealthy"
    
    # Counts
    total_schools = db.query(School).count()
    total_users = db.query(User).count()
    total_students = db.query(Student).count()
    
    # Performance metrics
    last_hour = datetime.now() - timedelta(hours=1)
    active_users_last_hour = db.query(User).filter(
        User.last_login >= last_hour
    ).count()
    
    payments_last_hour = db.query(Payment).filter(
        Payment.payment_date >= last_hour,
        Payment.status == "completed"
    ).count()
    
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now(),
        "uptime": "unknown",  # Would need to track this
        "stats": {
            "schools": total_schools,
            "users": total_users,
            "students": total_students
        },
        "activity": {
            "active_users_last_hour": active_users_last_hour,
            "payments_last_hour": payments_last_hour
        },
        "version": "1.0.0",
        "environment": "production"
    }

# ============================================
# EXPORT FUNCTIONS
# ============================================

@router.get("/export/schools")
async def export_schools_data(
    format: str = "json",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Export schools data"""
    
    schools = db.query(School).all()
    
    if format == "csv":
        # Return CSV format
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Email", "Phone", "Status", "Plan", "Students", "Created"])
        
        for school in schools:
            student_count = db.query(Student).filter(Student.school_id == school.id).count()
            writer.writerow([
                school.id,
                school.name,
                school.email or "",
                school.phone or "",
                school.status,
                school.subscription_plan,
                student_count,
                school.created_at.strftime("%Y-%m-%d")
            ])
        
        return output.getvalue()
    
    return schools