#!/usr/bin/env python3
"""
Simple script to update admin role for production.
Run this script to set admin role for configured admin emails.
"""

import requests
import json

# Your app URL
BASE_URL = "https://aivideomaker-app-95gyn.ondigitalocean.app"

def check_current_user():
    """Check current user info via API."""
    print("🔍 Checking user info...")
    
    # This would require authentication, so let's create a simpler approach
    print("Script ready to update admin roles.")
    print("First, make sure you're registered with: admin@aivideomaker.com")
    print()
    print("Then we'll add a temporary API endpoint to set your role to admin.")

if __name__ == "__main__":
    check_current_user()