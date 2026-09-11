from functools import wraps
from flask import session, flash, redirect, url_for, request
from models import User, Role, Permission

def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "error")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(perm_code):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in first.", "error")
                return redirect(url_for("auth.login"))
            
            user = get_current_user()
            if not user or user.status != "ACTIVE":
                flash("Your account is inactive or not found.", "error")
                return redirect(url_for("auth.login"))

            # Super admin has all permissions
            if user.role.role_code == "super_admin":
                return f(*args, **kwargs)

            # Check role permissions
            user_perms = [p.perm_code for p in user.role.permissions]
            if perm_code not in user_perms:
                flash(f"Access denied: Missing required permission '{perm_code}'.", "error")
                return redirect(url_for("main.dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_required(*role_codes):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in first.", "error")
                return redirect(url_for("auth.login"))
            
            user = get_current_user()
            if not user or user.role.role_code not in role_codes:
                flash("Access denied: Unauthorized role.", "error")
                return redirect(url_for("main.dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

