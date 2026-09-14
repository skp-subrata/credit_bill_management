from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from models import IPAdmission, IPDischarge, OPEpisode, Patient, HospitalUnit, Payer, HospitalPayer
from utils.auth import login_required, permission_required, get_current_user
from utils.audit import log_audit
from config import Config

encounter_bp = Blueprint('encounters', __name__, url_prefix='/encounters')

# --- IP ADMISSIONS ---
@encounter_bp.route('/ip/admissions', methods=['GET', 'POST'])
@login_required
@permission_required('manage_admission')
def ip_admissions():
    unit_id = session.get('active_unit_id')
    if request.method == 'POST':
        ip_number = request.form.get('ip_number', '').strip().upper()
        patient_id = int(request.form.get('patient_id'))
        admission_date = request.form.get('admission_date')
        admission_time = request.form.get('admission_time', '')
        department = request.form.get('department', 'General')
        doctor_name = request.form.get('doctor_name', '')
        bill_type = request.form.get('bill_type', 'CREDIT')
        hospital_payer_id_val = request.form.get('hospital_payer_id')

        # Check IP Number uniqueness within unit
        if IPAdmission.query.filter_by(unit_id=unit_id, ip_number=ip_number).first():
            flash(f"IP Number '{ip_number}' already exists in this hospital unit.", 'error')
            return redirect(url_for('encounters.ip_admissions'))

        patient = Patient.query.get_or_404(patient_id)

        payer_id = None
        hospital_payer_id = None
        if bill_type == 'CREDIT' and hospital_payer_id_val:
            hp = HospitalPayer.query.get(int(hospital_payer_id_val))
            if hp:
                hospital_payer_id = hp.hospital_payer_id
                payer_id = hp.payer_id

        admission = IPAdmission(
            ip_number=ip_number,
            unit_id=unit_id,
            patient_id=patient_id,
            patient_name_snapshot=patient.patient_name,
            admission_date=admission_date,
            admission_time=admission_time,
            department=department,
            doctor_name=doctor_name,
            bill_type=bill_type,
            payer_id=payer_id,
            hospital_payer_id=hospital_payer_id,
            admission_status='ADMITTED'
        )
        db.session.add(admission)
        db.session.commit()

        log_audit('CREATE_IP_ADMISSION', 'IPAdmission', admission.admission_id, None, {'ip_number': ip_number, 'patient': patient.patient_name})
        flash(f"IP Admission '{ip_number}' created for patient '{patient.patient_name}'.", 'success')
        return redirect(url_for('encounters.ip_admissions'))

    patients = Patient.query.order_by(Patient.patient_name).all()
    hospital_payers = HospitalPayer.query.filter_by(unit_id=unit_id, status='ACTIVE').all()

    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    bill_type_filter = request.args.get('bill_type', '').strip()
    sort_order = request.args.get('sort_order', 'desc').lower()
    if sort_order not in ('asc', 'desc'):
        sort_order = 'desc'

    query = IPAdmission.query.filter_by(unit_id=unit_id)
    if q:
        query = query.filter(
            (IPAdmission.ip_number.ilike(f'%{q}%')) |
            (IPAdmission.patient_name_snapshot.ilike(f'%{q}%'))
        )
    if status_filter:
        query = query.filter(IPAdmission.admission_status == status_filter)
    if bill_type_filter:
        query = query.filter(IPAdmission.bill_type == bill_type_filter)

    if sort_order == 'asc':
        query = query.order_by(IPAdmission.admission_date.asc(), IPAdmission.admission_id.asc())
    else:
        query = query.order_by(IPAdmission.admission_date.desc(), IPAdmission.admission_id.desc())

    admissions_pagination = query.paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)

    return render_template(
        'encounters/ip_admissions.html',
        admissions=admissions_pagination.items,
        pagination=admissions_pagination,
        patients=patients,
        hospital_payers=hospital_payers,
        q=q,
        status_filter=status_filter,
        bill_type_filter=bill_type_filter,
        sort_order=sort_order
    )

