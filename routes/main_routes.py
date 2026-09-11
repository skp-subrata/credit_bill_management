from flask import Blueprint, render_template, session
from models import HospitalUnit, IPAdmission, OPEpisode, Bill, Patient, Payer
from utils.auth import login_required, get_current_user
from utils.exports import calculate_aging_category

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    unit_id = session.get('active_unit_id')
    current_unit = HospitalUnit.query.get(unit_id) if unit_id else None
    all_units = HospitalUnit.query.filter_by(status='ACTIVE').all()

    # Hospital Unit Metrics
    admissions_cnt = IPAdmission.query.filter_by(unit_id=unit_id, admission_status='ADMITTED').count() if unit_id else 0
    episodes_cnt = OPEpisode.query.filter_by(unit_id=unit_id).count() if unit_id else 0
    bills_cnt = Bill.query.filter_by(unit_id=unit_id).count() if unit_id else 0
    
    # Financial KPI summary
    bills_query = Bill.query.filter_by(unit_id=unit_id) if unit_id else Bill.query
    all_bills = bills_query.all()

    total_billed = sum(b.bill_amount for b in all_bills)
    total_outstanding = sum(b.outstanding_amount for b in all_bills)
    pending_verifications = sum(1 for b in all_bills if b.bill_status in ('GENERATED', 'VERIFICATION_PENDING'))
    ready_dispatches = sum(1 for b in all_bills if b.bill_status == 'VERIFIED')

    # Calculate Aging Breakdown
    aging_summary = {
        "0–3 days": 0.0,
        "4–7 days": 0.0,
        "8–15 days": 0.0,
        "16–30 days": 0.0,
        "31–60 days": 0.0,
        ">60 days": 0.0
    }

    for b in all_bills:
        if b.outstanding_amount > 0:
            cat = calculate_aging_category(b.bill_date)
            if cat in aging_summary:
                aging_summary[cat] += b.outstanding_amount

    recent_bills = bills_query.order_by(Bill.bill_id.desc()).limit(10).all()

    return render_template(
        'dashboard.html',
        current_unit=current_unit,
        units=all_units,
        admissions_cnt=admissions_cnt,
        episodes_cnt=episodes_cnt,
        bills_cnt=bills_cnt,
        total_billed=total_billed,
        total_outstanding=total_outstanding,
        pending_verifications=pending_verifications,
        ready_dispatches=ready_dispatches,
        aging_summary=aging_summary,
        recent_bills=recent_bills
    )

