from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from database import db
from models import User, Role, HospitalUnit, AuditLog
from utils.auth import login_required, permission_required, get_current_user
from utils.audit import log_audit
from config import Config

user_bp = Blueprint('users', __name__, url_prefix='/admin')

@user_bp.route('/users', methods=['GET', 'POST'])
@login_required
@permission_required('manage_users')
def users():
    if request.method == 'POST':
        employee_id = request.form.get('employee_id', '').strip().upper()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        role_id = int(request.form.get('role_id'))
        hospital_unit_id = request.form.get('hospital_unit_id')

        if User.query.filter_by(employee_id=employee_id).first():
            flash(f"Employee ID '{employee_id}' already exists.", 'error')
            return redirect(url_for('users.users'))

        if User.query.filter_by(email=email).first():
            flash(f"Email '{email}' is already registered.", 'error')
            return redirect(url_for('users.users'))

        user = User(
            employee_id=employee_id,
            name=name,
            email=email,
            phone=phone,
            password_hash=generate_password_hash(password),
            role_id=role_id,
            hospital_unit_id=int(hospital_unit_id) if hospital_unit_id else None,
            status='ACTIVE'
        )
        db.session.add(user)
        db.session.commit()

        log_audit('CREATE_USER', 'User', user.id, None, {'employee_id': employee_id, 'name': name})
        flash(f"User '{name}' ({employee_id}) created successfully!", 'success')
        return redirect(url_for('users.users'))

    page = request.args.get('page', 1, type=int)
    users_pagination = User.query.order_by(User.id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    roles = Role.query.all()
    units = HospitalUnit.query.filter_by(status='ACTIVE').all()

    return render_template('admin/users.html', users=users_pagination.items, pagination=users_pagination, roles=roles, units=units)

@user_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@permission_required('manage_users')
def toggle_user_status(user_id):
    if user_id == session.get('user_id'):
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('users.users'))

    user = User.query.get_or_404(user_id)
    new_status = 'INACTIVE' if user.status == 'ACTIVE' else 'ACTIVE'
    user.status = new_status
    db.session.commit()

    log_audit('TOGGLE_USER_STATUS', 'User', user.id, None, {'status': new_status})
    flash(f"User @{user.employee_id} status updated to {new_status}.", 'success')
    return redirect(url_for('users.users'))

@user_bp.route('/audit-logs')
@login_required
@permission_required('view_audit_logs')
def audit_logs():
    page = request.args.get('page', 1, type=int)
    logs_pagination = AuditLog.query.order_by(AuditLog.log_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    return render_template('admin/audit_logs.html', logs=logs_pagination.items, pagination=logs_pagination)

