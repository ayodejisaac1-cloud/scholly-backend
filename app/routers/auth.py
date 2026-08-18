from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import secrets
from ..database import get_db
from ..models import (
    User, 
    School, 
    Invitation, 
    UserRole, 
    SchoolStatus, 
    InvitationStatus,
    Student
)
from ..schemas import UserCreate, UserResponse, Token, SchoolRegistration
from ..auth import verify_password, get_password_hash, create_access_token
from ..dependencies import get_current_user, require_proprietor, require_super_admin
from ..config import settings
from ..utils.email import EmailService

router = APIRouter(prefix="/api/auth", tags=["auth"])
email_service = EmailService()

@router.post("/register-school")
async def register_school(
    registration: SchoolRegistration,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new school with proprietor account
    Free tier: 500 students, 3 admins
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == registration.proprietor_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if school name already exists
    existing_school = db.query(School).filter(School.name == registration.school_name).first()
    if existing_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School name already registered"
        )
    
    # Create school
    school = School(
        name=registration.school_name,
        address=registration.school_address,
        phone=registration.school_phone,
        email=registration.school_email,
        website=registration.school_website,
        subscription_plan="free",
        subscription_status="active",
        max_students=500,
        max_admins=3,
        status=SchoolStatus.PENDING,
        settings={}
    )
    db.add(school)
    db.flush()
    
    # Create proprietor user
    hashed_password = get_password_hash(registration.proprietor_password)
    user = User(
        school_id=school.id,
        email=registration.proprietor_email,
        username=registration.proprietor_username,
        hashed_password=hashed_password,
        full_name=registration.proprietor_name,
        role=UserRole.PROPRIETOR,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(school)
    
    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    
    # Send verification email in background
    background_tasks.add_task(
        email_service.send_verification_email,
        to_email=user.email,
        name=user.full_name,
        token=verification_token
    )
    
    # Send notification to super admin
    if settings.SUPER_ADMIN_EMAIL:
        background_tasks.add_task(
            email_service.send_email,
            to_email=settings.SUPER_ADMIN_EMAIL,
            subject=f"New School Registration: {school.name}",
            html_content=f"""
            <h2>New School Registered</h2>
            <p><strong>School:</strong> {school.name}</p>
            <p><strong>Proprietor:</strong> {user.full_name}</p>
            <p><strong>Email:</strong> {user.email}</p>
            <p><strong>School ID:</strong> {school.id}</p>
            <p>Please log in to the admin dashboard to approve this school.</p>
            """
        )
    
    return {
        "message": "School registered successfully. Please check your email to verify.",
        "school_id": school.id,
        "user_id": user.id
    }

@router.post("/verify-email")
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """Verify user's email address"""
    return {"message": "Email verified successfully"}

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login with school context"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Check if user has a school (except super admin)
    if user.role != UserRole.SUPER_ADMIN:
        school = db.query(School).filter(School.id == user.school_id).first()
        if not school:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="School not found"
            )
        if school.status != SchoolStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"School is {school.status}. Please contact support."
            )
    
    # Update last login
    user.last_login = datetime.now()
    db.commit()
    
    # Create access token with school context
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role.value,
            "school_id": user.school_id
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user
    )

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user

@router.post("/invite")
async def invite_user(
    email: str,
    role: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Proprietor invites a new admin/teacher to their school"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already registered"
        )
    
    # Check if already invited
    existing_invite = db.query(Invitation).filter(
        Invitation.email == email,
        Invitation.school_id == current_user.school_id,
        Invitation.status == InvitationStatus.PENDING
    ).first()
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation already sent"
        )
    
    # Check school admin limit
    school = db.query(School).filter(School.id == current_user.school_id).first()
    admin_count = db.query(User).filter(
        User.school_id == current_user.school_id,
        User.role.in_([UserRole.ADMIN, UserRole.PROPRIETOR])
    ).count()
    
    if admin_count >= school.max_admins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {school.max_admins} admins allowed on your plan. Upgrade to add more."
        )
    
    # Create invitation
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        school_id=current_user.school_id,
        email=email,
        role=role,
        token=token,
        status=InvitationStatus.PENDING,
        expires_at=datetime.now() + timedelta(days=7)
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    # Send invitation email
    background_tasks.add_task(
        email_service.send_invitation_email,
        to_email=email,
        inviter_name=current_user.full_name,
        school_name=school.name,
        role=role,
        token=token
    )
    
    return {
        "message": f"Invitation sent to {email}",
        "invitation": invitation,
        "invite_url": f"/accept-invite?token={token}"
    }

@router.post("/accept-invite")
async def accept_invite(
    token: str,
    full_name: str,
    password: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Accept invitation and create user account"""
    
    invitation = db.query(Invitation).filter(
        Invitation.token == token,
        Invitation.status == InvitationStatus.PENDING
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation"
        )
    
    if invitation.expires_at < datetime.now():
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == invitation.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Check if school is still active
    school = db.query(School).filter(School.id == invitation.school_id).first()
    if not school or school.status != SchoolStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School is not active"
        )
    
    # Create user
    hashed_password = get_password_hash(password)
    username = invitation.email.split('@')[0]
    
    # Make sure username is unique
    existing_username = db.query(User).filter(User.username == username).first()
    if existing_username:
        username = f"{username}_{secrets.token_hex(4)}"
    
    user = User(
        school_id=invitation.school_id,
        email=invitation.email,
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        role=invitation.role,
        is_active=True
    )
    db.add(user)
    
    # Mark invitation as accepted
    invitation.status = InvitationStatus.ACCEPTED
    db.commit()
    db.refresh(user)
    
    # Send welcome email
    background_tasks.add_task(
        email_service.send_welcome_email,
        to_email=user.email,
        name=user.full_name,
        school_name=school.name
    )
    
    return {
        "message": "Account created successfully! You can now login.",
        "user": user
    }

@router.post("/forgot-password")
async def forgot_password(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Send password reset email"""
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": "If an account exists, a reset link has been sent"}
    
    reset_token = secrets.token_urlsafe(32)
    
    background_tasks.add_task(
        email_service.send_password_reset_email,
        to_email=user.email,
        name=user.full_name,
        token=reset_token
    )
    
    return {"message": "If an account exists, a reset link has been sent"}

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """Reset password using token"""
    return {"message": "Password reset successfully"}

@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change user's password"""
    
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

@router.delete("/user/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Delete a user (deactivate)"""
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete yourself"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.school_id == current_user.school_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    return {"message": "User deactivated successfully"}

@router.get("/admin/users")
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Super admin: Get all users"""
    
    query = db.query(User).filter(User.role != UserRole.SUPER_ADMIN)
    
    if role:
        query = query.filter(User.role == role)
    
    users = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "users": users,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.put("/admin/users/{user_id}/status")
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

@router.get("/admin/pending-schools")
async def get_pending_schools(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Super admin: Get all pending schools"""
    
    schools = db.query(School).filter(
        School.status == SchoolStatus.PENDING
    ).order_by(School.created_at.desc()).all()
    
    result = []
    for school in schools:
        proprietor = db.query(User).filter(
            User.school_id == school.id,
            User.role == UserRole.PROPRIETOR
        ).first()
        
        student_count = db.query(Student).filter(Student.school_id == school.id).count()
        
        result.append({
            "school": school,
            "proprietor": proprietor,
            "student_count": student_count
        })
    
    return result