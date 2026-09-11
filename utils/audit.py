import json
from flask import session, request
from database import db
from models import AuditLog

def log_audit(action, entity_type, entity_id=None, old_values=None, new_values=None):
    """
    Log every critical business event for security & audit trail compliance.
    """
    try:
        user_id = session.get("user_id")
        
        old_val_str = json.dumps(old_values, default=str) if old_values is not None else None
        new_val_str = json.dumps(new_values, default=str) if new_values is not None else None
        
        ip_addr = request.remote_addr if request else "127.0.0.1"

        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            old_values=old_val_str,
            new_values=new_val_str,
            ip_address=ip_addr
        )
        db.session.add(audit_entry)
        db.session.commit()
    except Exception as e:
        print(f"Error writing audit log: {e}")
        db.session.rollback()

