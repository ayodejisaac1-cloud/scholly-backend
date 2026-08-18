from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, students, payments, expenses, reports, settings as settings_router, admin, schools
from .database import engine, Base
from .config import settings
import logging

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Scholly - School Accounting System",
    description="A comprehensive school accounting system with role-based access",
    version="1.0.0"
)

# Disable automatic trailing slash redirect
# This prevents FastAPI from automatically adding/removing trailing slashes
app.router.redirect_slashes = False

# CORS middleware - Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://scholly.vercel.app",
        "https://your-frontend-domain.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# INCLUDE ALL ROUTERS
# ============================================

# Auth routes - login, register, etc.
app.include_router(auth.router)

# Student routes - CRUD operations for students
app.include_router(students.router)

# Payment routes - Record and manage payments
app.include_router(payments.router)

# Expense routes - Record and manage expenses
app.include_router(expenses.router)

# Report routes - Financial reports and analytics
app.include_router(reports.router)

# Settings routes - System settings
app.include_router(settings_router.router)

# Admin routes - Super admin functionality
app.include_router(admin.router)

# School routes - School management and team management
app.include_router(schools.router)

# ============================================
# DEBUG: PRINT ALL REGISTERED ROUTES
# ============================================

print("\n" + "="*60)
print("📋 REGISTERED ROUTES:")
print("="*60)
for route in app.routes:
    if hasattr(route, 'path'):
        methods = getattr(route, 'methods', set())
        methods_str = ", ".join(methods) if methods else "GET"
        print(f"  {methods_str:10} {route.path}")
print("="*60 + "\n")

print("✅ All routers loaded successfully!")
print(f"🚀 Server running on: http://localhost:8000")
print(f"📚 API Docs: http://localhost:8000/docs")
print(f"📖 ReDoc: http://localhost:8000/redoc")

# ============================================
# ROOT AND HEALTH ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Welcome to Scholly API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z"
    }

# ============================================
# OPTIONAL: ERROR HANDLERS
# ============================================

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 error handler"""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "The requested endpoint was not found",
            "path": request.url.path,
            "method": request.method
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Custom 500 error handler"""
    logger.error(f"Internal Server Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "path": request.url.path
        }
    )