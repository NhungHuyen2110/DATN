"""Run ONCE from backend folder: python init_password_reset_table.py"""
from app.core.database import get_db
from app.routers.password_reset import PasswordResetToken

session_generator = get_db()
db = next(session_generator)
try:
    PasswordResetToken.__table__.create(bind=db.get_bind(), checkfirst=True)
    print("PASSWORD RESET TABLE READY")
finally:
    session_generator.close()
