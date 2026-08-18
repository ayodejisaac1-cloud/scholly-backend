from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SystemSetting, User, School
from ..dependencies import require_proprietor, require_super_admin, get_current_user
from ..models import UserRole
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/settings", tags=["settings"])  # No trailing slash

class SettingUpdate(BaseModel):
    value: str

@router.get("/")
async def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all settings"""
    settings = db.query(SystemSetting).all()
    return {s.key: s.value for s in settings}

@router.get("/{key}")
async def get_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific setting"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        return {"value": None}
    return {"value": setting.value}

@router.post("/{key}")
async def update_setting(
    key: str,
    data: SettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Update a setting"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting:
        setting.value = data.value
    else:
        setting = SystemSetting(key=key, value=data.value)
        db.add(setting)
    
    db.commit()
    return {"message": "Setting updated successfully"}

@router.delete("/{key}")
async def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_proprietor)
):
    """Delete a setting"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting:
        db.delete(setting)
        db.commit()
    return {"message": "Setting deleted"}