from datetime import datetime
from flask import Blueprint, render_template, request, Response, send_file, session
from database import db
from models import (
    IPAdmission, IPDischarge, OPEpisode, Bill, BillDispatch, 
    BillQuery, BillPayment, User, AuditLog, HospitalUnit, Payer
)
from utils.auth import login_required, permission_required
from utils.exports import generate_csv_report, generate_excel_report, calculate_aging_category

report_bp = Blueprint('reports', __name__, url_prefix='/reports')

@report_bp.route('/')
@login_required
@permission_required('view_reports')
def index():
    unit_id = session.get('active_unit_id')
    units = HospitalUnit.query.all()
    payers = Payer.query.all()
    return render_template('reports/index.html', units=units, payers=payers, active_unit_id=unit_id)

@report_bp.route('/<report_type>/export')
@login_required
@permission_required('view_reports')
def export_report(report_type):
    fmt = request.args.get('format', 'csv').lower() # csv or excel
    unit_id = request.args.get('unit_id', type=int) or session.get('active_unit_id')

    headers = []
    rows = []
    title = report_type.upper()

    if report_type == 'ip_admissions':
        title = "IP Admissions Report"
        headers = ['Admission ID', 'IP Number', 'Unit', 'UHID/Patient', 'Admission Date', 'Department', 'Doctor', 'Status', 'Bill Type']
        query = IPAdmission.query.filter_by(unit_id=unit_id).all()
        for r in query:
            rows.append([r.admission_id, r.ip_number, r.unit.hospital_name, r.patient_name_snapshot, r.admission_date, r.department, r.doctor_name, r.admission_status, r.bill_type])

    elif report_type == 'discharges':
        title = "IP Discharge Report"
        headers = ['Discharge ID', 'IP Number', 'Discharge Date', 'Discharge Type', 'Status', 'Remarks']
        query = IPDischarge.query.all()
        for r in query:
            rows.append([r.discharge_id, r.ip_number, r.discharge_date, r.discharge_type, r.discharge_status, r.remarks])

    elif report_type == 'op_episodes':
        title = "OP Episodes Report"
        headers = ['Episode ID', 'OP Number', 'Unit', 'Patient Name', 'Visit Date', 'Department', 'Doctor', 'Status']
        query = OPEpisode.query.filter_by(unit_id=unit_id).all()
        for r in query:
            rows.append([r.episode_id, r.op_number, r.unit.hospital_name, r.patient_name_snapshot, r.visit_date, r.department, r.doctor_name, r.episode_status])

    elif report_type == 'billing':
        title = "Billing Report"
        headers = ['Bill ID', 'Bill Number', 'Encounter', 'Patient Name', 'Payer', 'Bill Date', 'Amount', 'Outstanding', 'Status']
        query = Bill.query.filter_by(unit_id=unit_id).all()
        for r in query:
            pname = r.payer.payer_name if r.payer else 'N/A (Cash)'
            rows.append([r.bill_id, r.bill_number, r.encounter_type, r.patient_name_snapshot, pname, r.bill_date, r.bill_amount, r.outstanding_amount, r.bill_status])

    elif report_type == 'aging':
        title = "Bill & Query Aging Report"
        headers = ['Bill Number', 'Patient Name', 'Bill Date', 'Aging Bracket', 'Bill Amount', 'Outstanding Amount', 'Bill Status']
        query = Bill.query.filter_by(unit_id=unit_id).all()
        for r in query:
            aging_cat = calculate_aging_category(r.bill_date)
            rows.append([r.bill_number, r.patient_name_snapshot, r.bill_date, aging_cat, r.bill_amount, r.outstanding_amount, r.bill_status])

    elif report_type == 'audit':
        title = "System Audit Trail Report"
        headers = ['Log ID', 'User ID', 'Action', 'Entity Type', 'Entity ID', 'IP Address', 'Timestamp']
        query = AuditLog.query.order_by(AuditLog.log_id.desc()).limit(1000).all()
        for r in query:
            rows.append([r.log_id, r.user_id, r.action, r.entity_type, r.entity_id, r.ip_address, r.timestamp.strftime('%Y-%m-%d %H:%M:%S')])

    else:
        # Default Billing Export
        headers = ['Bill Number', 'Patient Name', 'Bill Date', 'Amount', 'Outstanding', 'Status']
        query = Bill.query.filter_by(unit_id=unit_id).all()
        for r in query:
            rows.append([r.bill_number, r.patient_name_snapshot, r.bill_date, r.bill_amount, r.outstanding_amount, r.bill_status])

    if fmt == 'excel':
        excel_bytes = generate_excel_report(title, headers, rows)
        return Response(
            excel_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={report_type}_report.xlsx'}
        )
    else:
        csv_data = generate_csv_report(headers, rows)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={report_type}_report.csv'}
        )

