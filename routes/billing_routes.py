from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from models import (
    Bill, BillVerification, BillDispatch, BillQuery, BillPayment, 
    IPAdmission, IPDischarge, OPEpisode, Patient, HospitalPayer, Payer, User
)
from utils.auth import login_required, permission_required, get_current_user
from utils.audit import log_audit

from config import Config
from utils.tat import calculate_tat_metrics, get_dispatch_date_bounds, validate_dispatch_date

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

# --- BILLS QUEUE & GENERATION ---
@billing_bp.route('/bills', methods=['GET', 'POST'])
@login_required
@permission_required('generate_bill')
def bills():
    unit_id = session.get('active_unit_id')
    if request.method == 'POST':
        bill_number = request.form.get('bill_number', '').strip().upper()
        encounter_type = request.form.get('encounter_type') # IP or OP
        bill_type = request.form.get('bill_type', 'CREDIT') # CREDIT or CASH
        bill_date = request.form.get('bill_date')
        bill_amount = float(request.form.get('bill_amount', 0))

        if Bill.query.filter_by(bill_number=bill_number).first():
            flash(f"Bill Number '{bill_number}' already exists.", 'error')
            return redirect(url_for('billing.bills'))

        patient_id = None
        patient_name_snapshot = ''
        ip_number = None
        admission_id = None
        discharge_id = None
        episode_id = None
        payer_id = None
        hospital_payer_id = None

        if encounter_type == 'IP':
            admission_id_val = request.form.get('admission_id')
            if not admission_id_val:
                flash('Please select an IP Admission for IP bill generation.', 'error')
                return redirect(url_for('billing.bills'))
            admission = IPAdmission.query.get_or_404(int(admission_id_val))
            
            # IP Credit bills should be discharged first
            if bill_type == 'CREDIT' and admission.admission_status != 'DISCHARGED':
                flash('IP Credit Bill cannot be completed before patient discharge.', 'error')
                return redirect(url_for('billing.bills'))

            patient_id = admission.patient_id
            patient_name_snapshot = admission.patient_name_snapshot
            ip_number = admission.ip_number
            admission_id = admission.admission_id
            if admission.discharge:
                discharge_id = admission.discharge.discharge_id
            
            if bill_type == 'CREDIT':
                payer_id = admission.payer_id
                hospital_payer_id = admission.hospital_payer_id

        elif encounter_type == 'OP':
            episode_id_val = request.form.get('episode_id')
            if not episode_id_val:
                flash('Please select an OP Episode for OP bill generation.', 'error')
                return redirect(url_for('billing.bills'))
            episode = OPEpisode.query.get_or_404(int(episode_id_val))
            patient_id = episode.patient_id
            patient_name_snapshot = episode.patient_name_snapshot
            episode_id = episode.episode_id
            
            if bill_type == 'CREDIT':
                payer_id = episode.payer_id

        if bill_type == 'CREDIT' and not payer_id:
            flash('Credit Bills must have a valid Payer configured.', 'error')
            return redirect(url_for('billing.bills'))

        bill = Bill(
            bill_number=bill_number,
            unit_id=unit_id,
            encounter_type=encounter_type,
            bill_type=bill_type,
            patient_id=patient_id,
            patient_name_snapshot=patient_name_snapshot,
            ip_number=ip_number,
            admission_id=admission_id,
            discharge_id=discharge_id,
            payer_id=payer_id,
            hospital_payer_id=hospital_payer_id,
            bill_date=bill_date,
            bill_amount=bill_amount,
            approved_amount=bill_amount,
            outstanding_amount=bill_amount,
            bill_status='GENERATED',
            created_by=session.get('user_id')
        )
        db.session.add(bill)
        db.session.commit()

        log_audit('GENERATE_BILL', 'Bill', bill.bill_id, None, {'bill_number': bill_number, 'amount': bill_amount})
        flash(f"Bill '{bill_number}' of ₹{bill_amount:,.2f} generated successfully!", 'success')
        return redirect(url_for('billing.bills'))

    # Load Discharged IP admissions & OP episodes ready for billing
    ip_admissions_ready = IPAdmission.query.filter_by(unit_id=unit_id).all()
    op_episodes_ready = OPEpisode.query.filter_by(unit_id=unit_id).all()

    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    bill_type_filter = request.args.get('bill_type', '').strip()
    sort_order = request.args.get('sort_order', 'desc').lower()
    if sort_order not in ('asc', 'desc'):
        sort_order = 'desc'

    bills_query = Bill.query.filter_by(unit_id=unit_id)
    if q:
        bills_query = bills_query.filter(
            (Bill.bill_number.ilike(f'%{q}%')) |
            (Bill.patient_name_snapshot.ilike(f'%{q}%'))
        )
    if status_filter:
        bills_query = bills_query.filter(Bill.bill_status == status_filter)
    if bill_type_filter:
        bills_query = bills_query.filter(Bill.bill_type == bill_type_filter)

    if sort_order == 'asc':
        bills_query = bills_query.order_by(Bill.bill_date.asc(), Bill.bill_id.asc())
    else:
        bills_query = bills_query.order_by(Bill.bill_date.desc(), Bill.bill_id.desc())

    bills_pagination = bills_query.paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    bills_list = bills_pagination.items
    for b in bills_list:
        b.update_lifecycle_status()
        tat_days = 15
        monthly_sub = False
        if b.hospital_payer:
            tat_days = b.hospital_payer.submission_tat_days
            monthly_sub = b.hospital_payer.monthly_submission
        b.tat_info = calculate_tat_metrics(b.bill_date, submission_tat_days=tat_days, monthly_submission=monthly_sub)
    db.session.commit()

    return render_template(
        'billing/bills.html',
        bills=bills_list,
        pagination=bills_pagination,
        ip_admissions=ip_admissions_ready,
        op_episodes=op_episodes_ready,
        q=q,
        status_filter=status_filter,
        bill_type_filter=bill_type_filter,
        sort_order=sort_order
    )

