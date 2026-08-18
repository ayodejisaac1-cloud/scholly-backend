from app.database import SessionLocal, engine
from app.models import Base, User, UserRole
from app.auth import get_password_hash

def init_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created!")
    
    db = SessionLocal()
    try:
        # Create Super Admin
        super_admin = db.query(User).filter(User.username == "superadmin").first()
        if not super_admin:
            super_admin = User(
                email="superadmin@scholly.com",
                username="superadmin",
                hashed_password=get_password_hash("superadmin123"),
                full_name="System Administrator",
                role=UserRole.SUPER_ADMIN,
                is_active=True
            )
            db.add(super_admin)
            print("✅ Super Admin created: superadmin / superadmin123")
        else:
            print("ℹ️ Super Admin already exists")
        
        # Create Admin
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                email="admin@scholly.com",
                username="admin",
                hashed_password=get_password_hash("admin123"),
                full_name="School Administrator",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin)
            print("✅ Admin created: admin / admin123")
        else:
            print("ℹ️ Admin already exists")
        
        db.commit()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()