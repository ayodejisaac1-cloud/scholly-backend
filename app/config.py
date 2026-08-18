from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email Settings
    SMTP_EMAIL: str
    SMTP_PASSWORD: str
    FRONTEND_URL: str = "http://localhost:5173"
    SUPER_ADMIN_EMAIL: str = "admin@scholly.com"
    
    # Paystack Settings
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    
    class Config:
        env_file = ".env"
        # Allow extra fields in .env file
        extra = "ignore"

settings = Settings()