from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta
from typing import Optional
from ..database import get_db
from ..models import Payment, Student, Installment, Expense, User, School
from ..dependencies import get_current_user, require_proprietor, require_super_admin
from ..models import UserRole

router = APIRouter(prefix="/api/reports", tags=["reports"])  # No trailing slash

@router.get("/income")
async def get_income_report(
    term: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get income report"""
    query = db.query(Payment).filter(Payment.status == "completed")
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        query = query.filter(Payment.school_id == current_user.school_id)
    
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    
    total_collected = query.with_entities(func.sum(Payment.amount)).scalar() or 0
    
    # By class
    by_class = db.query(
        Student.class_name,
        func.sum(Payment.amount).label("total")
    ).join(Payment, Payment.student_id == Student.id)\
     .filter(Payment.status == "completed")
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            by_class = by_class.filter(Student.school_id == current_user.school_id)
    
    if term:
        by_class = by_class.filter(Student.term == term)
    if start_date:
        by_class = by_class.filter(Payment.payment_date >= start_date)
    if end_date:
        by_class = by_class.filter(Payment.payment_date <= end_date)
    
    by_class = by_class.group_by(Student.class_name).all()
    
    # Payment methods
    by_method = db.query(
        Payment.payment_method,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total")
    ).filter(Payment.status == "completed")
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            by_method = by_method.filter(Payment.school_id == current_user.school_id)
    
    if start_date:
        by_method = by_method.filter(Payment.payment_date >= start_date)
    if end_date:
        by_method = by_method.filter(Payment.payment_date <= end_date)
    
    by_method = by_method.group_by(Payment.payment_method).all()
    
    return {
        "total_collected": total_collected,
        "by_term": {term: total_collected},
        "by_class": [{"class": c[0], "total": c[1]} for c in by_class],
        "payment_methods": [{"method": m[0], "count": m[1], "total": m[2]} for m in by_method],
        "period": f"{start_date or 'start'} to {end_date or 'today'}"
    }

@router.get("/profit-loss")
async def get_profit_loss_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Get profit/loss report"""
    # Calculate total income
    income_query = db.query(Payment).filter(Payment.status == "completed")
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            income_query = income_query.filter(Payment.school_id == current_user.school_id)
    
    if start_date:
        income_query = income_query.filter(Payment.payment_date >= start_date)
    if end_date:
        income_query = income_query.filter(Payment.payment_date <= end_date)
    total_income = income_query.with_entities(func.sum(Payment.amount)).scalar() or 0
    
    # Income by term
    income_by_term = db.query(
        Student.term,
        func.sum(Payment.amount).label("total")
    ).join(Payment, Payment.student_id == Student.id)\
     .filter(Payment.status == "completed")
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            income_by_term = income_by_term.filter(Student.school_id == current_user.school_id)
    
    if start_date:
        income_by_term = income_by_term.filter(Payment.payment_date >= start_date)
    if end_date:
        income_by_term = income_by_term.filter(Payment.payment_date <= end_date)
    income_by_term = income_by_term.group_by(Student.term).all()
    
    # Calculate total expenses
    expense_query = db.query(Expense)
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            expense_query = expense_query.filter(Expense.school_id == current_user.school_id)
    
    if start_date:
        expense_query = expense_query.filter(Expense.expense_date >= start_date)
    if end_date:
        expense_query = expense_query.filter(Expense.expense_date <= end_date)
    total_expenses = expense_query.with_entities(func.sum(Expense.amount)).scalar() or 0
    
    # Expenses by category
    expenses_by_category = db.query(
        Expense.category,
        func.sum(Expense.amount).label("total")
    )
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            expenses_by_category = expenses_by_category.filter(Expense.school_id == current_user.school_id)
    
    if start_date:
        expenses_by_category = expenses_by_category.filter(Expense.expense_date >= start_date)
    if end_date:
        expenses_by_category = expenses_by_category.filter(Expense.expense_date <= end_date)
    expenses_by_category = expenses_by_category.group_by(Expense.category).all()
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
        "income_by_term": [{"term": t[0], "total": t[1]} for t in income_by_term],
        "expenses_by_category": [{"category": c[0], "total": c[1]} for c in expenses_by_category]
    }

@router.get("/financial-summary")
async def get_financial_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get financial summary for dashboard"""
    # Total students
    student_query = db.query(Student).filter(Student.is_active == True)
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            student_query = student_query.filter(Student.school_id == current_user.school_id)
    total_students = student_query.count()
    
    # Total revenue
    revenue_query = db.query(Payment).filter(Payment.status == "completed")
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            revenue_query = revenue_query.filter(Payment.school_id == current_user.school_id)
    total_revenue = revenue_query.with_entities(func.sum(Payment.amount)).scalar() or 0
    
    # Overdue payments
    overdue_query = db.query(Installment).filter(Installment.status == "overdue")
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            overdue_query = overdue_query.filter(Installment.school_id == current_user.school_id)
    overdue = overdue_query.with_entities(func.sum(Installment.amount + Installment.late_fee)).scalar() or 0
    
    # Outstanding balance
    balance_query = db.query(Student)
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            balance_query = balance_query.filter(Student.school_id == current_user.school_id)
    outstanding = balance_query.with_entities(func.sum(Student.balance)).scalar() or 0
    
    # Recent payments
    recent_query = db.query(Payment).filter(Payment.status == "completed")
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.school_id:
            recent_query = recent_query.filter(Payment.school_id == current_user.school_id)
    recent_payments = recent_query.order_by(Payment.payment_date.desc()).limit(5).all()
    
    return {
        "total_students": total_students,
        "total_revenue": total_revenue,
        "overdue_payments": overdue,
        "outstanding_balance": outstanding,
        "recent_payments": recent_payments
    }