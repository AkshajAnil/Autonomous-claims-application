from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash

print("Testing DB connection...")
db = SessionLocal()
try:
    user = User(username="test_db_user", password_hash=get_password_hash("test"))
    db.add(user)
    db.commit()
    print("User created successfully.")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
