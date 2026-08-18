from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from ..database import get_db
from ..auth import decode_token
from ..models import User, UserRole, School, SchoolStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    return user

def get_current_school(current_user: User = Depends(get_current_user)):
    """Get the current user's school with validation"""
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    
    if current_user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no school associated"
        )
    
    return current_user.school_id

def require_school_access(current_user: User = Depends(get_current_user)):
    """Verify user has access to their school and school is active"""
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    
    if current_user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No school access"
        )
    
    return current_user.school_id

def require_role(required_role: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)):
        # ✅ Super Admin can do anything
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user
        
        # ✅ Proprietor can access ADMIN-level endpoints
        if current_user.role == UserRole.PROPRIETOR and required_role == UserRole.ADMIN:
            return current_user
        
        # ✅ Check exact role match
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role. Current role: {current_user.role}"
            )
        return current_user
    return role_checker

def require_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user

def require_proprietor(current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.PROPRIETOR, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Proprietor access required"
        )
    return current_user