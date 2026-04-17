from sqlalchemy import Column, Integer, String, Float, Text, TIMESTAMP, Boolean, DateTime , ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

# ------------------------------
# USERS
# ------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    last_login = Column(TIMESTAMP, default=datetime.utcnow)

# ------------------------------
# SOIL HISTORY
# ------------------------------
class SoilHistory(Base):
    __tablename__ = "soil_history"

    id = Column(Integer, primary_key=True, index=True)
    soil_type = Column(String(50))
    confidence = Column(Float)
    image_path = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

# ------------------------------
# TOOLS
# ------------------------------
class Tool(Base):
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    store_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    description = Column(Text)
    image = Column(String)

# ------------------------------
# NOTIFICATIONS
# ------------------------------
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    type = Column(String, default="general")
    click_rate = Column(Integer, default=0)
    views = Column(Integer, default=0)  # add this if you want to track views
    is_read = Column(Boolean, default=False)
    
    # ✅ Timestamp column with timezone support
    created_at = Column(DateTime(timezone=True), server_default=func.now())

 # relationship
    views_rel = relationship("NotificationView", back_populates="notification")


class NotificationView(Base):
    __tablename__ = "notification_views"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="CASCADE"))
    user_email = Column(String, nullable=False)  # store user identity
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())

    notification = relationship("Notification", back_populates="views_rel")

# ------------------------------
# CONTACT MESSAGES
# ------------------------------
class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    subject = Column(String)
    message = Column(Text, nullable=False)

    is_read = Column(Boolean, default=False)
    is_replied = Column(Boolean, default=False)

    reply = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MyGarden(Base):
    __tablename__ = "my_garden"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String)

    crop = Column(String)   # ✅ FIXED NAME
    image = Column(String)

    planted_at = Column(DateTime, default=datetime.utcnow)

    growth_days = Column(Integer, default=30)       # day stage (1,2,3...)

class DiseaseHistory(Base):
    __tablename__ = "disease_history"

    id = Column(Integer, primary_key=True, index=True)
    result = Column(String)
    image = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)