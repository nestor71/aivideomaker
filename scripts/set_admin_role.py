#!/usr/bin/env python3
"""
Script to set admin role for users with admin email addresses.
This script updates users in the database to have admin role if their email 
is in the ADMIN_EMAIL_ADDRESSES configuration.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database.base import SessionLocal
from app.database.models import User, UserRole
from app.core.config import settings


def set_admin_roles():
    """Set admin role for users with admin email addresses."""
    db = SessionLocal()
    
    try:
        admin_emails = settings.ADMIN_EMAIL_ADDRESSES
        print(f"Admin emails configured: {admin_emails}")
        
        if not admin_emails:
            print("No admin email addresses configured in ADMIN_EMAIL_ADDRESSES")
            return
        
        # Find users with admin emails
        admin_users = db.query(User).filter(User.email.in_(admin_emails)).all()
        
        if not admin_users:
            print("No users found with admin email addresses")
            print("Make sure the users are registered first:")
            for email in admin_emails:
                print(f"  - {email}")
            return
        
        updated_count = 0
        for user in admin_users:
            if user.role != UserRole.ADMIN:
                print(f"Setting admin role for user: {user.email}")
                user.role = UserRole.ADMIN
                updated_count += 1
            else:
                print(f"User {user.email} already has admin role")
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Successfully updated {updated_count} user(s) to admin role")
        else:
            print("\n✅ All admin users already have correct role")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Setting admin roles for configured admin emails...")
    set_admin_roles()
    print("✅ Done!")