# --- BILL DETAIL & TIMELINE ---
@billing_bp.route('/bills/<int:bill_id>')
@login_required
def bill_detail(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    bill.update_lifecycle_status()
    db.session.commit()

    tat_days = 15
    monthly_sub = False
    if bill.hospital_payer:
        tat_days = bill.hospital_payer.submission_tat_days
        monthly_sub = bill.hospital_payer.monthly_submission
    tat_info = calculate_tat_metrics(bill.bill_date, submission_tat_days=tat_days, monthly_submission=monthly_sub)
    min_dispatch_date, max_dispatch_date = get_dispatch_date_bounds()
    return render_template('billing/bill_detail.html', bill=bill, tat_info=tat_info, min_dispatch_date=min_dispatch_date, max_dispatch_date=max_dispatch_date)

# --- BILL VERIFICATION ---
@billing_bp.route('/bills/<int:bill_id>/verify', methods=['POST'])
@login_required
@permission_required('verify_bill')
def verify_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    action = request.form.get('action') # VERIFY or REJECT
    remarks = request.form.get('remarks', '')
    rejection_reason = request.form.get('rejection_reason', '')

    verification_status = 'VERIFIED' if action == 'VERIFY' else 'REJECTED'

    verification = BillVerification(
        bill_id=bill.bill_id,
        verification_status=verification_status,
        verified_by=session.get('user_id'),
        verification_remarks=remarks,
        rejection_reason=rejection_reason
    )

    db.session.add(verification)
    bill.update_lifecycle_status()
    db.session.commit()

    if action == 'VERIFY':
        flash(f"Bill '{bill.bill_number}' verified and approved for dispatch!", 'success')
    else:
        flash(f"Bill '{bill.bill_number}' rejected for rework.", 'error')

    log_audit('VERIFY_BILL', 'Bill', bill.bill_id, None, {'status': verification_status})
    return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

# --- DISPATCH TRACKER ---
@billing_bp.route('/bills/<int:bill_id>/dispatch', methods=['POST'])
@login_required
@permission_required('dispatch_bill')
def dispatch_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)

    # Validation: Until a bill is VERIFIED, entering dispatch details is NOT allowed
    if not bill.is_verified:
        flash(f"Cannot dispatch bill '{bill.bill_number}'. The bill must be VERIFIED before dispatch details can be entered.", 'error')
        return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

    dispatch_date = request.form.get('dispatch_date')

    # Enforce Dispatch Date restriction (Today - 3 days to Today)
    is_valid, error_msg = validate_dispatch_date(dispatch_date)
    if not is_valid:
        flash(error_msg, 'error')
        return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

    dispatch_mode = request.form.get('dispatch_mode', 'COURIER')
    courier_name = request.form.get('courier_name', '')
    tracking_number = request.form.get('tracking_number', '')
    recipient_name = request.form.get('recipient_name', '')
    recipient_email = request.form.get('recipient_email', '')
    remarks = request.form.get('remarks', '')

    dispatch = BillDispatch(
        bill_id=bill.bill_id,
        bill_number=bill.bill_number,
        dispatch_date=dispatch_date,
        dispatch_mode=dispatch_mode,
        courier_name=courier_name,
        tracking_number=tracking_number,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        dispatch_status='DISPATCHED',
        dispatched_by=session.get('user_id'),
        remarks=remarks
    )

    db.session.add(dispatch)
    bill.update_lifecycle_status()
    db.session.commit()

    log_audit('DISPATCH_BILL', 'BillDispatch', dispatch.dispatch_id, None, {'bill_number': bill.bill_number, 'mode': dispatch_mode})
    flash(f"Dispatch record created for Bill '{bill.bill_number}'!", 'success')
    return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

