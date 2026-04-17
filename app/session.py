from sqlalchemy.orm import Session  # Import Session
from app.models import User  # Import User model

def create_user_session(request, user):
    request.session["user_id"] = user.id
    request.session["username"] = user.full_name  # optional for display
    request.session["user_email"] = user.email  # store email for profile queries

def get_current_user(request, db: Session):
    email = request.session.get("user_email")
    if email:
        return db.query(User).filter(User.email == email).first()
    return None

def clear_user_session(request):
    request.session.clear()