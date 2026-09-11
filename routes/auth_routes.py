from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from database import db
from models import User, HospitalUnit
from utils.auth import login_required, get_current_user
from utils.audit import log_audit

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        employee_id = request.form.get('employee_id', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(employee_id=employee_id).first()

        if user and check_password_hash(user.password_hash, password):
            if user.status != 'ACTIVE':
                flash('Account is inactive. Please contact system administrator.', 'error')
                return render_template('login.html')

            session.clear()
            session['user_id'] = user.id
            session['employee_id'] = user.employee_id
            session['name'] = user.name
            session['role_code'] = user.role.role_code
            session['role_name'] = user.role.role_name
            session['unit_id'] = user.hospital_unit_id
            session['active_unit_id'] = user.hospital_unit_id

            user.last_login = datetime.utcnow()
            db.session.commit()

            log_audit('USER_LOGIN', 'User', user.id, None, {'employee_id': user.employee_id})
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Invalid Employee ID or Password.', 'error')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        log_audit('USER_LOGOUT', 'User', user_id)
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/select-unit/<int:unit_id>', methods=['POST'])
@login_required
def select_unit(unit_id):
    unit = HospitalUnit.query.get_or_404(unit_id)
    session['active_unit_id'] = unit.unit_id
    flash(f'Switched active hospital unit to {unit.hospital_name} ({unit.unit_code}).', 'success')
    return redirect(request.referrer or url_for('main.dashboard'))

