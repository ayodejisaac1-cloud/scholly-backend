from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import Optional, List
from .models import UserRole, ExpenseCategory

# ============================================
# AUTH SCHEMAS
# ============================================

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    role: UserRole = UserRole.ADMIN

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# ============================================
# SCHOOL SCHEMAS
# ============================================

class SchoolRegistration(BaseModel):
    school_name: str
    school_address: Optional[str] = None
    school_phone: Optional[str] = None
    school_email: Optional[EmailStr] = None
    school_website: Optional[str] = None
    
    proprietor_name: str
    proprietor_email: EmailStr
    proprietor_username: str
    proprietor_password: str
    
    terms_accepted: bool

class SchoolResponse(BaseModel):
    id: int
    name: str
    address: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    website: Optional[str]
    subscription_plan: str
    max_students: int
    max_admins: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None

# ============================================
# INVITATION SCHEMAS
# ============================================

class InvitationCreate(BaseModel):
    email: EmailStr
    role: str  # admin, teacher

class InvitationResponse(BaseModel):
    id: int
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

class AcceptInvitation(BaseModel):
    token: str
    full_name: str
    password: str

# ============================================
# STUDENT SCHEMAS
# ============================================

class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    class_name: str
    term: str
    admission_number: str
    total_fees: float

class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    class_name: Optional[str] = None
    term: Optional[str] = None
    total_fees: Optional[float] = None
    is_active: Optional[bool] = None

class StudentResponse(BaseModel):
    id: int
    school_id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    class_name: str
    term: str
    admission_number: str
    total_fees: float
    balance: float
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================
# INSTALLMENT SCHEMAS
# ============================================

class InstallmentCreate(BaseModel):
    installment_number: int
    due_date: date
    amount: float

class InstallmentUpdate(BaseModel):
    due_date: Optional[date] = None
    amount: Optional[float] = None
    status: Optional[str] = None

class InstallmentResponse(BaseModel):
    id: int
    student_id: int
    installment_number: int
    due_date: date
    amount: float
    status: str
    late_fee: float
    paid_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# ============================================
# PAYMENT SCHEMAS
# ============================================

class PaymentCreate(BaseModel):
    student_id: int
    installment_id: Optional[int] = None
    amount: float
    payment_method: str

class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None
    payment_date: Optional[datetime] = None

class PaymentResponse(BaseModel):
    id: int
    school_id: int
    student_id: int
    installment_id: Optional[int]
    amount: float
    payment_date: datetime
    payment_method: str
    reference: str
    status: str
    
    class Config:
        from_attributes = True

class PaymentFilter(BaseModel):
    student_id: Optional[int] = None
    installment_id: Optional[int] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

# ============================================
# EXPENSE SCHEMAS
# ============================================

class ExpenseCreate(BaseModel):
    description: str
    category: ExpenseCategory
    amount: float
    expense_date: date
    receipt_url: Optional[str] = None
    notes: Optional[str] = None

class ExpenseResponse(BaseModel):
    id: int
    school_id: int
    description: str
    category: ExpenseCategory
    amount: float
    expense_date: date
    receipt_url: Optional[str]
    notes: Optional[str]
    created_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================
# REPORT SCHEMAS
# ============================================

class StudentFinancialStatus(BaseModel):
    student: StudentResponse
    total_fees: float
    total_paid: float
    balance: float
    overdue_amount: float
    installments: List[InstallmentResponse]

class IncomeReport(BaseModel):
    total_collected: float
    by_term: dict
    by_class: dict
    payment_methods: dict
    period: str

class ProfitLossReport(BaseModel):
    total_income: float
    total_expenses: float
    net_profit: float
    income_by_category: dict
    expenses_by_category: dict

# ============================================
# PAYSTACK SCHEMAS
# ============================================

class PaystackInitializeRequest(BaseModel):
    email: str
    amount: float
    student_id: int
    installment_id: Optional[int] = None
    callback_url: str

class PaystackInitializeResponse(BaseModel):
    authorization_url: str
    reference: str

class PaystackWebhookPayload(BaseModel):
    event: str
    data: dict

# ============================================
# ADMIN SCHEMAS
# ============================================

class SchoolStats(BaseModel):
    total_students: int
    total_teachers: Optional[int] = 0
    total_payments: int
    total_revenue: float
    pending_payments: int
    overdue_payments: int

class RevenueReport(BaseModel):
    total_revenue: float
    by_month: dict
    by_year: dict
    by_school: dict
    by_payment_method: dict

class SystemStats(BaseModel):
    total_schools: int
    total_users: int
    total_students: int
    total_payments: int
    total_revenue: float
    active_schools: int
    pending_schools: int
    suspended_schools: int

# ============================================
# BULK OPERATIONS SCHEMAS
# ============================================

class BulkStudentCreate(BaseModel):
    students: List[StudentCreate]

class BulkPaymentCreate(BaseModel):
    payments: List[PaymentCreate]

class BulkOperationResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[dict]
    errors: List[dict]

# ============================================
# DASHBOARD SCHEMAS
# ============================================

class DashboardStats(BaseModel):
    total_students: int
    total_revenue: float
    overdue_payments: float
    outstanding_balance: float
    recent_payments: List[PaymentResponse]

class DashboardQuickActions(BaseModel):
    add_student: bool
    record_payment: bool
    add_expense: bool
    view_reports: bool

# ============================================
# NOTIFICATION SCHEMAS
# ============================================

class EmailNotification(BaseModel):
    to_email: str
    subject: str
    html_content: str
    text_content: Optional[str] = None

class InviteNotification(BaseModel):
    email: str
    inviter_name: str
    school_name: str
    role: str
    token: str

class PasswordResetNotification(BaseModel):
    email: str
    name: str
    token: str

# ============================================
# SYSTEM SETTINGS SCHEMAS
# ============================================

class SystemSettingCreate(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class SystemSettingResponse(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str]
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# ============================================
# SEARCH AND FILTER SCHEMAS
# ============================================

class SearchParams(BaseModel):
    query: Optional[str] = None
    class_name: Optional[str] = None
    term: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    page: int = 1
    limit: int = 20
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "desc"

class SearchResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    limit: int
    total_pages: int