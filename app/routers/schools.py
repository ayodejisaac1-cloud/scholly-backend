from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
from ..database import get_db
from ..models import (
    School, 
    User, 
    UserRole, 
    SchoolStatus, 
    Invitation, 
    InvitationStatus,
    Student,
    Payment
)
from ..schemas import (
    SchoolResponse, 
    SchoolUpdate, 
    InvitationCreate, 
    InvitationResponse,
    UserResponse  # Add this
)
from ..dependencies import get_current_user, require_proprietor, require_super_admin, get_current_school
from ..auth import get_password_hash
from ..config import settings
from ..utils.email import EmailService

router = APIRouter(prefix="/api/schools", tags=["schools"])
email_service = EmailService()

@router.get("/me", response_model=SchoolResponse)
async def get_my_school(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's school details"""
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin doesn't have a school"
        )
    
    if not current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no school associated"
        )
    
    school = db.query(School).filter(School.id == current_user.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    return school

@router.put("/me", response_model=SchoolResponse)
async def update_my_school(
    school_update: SchoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Update current user's school details"""
    school = db.query(School).filter(School.id == current_user.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    update_data = school_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(school, key, value)
    
    db.commit()
    db.refresh(school)
    return school

@router.get("/team", response_model=List[UserResponse])
async def get_team_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Get all team members of the school"""
    users = db.query(User).filter(
        User.school_id == current_user.school_id,
        User.is_active == True
    ).all()
    return users

@router.post("/invite")
async def invite_team_member(
    invite: InvitationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Invite a new team member to the school"""
    
    existing_user = db.query(User).filter(User.email == invite.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already registered"
        )
    
    existing_invite = db.query(Invitation).filter(
        Invitation.email == invite.email,
        Invitation.school_id == current_user.school_id,
        Invitation.status == InvitationStatus.PENDING
    ).first()
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation already sent to this email"
        )
    
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
    
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        school_id=current_user.school_id,
        email=invite.email,
        role=invite.role,
        token=token,
        status=InvitationStatus.PENDING,
        expires_at=datetime.now() + timedelta(days=7)
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    background_tasks.add_task(
        email_service.send_invitation_email,
        to_email=invite.email,
        inviter_name=current_user.full_name,
        school_name=school.name,
        role=invite.role,
        token=token
    )
    
    return {
        "message": f"Invitation sent to {invite.email}",
        "invitation": invitation,
        "invite_url": f"/accept-invite?token={token}"
    }

@router.get("/invitations", response_model=List[InvitationResponse])
async def get_invitations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Get all pending invitations for the school"""
    invitations = db.query(Invitation).filter(
        Invitation.school_id == current_user.school_id,
        Invitation.status == InvitationStatus.PENDING
    ).all()
    return invitations

@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Cancel a pending invitation"""
    invitation = db.query(Invitation).filter(
        Invitation.id == invitation_id,
        Invitation.school_id == current_user.school_id,
        Invitation.status == InvitationStatus.PENDING
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    db.delete(invitation)
    db.commit()
    
    return {"message": "Invitation cancelled"}

@router.delete("/team/{user_id}")
async def remove_team_member(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Remove a team member from the school"""
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove yourself"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.school_id == current_user.school_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    return {"message": "Team member removed successfully"}

@router.post("/accept-invite")
async def accept_invitation(
    token: str,
    full_name: str,
    password: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Accept an invitation and create user account"""
    
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
    
    existing_user = db.query(User).filter(User.email == invitation.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    school = db.query(School).filter(School.id == invitation.school_id).first()
    if not school or school.status != SchoolStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School is not active"
        )
    
    hashed_password = get_password_hash(password)
    username = invitation.email.split('@')[0]
    
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
    
    invitation.status = InvitationStatus.ACCEPTED
    db.commit()
    db.refresh(user)
    
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

@router.get("/admin/all")
async def get_all_schools(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Super admin: Get all schools"""
    schools = db.query(School).offset(skip).limit(limit).all()
    total = db.query(School).count()
    
    return {
        "schools": schools,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.put("/admin/{school_id}/status")
async def update_school_status(
    school_id: int,
    status: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Super admin: Approve or suspend a school"""
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
    db.commit()
    
    proprietor = db.query(User).filter(
        User.school_id == school_id,
        User.role == UserRole.PROPRIETOR
    ).first()
    
    if proprietor and background_tasks:
        background_tasks.add_task(
            email_service.send_school_approval_email,
            to_email=proprietor.email,
            school_name=school.name,
            status=status
        )
    
    return {
        "message": f"School {school.name} is now {status}",
        "school": school,
        "old_status": old_status,
        "new_status": status
    }

@router.get("/admin/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Super admin: Get system-wide statistics"""
    total_schools = db.query(School).count()
    total_users = db.query(User).filter(User.role != UserRole.SUPER_ADMIN).count()
    total_students = db.query(Student).count()
    total_payments = db.query(Payment).filter(Payment.status == "completed").count()
    total_revenue = db.query(Payment).filter(Payment.status == "completed").with_entities(func.sum(Payment.amount)).scalar() or 0
    
    schools_by_status = db.query(School.status, func.count(School.id)).group_by(School.status).all()
    
    return {
        "total_schools": total_schools,
        "total_users": total_users,
        "total_students": total_students,
        "total_payments": total_payments,
        "total_revenue": total_revenue,
        "schools_by_status": [{"status": s[0], "count": s[1]} for s in schools_by_status]
    }