from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from models import HospitalUnit, Patient, Payer, HospitalPayer
from utils.auth import login_required, permission_required, get_current_user
from utils.audit import log_audit
from config import Config

master_bp = Blueprint('masters', __name__, url_prefix='/masters')

# --- Hospital Units ---
@master_bp.route('/units', methods=['GET', 'POST'])
@login_required
@permission_required('manage_units')
def units():
    if request.method == 'POST':
        unit_code = request.form.get('unit_code', '').strip().upper()
        hospital_name = request.form.get('hospital_name', '').strip()
        address_line1 = request.form.get('address_line1', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        contact_no = request.form.get('contact_no', '').strip()
        email = request.form.get('email', '').strip()

        if HospitalUnit.query.filter_by(unit_code=unit_code).first():
            flash(f"Unit Code '{unit_code}' already exists.", 'error')
            return redirect(url_for('masters.units'))

        unit = HospitalUnit(
            unit_code=unit_code,
            hospital_name=hospital_name,
            address_line1=address_line1,
            city=city,
            state=state,
            pincode=pincode,
            contact_no=contact_no,
            email=email
        )
        db.session.add(unit)
        db.session.commit()

        log_audit('CREATE_HOSPITAL_UNIT', 'HospitalUnit', unit.unit_id, None, {'unit_code': unit_code})
        flash(f"Hospital Unit '{hospital_name}' created successfully!", 'success')
        return redirect(url_for('masters.units'))

    page = request.args.get('page', 1, type=int)
    units_pagination = HospitalUnit.query.order_by(HospitalUnit.unit_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    return render_template('masters/units.html', units=units_pagination.items, pagination=units_pagination)

# --- Patients Registry ---
@master_bp.route('/patients', methods=['GET', 'POST'])
@login_required
@permission_required('register_patient')
def patients():
    if request.method == 'POST':
        uhid = request.form.get('uhid', '').strip().upper()
        patient_name = request.form.get('patient_name', '').strip()
        date_of_birth = request.form.get('date_of_birth', '').strip()
        gender = request.form.get('gender', 'OTHER')
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()

        if Patient.query.filter_by(uhid=uhid).first():
            flash(f"Patient UHID '{uhid}' is already registered.", 'error')
            return redirect(url_for('masters.patients'))

        patient = Patient(
            uhid=uhid,
            patient_name=patient_name,
            date_of_birth=date_of_birth,
            gender=gender,
            phone=phone,
            email=email,
            address=address
        )
        db.session.add(patient)
        db.session.commit()

        log_audit('REGISTER_PATIENT', 'Patient', patient.patient_id, None, {'uhid': uhid, 'name': patient_name})
        flash(f"Patient '{patient_name}' (UHID: {uhid}) registered successfully!", 'success')
        return redirect(url_for('masters.patients'))

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    query = Patient.query
    if search:
        query = query.filter((Patient.uhid.ilike(f'%{search}%')) | (Patient.patient_name.ilike(f'%{search}%')) | (Patient.phone.ilike(f'%{search}%')))
    patients_pagination = query.order_by(Patient.patient_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)

    return render_template('masters/patients.html', patients=patients_pagination.items, pagination=patients_pagination, search=search)

# --- Payers Master ---
@master_bp.route('/payers', methods=['GET', 'POST'])
@login_required
@permission_required('manage_payers')
def payers():
    if request.method == 'POST':
        payer_code = request.form.get('payer_code', '').strip().upper()
        payer_name = request.form.get('payer_name', '').strip()
        payer_type = request.form.get('payer_type', 'INSURANCE')
        contact_person = request.form.get('contact_person', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        if Payer.query.filter_by(payer_code=payer_code).first():
            flash(f"Payer Code '{payer_code}' already exists.", 'error')
            return redirect(url_for('masters.payers'))

        payer = Payer(
            payer_code=payer_code,
            payer_name=payer_name,
            payer_type=payer_type,
            contact_person=contact_person,
            email=email,
            phone=phone,
            address=address
        )
        db.session.add(payer)
        db.session.commit()

        log_audit('CREATE_PAYER', 'Payer', payer.payer_id, None, {'payer_code': payer_code})
        flash(f"Payer '{payer_name}' created successfully!", 'success')
        return redirect(url_for('masters.payers'))

    page = request.args.get('page', 1, type=int)
    payers_pagination = Payer.query.order_by(Payer.payer_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    return render_template('masters/payers.html', payers=payers_pagination.items, pagination=payers_pagination)

# --- Hospital-Payer Configurations ---
@master_bp.route('/hospital-payers', methods=['GET', 'POST'])
@login_required
@permission_required('manage_payers')
def hospital_payers():
    if request.method == 'POST':
        unit_id = int(request.form.get('unit_id'))
        payer_id = int(request.form.get('payer_id'))
        payer_code_at_unit = request.form.get('payer_code_at_unit', '').strip()
        billing_type = request.form.get('billing_type', 'CREDIT')
        credit_allowed = request.form.get('credit_allowed') == 'on'
        submission_tat_days = int(request.form.get('submission_tat_days', 15))
        monthly_submission = request.form.get('monthly_submission') == 'on'
        document_requirement = request.form.get('document_requirement', '').strip()
        approval_required = request.form.get('approval_required') == 'on'
        dispatch_mode = request.form.get('dispatch_mode', 'COURIER')

        existing = HospitalPayer.query.filter_by(unit_id=unit_id, payer_id=payer_id).first()
        if existing:
            existing.payer_code_at_unit = payer_code_at_unit
            existing.billing_type = billing_type
            existing.credit_allowed = credit_allowed
            existing.submission_tat_days = submission_tat_days
            existing.monthly_submission = monthly_submission
            existing.document_requirement = document_requirement
            existing.approval_required = approval_required
            existing.dispatch_mode = dispatch_mode
            db.session.commit()
            flash("Updated existing Hospital-Payer Configuration successfully!", 'success')
            return redirect(url_for('masters.hospital_payers'))

        hp = HospitalPayer(
            unit_id=unit_id,
            payer_id=payer_id,
            payer_code_at_unit=payer_code_at_unit,
            billing_type=billing_type,
            credit_allowed=credit_allowed,
            submission_tat_days=submission_tat_days,
            monthly_submission=monthly_submission,
            document_requirement=document_requirement,
            approval_required=approval_required,
            dispatch_mode=dispatch_mode
        )
        db.session.add(hp)
        db.session.commit()

        log_audit('CREATE_HOSPITAL_PAYER_CONFIG', 'HospitalPayer', hp.hospital_payer_id, None, {'unit_id': unit_id, 'payer_id': payer_id})
        flash("Hospital-Payer Configuration saved successfully!", 'success')
        return redirect(url_for('masters.hospital_payers'))

    active_unit_id = session.get('active_unit_id')
    units_list = HospitalUnit.query.filter_by(status='ACTIVE').all()
    payers_list = Payer.query.filter_by(status='ACTIVE').all()

    page = request.args.get('page', 1, type=int)
    hp_pagination = HospitalPayer.query.order_by(HospitalPayer.hospital_payer_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)

    return render_template('masters/hospital_payers.html', units=units_list, payers=payers_list, hp_configs=hp_pagination.items, pagination=hp_pagination, active_unit_id=active_unit_id)

