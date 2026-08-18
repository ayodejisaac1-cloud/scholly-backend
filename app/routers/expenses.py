from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date
from ..database import get_db
from ..models import Expense, User, School
from ..schemas import ExpenseCreate, ExpenseResponse
from ..dependencies import require_proprietor, get_current_user, require_super_admin
from ..models import UserRole

router = APIRouter(prefix="/api/expenses", tags=["expenses"])

# ============================================
# GET ENDPOINTS
# ============================================

@router.get("", response_model=List[ExpenseResponse])  # ✅ No trailing slash
async def get_expenses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all expenses with filters"""
    query = db.query(Expense)
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        query = query.filter(Expense.school_id == current_user.school_id)
    
    if category:
        query = query.filter(Expense.category == category)
    if start_date:
        query = query.filter(Expense.expense_date >= start_date)
    if end_date:
        query = query.filter(Expense.expense_date <= end_date)
    
    expenses = query.order_by(Expense.expense_date.desc()).offset(skip).limit(limit).all()
    return expenses

@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific expense"""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if expense.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return expense

@router.get("/summary")
async def get_expense_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get expense summary"""
    query = db.query(Expense)
    
    # Filter by school
    if current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.school_id:
            raise HTTPException(status_code=403, detail="No school access")
        query = query.filter(Expense.school_id == current_user.school_id)
    
    total = query.with_entities(func.sum(Expense.amount)).scalar() or 0
    by_category = query.with_entities(
        Expense.category,
        func.sum(Expense.amount).label("total")
    ).group_by(Expense.category).all()
    
    return {
        "total": total,
        "by_category": [{"category": c[0], "total": c[1]} for c in by_category]
    }

# ============================================
# POST ENDPOINTS
# ============================================

@router.post("", response_model=ExpenseResponse)  # ✅ No trailing slash
async def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Create a new expense"""
    # Set school_id
    school_id = current_user.school_id
    if current_user.role == UserRole.SUPER_ADMIN:
        school = db.query(School).first()
        if school:
            school_id = school.id
        else:
            raise HTTPException(status_code=400, detail="No school available")
    
    db_expense = Expense(
        **expense.model_dump(),
        school_id=school_id,
        created_by=current_user.id
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@router.post("/manual", response_model=ExpenseResponse)
async def create_manual_expense(
    expense_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Record a manual expense with additional fields"""
    # Set school_id
    school_id = current_user.school_id
    if current_user.role == UserRole.SUPER_ADMIN:
        school = db.query(School).first()
        if school:
            school_id = school.id
        else:
            raise HTTPException(status_code=400, detail="No school available")
    
    # Validate required fields
    required_fields = ['description', 'category', 'amount', 'expense_date']
    for field in required_fields:
        if field not in expense_data:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field}"
            )
    
    # Parse expense date
    expense_date = datetime.now().date()
    if expense_data.get("expense_date"):
        try:
            expense_date = datetime.fromisoformat(expense_data["expense_date"]).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid expense date format")
    
    db_expense = Expense(
        description=expense_data["description"],
        category=expense_data["category"],
        amount=float(expense_data["amount"]),
        expense_date=expense_date,
        receipt_url=expense_data.get("receipt_url"),
        notes=expense_data.get("notes"),
        school_id=school_id,
        created_by=current_user.id
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

# ============================================
# PUT ENDPOINTS
# ============================================

@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    expense_update: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Update an expense"""
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if db_expense.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    for key, value in expense_update.model_dump(exclude_unset=True).items():
        setattr(db_expense, key, value)
    
    db.commit()
    db.refresh(db_expense)
    return db_expense

# ============================================
# DELETE ENDPOINTS
# ============================================

@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Delete an expense"""
    db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Check school access
    if current_user.role != UserRole.SUPER_ADMIN:
        if db_expense.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(db_expense)
    db.commit()
    return {"message": "Expense deleted successfully"}

print("✅ Expenses router loaded successfully!")