# --- IP DISCHARGE ---
@encounter_bp.route('/ip/admissions/<int:admission_id>/discharge', methods=['POST'])
@login_required
@permission_required('manage_admission')
def ip_discharge(admission_id):
    admission = IPAdmission.query.get_or_404(admission_id)
    if admission.admission_status == 'DISCHARGED':
        flash('This IP Admission is already discharged.', 'error')
        return redirect(url_for('encounters.ip_admissions'))

    discharge_date = request.form.get('discharge_date')
    discharge_time = request.form.get('discharge_time', '')
    discharge_type = request.form.get('discharge_type', 'REGULAR')
    remarks = request.form.get('remarks', '')

    discharge = IPDischarge(
        admission_id=admission.admission_id,
        ip_number=admission.ip_number,
        discharge_date=discharge_date,
        discharge_time=discharge_time,
        discharge_type=discharge_type,
        discharge_status='COMPLETED',
        discharge_summary_status='COMPLETED',
        final_bill_status='PENDING',
        initiated_by=session.get('user_id'),
        completed_by=session.get('user_id'),
        remarks=remarks
    )

    admission.admission_status = 'DISCHARGED'
    admission.discharge_status = 'DISCHARGED'

    db.session.add(discharge)
    db.session.commit()

    log_audit('DISCHARGE_IP_PATIENT', 'IPDischarge', discharge.discharge_id, None, {'ip_number': admission.ip_number})
    flash(f"Patient under IP Number '{admission.ip_number}' has been discharged successfully!", 'success')
    return redirect(url_for('encounters.ip_admissions'))

# --- OP EPISODES ---
@encounter_bp.route('/op/episodes', methods=['GET', 'POST'])
@login_required
@permission_required('manage_op_episode')
def op_episodes():
    unit_id = session.get('active_unit_id')
    if request.method == 'POST':
        op_number = request.form.get('op_number', '').strip().upper()
        patient_id = int(request.form.get('patient_id'))
        visit_date = request.form.get('visit_date')
        department = request.form.get('department', 'Outpatient')
        doctor_name = request.form.get('doctor_name', '')
        hospital_payer_id_val = request.form.get('hospital_payer_id')

        if OPEpisode.query.filter_by(unit_id=unit_id, op_number=op_number).first():
            flash(f"OP Number '{op_number}' already exists in this unit.", 'error')
            return redirect(url_for('encounters.op_episodes'))

        patient = Patient.query.get_or_404(patient_id)

        payer_id = None
        hospital_payer_id = None
        if hospital_payer_id_val:
            hp = HospitalPayer.query.get(int(hospital_payer_id_val))
            if hp:
                hospital_payer_id = hp.hospital_payer_id
                payer_id = hp.payer_id

        episode = OPEpisode(
            op_number=op_number,
            unit_id=unit_id,
            patient_id=patient_id,
            patient_name_snapshot=patient.patient_name,
            visit_date=visit_date,
            doctor_name=doctor_name,
            department=department,
            payer_id=payer_id,
            hospital_payer_id=hospital_payer_id,
            episode_status='ACTIVE'
        )
        db.session.add(episode)
        db.session.commit()

        log_audit('REGISTER_OP_EPISODE', 'OPEpisode', episode.episode_id, None, {'op_number': op_number})
        flash(f"OP Episode '{op_number}' registered successfully!", 'success')
        return redirect(url_for('encounters.op_episodes'))

    patients = Patient.query.order_by(Patient.patient_name).all()
    hospital_payers = HospitalPayer.query.filter_by(unit_id=unit_id, status='ACTIVE').all()

    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    department_filter = request.args.get('department', '').strip()
    sort_order = request.args.get('sort_order', 'desc').lower()
    if sort_order not in ('asc', 'desc'):
        sort_order = 'desc'

    query = OPEpisode.query.filter_by(unit_id=unit_id)
    if q:
        query = query.filter(
            (OPEpisode.op_number.ilike(f'%{q}%')) |
            (OPEpisode.patient_name_snapshot.ilike(f'%{q}%'))
        )
    if department_filter:
        query = query.filter(OPEpisode.department == department_filter)

    if sort_order == 'asc':
        query = query.order_by(OPEpisode.visit_date.asc(), OPEpisode.episode_id.asc())
    else:
        query = query.order_by(OPEpisode.visit_date.desc(), OPEpisode.episode_id.desc())

    episodes_pagination = query.paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)

    return render_template(
        'encounters/op_episodes.html',
        episodes=episodes_pagination.items,
        pagination=episodes_pagination,
        patients=patients,
        hospital_payers=hospital_payers,
        q=q,
        department_filter=department_filter,
        sort_order=sort_order
    )