# --- PAYER QUERY MANAGEMENT ---
@billing_bp.route('/bills/<int:bill_id>/queries', methods=['POST'])
@login_required
@permission_required('manage_query')
def raise_query(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    query_code = f"QRY-{bill.bill_number}-{datetime.utcnow().strftime('%M%S')}"
    query_date = request.form.get('query_date')
    query_type = request.form.get('query_type', 'DOCUMENTATION')
    query_description = request.form.get('query_description', '')
    raised_by_payer = request.form.get('raised_by_payer', '')
    due_date = request.form.get('due_date', '')

    query = BillQuery(
        bill_id=bill.bill_id,
        query_code=query_code,
        query_date=query_date,
        query_type=query_type,
        query_description=query_description,
        raised_by_payer=raised_by_payer,
        query_status='OPEN',
        assigned_to=session.get('user_id'),
        due_date=due_date
    )

    db.session.add(query)
    bill.update_lifecycle_status()
    db.session.commit()

    log_audit('RAISE_PAYER_QUERY', 'BillQuery', query.query_id, None, {'query_code': query_code})
    flash(f"Payer Query '{query_code}' recorded!", 'success')
    return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

@billing_bp.route('/queries/<int:query_id>/respond', methods=['POST'])
@login_required
@permission_required('manage_query')
def respond_query(query_id):
    query = BillQuery.query.get_or_404(query_id)
    query_status = request.form.get('query_status', 'RESOLVED')
    response_remarks = request.form.get('response_remarks', '')

    query.query_status = query_status
    query.response_remarks = response_remarks
    query.responded_at = datetime.utcnow()
    query.responded_by = session.get('user_id')

    query.bill.update_lifecycle_status()
    db.session.commit()

    log_audit('RESPOND_PAYER_QUERY', 'BillQuery', query.query_id, None, {'status': query_status})
    flash(f"Query '{query.query_code}' status updated to {query_status}!", 'success')
    return redirect(url_for('billing.bill_detail', bill_id=query.bill_id))

# --- PAYMENTS & SETTLEMENT ---
@billing_bp.route('/bills/<int:bill_id>/payments', methods=['POST'])
@login_required
@permission_required('process_payment')
def record_payment(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    payment_date = request.form.get('payment_date')
    payment_mode = request.form.get('payment_mode', 'NEFT/RTGS')
    utr_number = request.form.get('utr_number', '').strip()
    amount_received = float(request.form.get('amount_received', 0))
    short_fall_amount = float(request.form.get('short_fall_amount', 0))
    disallowance_reason = request.form.get('disallowance_reason', '')
    remarks = request.form.get('remarks', '')

    payment_status = 'FULL' if amount_received >= bill.outstanding_amount else 'PARTIAL'

    payment = BillPayment(
        bill_id=bill.bill_id,
        payment_date=payment_date,
        payment_mode=payment_mode,
        utr_number=utr_number,
        amount_received=amount_received,
        short_fall_amount=short_fall_amount,
        disallowance_reason=disallowance_reason,
        payment_status=payment_status,
        processed_by=session.get('user_id'),
        remarks=remarks
    )

    # Update bill outstanding balance
    bill.outstanding_amount = max(0.0, bill.outstanding_amount - amount_received)
    db.session.add(payment)

    bill.update_lifecycle_status()
    db.session.commit()

    log_audit('RECORD_BILL_PAYMENT', 'BillPayment', payment.payment_id, None, {'utr': utr_number, 'amount': amount_received})
    flash(f"Payment of ₹{amount_received:,.2f} recorded under UTR '{utr_number}'!", 'success')
    return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

# --- BILL CLOSURE ---
@billing_bp.route('/bills/<int:bill_id>/close', methods=['POST'])
@login_required
@permission_required('close_bill')
def close_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    bill.bill_status = 'CLOSED'
    db.session.commit()

    log_audit('CLOSE_BILL', 'Bill', bill.bill_id)
    flash(f"Bill '{bill.bill_number}' has been formally CLOSED and archived.", 'success')
    return redirect(url_for('billing.bill_detail', bill_id=bill.bill_id))

