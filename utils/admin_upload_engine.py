import os, io, json
from datetime import datetime
from openpyxl import Workbook, load_workbook
import csv

from database import db
from models import (
    HospitalUnit, Payer, HospitalPayer, Patient, DoctorMaster, 
    Bill, BillVerification, BillDispatch, BillQuery, BillPayment, AdminUploadHistory
)

def parse_admin_file(file_bytes, filename):
    """
    Multi-format parser for .xlsx, .xls, .csv files.
    Returns list of row dicts with lowercased header keys.
    """
    fn_lower = filename.lower()
    
    # 1. CSV Parser
    if fn_lower.endswith('.csv'):
        try:
            text = file_bytes.decode('utf-8-sig', errors='ignore')
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for r in reader:
                rows.append({str(k).strip().lower(): str(v).strip() for k, v in r.items() if k})
            return rows
        except Exception:
            pass

    # 2. OpenPyXL (.xlsx)
    try:
        wb = load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
        if raw_rows and len(raw_rows) > 1:
            headers = [str(c).strip().lower() if c is not None else '' for c in raw_rows[0]]
            rows = []
            for r in raw_rows[1:]:
                if not r or not any(c is not None and str(c).strip() != '' for c in r):
                    continue
                row_dict = {}
                for idx, h in enumerate(headers):
                    if h and idx < len(r):
                        row_dict[h] = str(r[idx]).strip() if r[idx] is not None else ''
                if row_dict:
                    rows.append(row_dict)
            return rows
    except Exception:
        pass

    # 3. Fallback to HIS Parser
    try:
        from utils.his_sync.parsers import parse_his_file
        return parse_his_file(filename, file_bytes)
    except Exception:
        return []
from utils.tat import parse_date_safe

# Data Categories Configuration
DATA_CATEGORIES_CONFIG = {
    'hospital_units': {
        'label': 'Hospital / Unit Master',
        'headers': ['unit_code', 'hospital_name', 'address_line1', 'city', 'state', 'contact_no', 'email', 'status'],
        'sample': [
            ['MH-BLR-01', 'Manipal Hospital Bangalore', 'HAL Airport Road', 'Bangalore', 'Karnataka', '080-12345678', 'blr@manipal.com', 'ACTIVE'],
            ['MH-DEL-01', 'Manipal Hospital Delhi', 'Dwarka Sector 6', 'New Delhi', 'Delhi', '011-87654321', 'delhi@manipal.com', 'ACTIVE']
        ],
        'key_fields': ['unit_code']
    },
    'payers': {
        'label': 'Payer Master',
        'headers': ['payer_code', 'payer_name', 'payer_type', 'contact_person', 'email', 'phone', 'address', 'status'],
        'sample': [
            ['PAY-STAR-01', 'Star Health Insurance', 'INSURANCE', 'Rajesh Kumar', 'claims@starhealth.in', '1800-425-2255', 'Chennai, TN', 'ACTIVE'],
            ['PAY-CGHS-01', 'CGHS Government Plan', 'GOVERNMENT', 'Dr. Sharma', 'cghs@gov.in', '011-23061234', 'New Delhi', 'ACTIVE']
        ],
        'key_fields': ['payer_code']
    },
    'hospital_payers': {
        'label': 'Hospital-Payer / Payer-Pair Master',
        'headers': ['unit_code', 'payer_code', 'payer_code_at_unit', 'billing_type', 'credit_allowed', 'submission_tat_days', 'monthly_submission', 'dispatch_mode', 'status'],
        'sample': [
            ['MH-BLR-01', 'PAY-STAR-01', 'STAR-BLR', 'CREDIT', 'Yes', 15, 'Yes', 'ONLINE + COURIER', 'ACTIVE'],
            ['MH-BLR-01', 'PAY-CGHS-01', 'CGHS-BLR', 'CREDIT', 'Yes', 30, 'No', 'HAND_DELIVERY', 'ACTIVE']
        ],
        'key_fields': ['unit_code', 'payer_code']
    },
    'patients': {
        'label': 'Patient Master',
        'headers': ['uhid', 'patient_name', 'date_of_birth', 'gender', 'phone', 'email', 'address'],
        'sample': [
            ['UHID-9001001', 'Ramesh Sharma', '1985-06-15', 'MALE', '9876543210', 'ramesh@gmail.com', 'Indiranagar, Bangalore'],
            ['UHID-9001002', 'Priya Patel', '1992-11-20', 'FEMALE', '9812345678', 'priya@yahoo.com', 'Koramangala, Bangalore']
        ],
        'key_fields': ['uhid']
    },
    'doctor_master': {
        'label': 'Doctor Master',
        'headers': ['doctor_code', 'doctor_name', 'department', 'specialization', 'unit_code'],
        'sample': [
            ['DOC-101', 'Dr. Ananya Roy', 'Cardiology', 'Interventional Cardiologist', 'MH-BLR-01'],
            ['DOC-102', 'Dr. Vikram Seth', 'Orthopedics', 'Joint Replacement Specialist', 'MH-BLR-01']
        ],
        'key_fields': ['doctor_code']
    },
    'bills': {
        'label': 'Bills / Base Transactions',
        'headers': ['bill_number', 'unit_code', 'uhid', 'encounter_type', 'bill_type', 'ip_number', 'payer_code', 'bill_date', 'bill_amount', 'outstanding_amount'],
        'sample': [
            ['BILL-2026-9001', 'MH-BLR-01', 'UHID-9001001', 'IP', 'CREDIT', 'IP-9001', 'PAY-STAR-01', '2026-09-01', 45000.00, 45000.00],
            ['BILL-2026-9002', 'MH-BLR-01', 'UHID-9001002', 'IP', 'CREDIT', 'IP-9002', 'PAY-CGHS-01', '2026-09-05', 28000.00, 28000.00]
        ],
        'key_fields': ['bill_number']
    },
    'bill_verifications': {
        'label': 'Bill Verification History',
        'headers': ['bill_number', 'verification_status', 'verification_remarks', 'rejection_reason'],
        'sample': [
            ['BILL-2026-9001', 'VERIFIED', 'Internal audit completed and verified', ''],
            ['BILL-2026-9002', 'REJECTED', 'Missing discharge summary', 'Discharge summary attached is incomplete']
        ],
        'key_fields': ['bill_number']
    },
    'bill_dispatch': {
        'label': 'Dispatch Details',
        'headers': ['bill_number', 'dispatch_date', 'dispatch_mode', 'courier_name', 'tracking_number', 'recipient_name', 'remarks'],
        'sample': [
            ['BILL-2026-9001', '2026-09-10', 'COURIER', 'BlueDart', 'BD-9908123', 'Star Health Desk', 'Dispatched physical dossier']
        ],
        'key_fields': ['bill_number']
    },
    'bill_queries': {
        'label': 'Payer Query Details',
        'headers': ['bill_number', 'query_code', 'query_date', 'query_type', 'query_description', 'raised_by_payer', 'due_date', 'query_status'],
        'sample': [
            ['BILL-2026-9002', 'QRY-2026-9002-01', '2026-09-08', 'DOCUMENTATION', 'Requested clarification on pharmacy implants', 'CGHS Desk', '2026-09-15', 'OPEN']
        ],
        'key_fields': ['query_code']
    },
    'bill_payments': {
        'label': 'Bill Payments & Settlement Details',
        'headers': ['bill_number', 'payment_date', 'payment_mode', 'utr_number', 'amount_received', 'short_fall_amount', 'disallowance_reason', 'remarks'],
        'sample': [
            ['BILL-2026-9001', '2026-09-11', 'NEFT/RTGS', 'UTR-990823412', 45000.00, 0.00, '', 'Full settlement received']
        ],
        'key_fields': ['utr_number', 'bill_number']
    }
}

def generate_template(category_key, fmt='xlsx'):
    """Generates dynamic Excel (.xlsx) or CSV template for a given data category."""
    cfg = DATA_CATEGORIES_CONFIG.get(category_key)
    if not cfg:
        raise ValueError(f"Invalid data category: {category_key}")

    headers = cfg['headers']
    sample_data = cfg['sample']

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in sample_data:
            writer.writerow(row)
        return output.getvalue().encode('utf-8'), 'text/csv', f"Template_{category_key}.csv"
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Data_Template"
        ws.append(headers)
        for row in sample_data:
            ws.append(row)
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', f"Template_{category_key}.xlsx"


def validate_admin_upload(category_key, file_storage):
    """
    Validates uploaded file against required headers, data types, and database master dependencies.
    Returns structured validation report.
    """
    cfg = DATA_CATEGORIES_CONFIG.get(category_key)
    if not cfg:
        return {'error': f"Unknown data category: {category_key}"}

    filename = file_storage.filename
    file_bytes = file_storage.read()

    # Parse file using parse_admin_file
    rows = parse_admin_file(file_bytes, filename)
    if not rows:
        return {'error': f"The uploaded file '{filename}' is empty or could not be parsed."}

    # Normalize headers
    expected_headers = cfg['headers']
    key_fields = cfg['key_fields']

    valid_records = []
    error_records = []
    seen_keys = set()

    for idx, row in enumerate(rows, start=2):
        cleaned_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k and v is not None}

        # Check mandatory key fields
        missing_keys = [k for k in key_fields if not cleaned_row.get(k)]
        if missing_keys:
            error_records.append({
                'row': idx,
                'data': cleaned_row,
                'reason': f"Missing mandatory field(s): {', '.join(missing_keys)}"
            })
            continue

        # Check in-file duplicates
        key_tuple = tuple(cleaned_row.get(k) for k in key_fields)
        if key_tuple in seen_keys:
            error_records.append({
                'row': idx,
                'data': cleaned_row,
                'reason': f"Duplicate record key within file: {key_tuple}"
            })
            continue
        seen_keys.add(key_tuple)

        # Master Dependency Validations
        dep_error = _validate_master_dependencies(category_key, cleaned_row)
        if dep_error:
            error_records.append({
                'row': idx,
                'data': cleaned_row,
                'reason': dep_error
            })
            continue

        valid_records.append({
            'row': idx,
            'data': cleaned_row
        })

    return {
        'data_category': category_key,
        'category_label': cfg['label'],
        'filename': filename,
        'total_records': len(rows),
        'valid_count': len(valid_records),
        'error_count': len(error_records),
        'duplicate_count': len(rows) - len(valid_records) - len(error_records),
        'valid_records': valid_records,
        'errors': error_records
    }


def _validate_master_dependencies(category_key, row):
    """Validates database master relationships (e.g. Unit must exist, Payer must exist)."""

    if category_key == 'hospital_payers':
        unit_code = row.get('unit_code')
        payer_code = row.get('payer_code')
        if not HospitalUnit.query.filter_by(unit_code=unit_code).first():
            return f"Hospital Unit '{unit_code}' does not exist in Hospital Unit Master."
        if not Payer.query.filter_by(payer_code=payer_code).first():
            return f"Payer Code '{payer_code}' does not exist in Payer Master."

    elif category_key == 'doctor_master':
        unit_code = row.get('unit_code')
        if unit_code and not HospitalUnit.query.filter_by(unit_code=unit_code).first():
            return f"Hospital Unit '{unit_code}' does not exist in Hospital Unit Master."

    elif category_key == 'bills':
        unit_code = row.get('unit_code')
        uhid = row.get('uhid')
        payer_code = row.get('payer_code')
        bill_type = row.get('bill_type', 'CREDIT').upper()

        if not HospitalUnit.query.filter_by(unit_code=unit_code).first():
            return f"Hospital Unit '{unit_code}' does not exist in Hospital Unit Master."
        if not Patient.query.filter_by(uhid=uhid).first():
            return f"Patient UHID '{uhid}' does not exist in Patient Master."
        if bill_type == 'CREDIT' and payer_code:
            if not Payer.query.filter_by(payer_code=payer_code).first():
                return f"Payer Code '{payer_code}' does not exist in Payer Master."

    elif category_key in ('bill_verifications', 'bill_dispatch', 'bill_queries', 'bill_payments'):
        bill_number = row.get('bill_number')
        if not Bill.query.filter_by(bill_number=bill_number).first():
            return f"Bill Number '{bill_number}' does not exist in Bills Master."

    return None


def execute_admin_import(category_key, valid_records, user_id, filename):
    """Executes database upserts for valid records and logs AdminUploadHistory."""
    success_count = 0
    fail_count = 0
    errors_list = []

    for item in valid_records:
        row = item['data']
        try:
            if category_key == 'hospital_units':
                u = HospitalUnit.query.filter_by(unit_code=row['unit_code']).first() or HospitalUnit(unit_code=row['unit_code'])
                u.hospital_name = row.get('hospital_name', u.hospital_name or '')
                u.address_line1 = row.get('address_line1', '')
                u.city = row.get('city', '')
                u.state = row.get('state', '')
                u.contact_no = row.get('contact_no', '')
                u.email = row.get('email', '')
                u.status = row.get('status', 'ACTIVE').upper()
                db.session.add(u)

            elif category_key == 'payers':
                p = Payer.query.filter_by(payer_code=row['payer_code']).first() or Payer(payer_code=row['payer_code'])
                p.payer_name = row.get('payer_name', p.payer_name or '')
                p.payer_type = row.get('payer_type', 'INSURANCE').upper()
                p.contact_person = row.get('contact_person', '')
                p.email = row.get('email', '')
                p.phone = row.get('phone', '')
                p.status = row.get('status', 'ACTIVE').upper()
                db.session.add(p)

            elif category_key == 'hospital_payers':
                unit = HospitalUnit.query.filter_by(unit_code=row['unit_code']).first()
                payer = Payer.query.filter_by(payer_code=row['payer_code']).first()
                
                hp = HospitalPayer.query.filter_by(unit_id=unit.unit_id, payer_id=payer.payer_id).first() or \
                     HospitalPayer(unit_id=unit.unit_id, payer_id=payer.payer_id)
                
                hp.payer_code_at_unit = row.get('payer_code_at_unit', '')
                hp.billing_type = row.get('billing_type', 'CREDIT').upper()
                hp.submission_tat_days = int(row.get('submission_tat_days', 15))
                
                # Process Monthly Submission (Yes/No / True/False / 1/0)
                monthly_val = str(row.get('monthly_submission', '')).strip().lower()
                hp.monthly_submission = monthly_val in ('yes', 'true', '1', 'y')

                hp.dispatch_mode = row.get('dispatch_mode', 'COURIER').upper()
                hp.status = row.get('status', 'ACTIVE').upper()
                db.session.add(hp)

            elif category_key == 'patients':
                pt = Patient.query.filter_by(uhid=row['uhid']).first() or Patient(uhid=row['uhid'])
                pt.patient_name = row.get('patient_name', pt.patient_name or '')
                pt.date_of_birth = row.get('date_of_birth', '')
                pt.gender = row.get('gender', 'OTHER').upper()
                pt.phone = row.get('phone', '')
                pt.email = row.get('email', '')
                db.session.add(pt)

            elif category_key == 'doctor_master':
                unit = HospitalUnit.query.filter_by(unit_code=row.get('unit_code')).first()
                d = DoctorMaster.query.filter_by(doctor_code=row['doctor_code']).first() or DoctorMaster(doctor_code=row['doctor_code'])
                d.doctor_name = row.get('doctor_name', '')
                d.normalized_doctor_name = d.doctor_name.lower().strip()
                d.department = row.get('department', '')
                d.specialization = row.get('specialization', '')
                d.unit_id = unit.unit_id if unit else None
                db.session.add(d)

            elif category_key == 'bills':
                unit = HospitalUnit.query.filter_by(unit_code=row['unit_code']).first()
                patient = Patient.query.filter_by(uhid=row['uhid']).first()
                payer = Payer.query.filter_by(payer_code=row.get('payer_code')).first() if row.get('payer_code') else None

                hp = None
                if unit and payer:
                    hp = HospitalPayer.query.filter_by(unit_id=unit.unit_id, payer_id=payer.payer_id).first()

                b = Bill.query.filter_by(bill_number=row['bill_number']).first() or Bill(bill_number=row['bill_number'])
                b.unit_id = unit.unit_id
                b.patient_id = patient.patient_id
                b.patient_name_snapshot = patient.patient_name
                b.encounter_type = row.get('encounter_type', 'IP').upper()
                b.bill_type = row.get('bill_type', 'CREDIT').upper()
                b.ip_number = row.get('ip_number', '')
                b.payer_id = payer.payer_id if payer else None
                b.hospital_payer_id = hp.hospital_payer_id if hp else None
                b.bill_date = row.get('bill_date', datetime.now().strftime('%Y-%m-%d'))
                b.bill_amount = float(row.get('bill_amount', 0))
                b.outstanding_amount = float(row.get('outstanding_amount', b.bill_amount))
                b.created_by = user_id
                b.update_lifecycle_status()
                db.session.add(b)

            elif category_key == 'bill_verifications':
                bill = Bill.query.filter_by(bill_number=row['bill_number']).first()
                v = BillVerification(
                    bill_id=bill.bill_id,
                    verification_status=row.get('verification_status', 'VERIFIED').upper(),
                    verified_by=user_id,
                    verification_remarks=row.get('verification_remarks', ''),
                    rejection_reason=row.get('rejection_reason', '')
                )
                db.session.add(v)
                bill.update_lifecycle_status()

            elif category_key == 'bill_dispatch':
                bill = Bill.query.filter_by(bill_number=row['bill_number']).first()
                d = BillDispatch(
                    bill_id=bill.bill_id,
                    bill_number=bill.bill_number,
                    dispatch_date=row.get('dispatch_date', datetime.now().strftime('%Y-%m-%d')),
                    dispatch_mode=row.get('dispatch_mode', 'COURIER').upper(),
                    courier_name=row.get('courier_name', ''),
                    tracking_number=row.get('tracking_number', ''),
                    recipient_name=row.get('recipient_name', ''),
                    dispatched_by=user_id,
                    remarks=row.get('remarks', '')
                )
                db.session.add(d)
                bill.update_lifecycle_status()

            elif category_key == 'bill_queries':
                bill = Bill.query.filter_by(bill_number=row['bill_number']).first()
                q = BillQuery(
                    bill_id=bill.bill_id,
                    query_code=row.get('query_code', f"QRY-{bill.bill_number}"),
                    query_date=row.get('query_date', datetime.now().strftime('%Y-%m-%d')),
                    query_type=row.get('query_type', 'DOCUMENTATION').upper(),
                    query_description=row.get('query_description', 'Payer query raised'),
                    raised_by_payer=row.get('raised_by_payer', ''),
                    query_status=row.get('query_status', 'OPEN').upper(),
                    assigned_to=user_id,
                    due_date=row.get('due_date', '')
                )
                db.session.add(q)
                bill.update_lifecycle_status()

            elif category_key == 'bill_payments':
                bill = Bill.query.filter_by(bill_number=row['bill_number']).first()
                amt = float(row.get('amount_received', 0))
                p = BillPayment(
                    bill_id=bill.bill_id,
                    payment_date=row.get('payment_date', datetime.now().strftime('%Y-%m-%d')),
                    payment_mode=row.get('payment_mode', 'NEFT/RTGS').upper(),
                    utr_number=row.get('utr_number', 'UTR-UNKNOWN'),
                    amount_received=amt,
                    short_fall_amount=float(row.get('short_fall_amount', 0)),
                    disallowance_reason=row.get('disallowance_reason', ''),
                    processed_by=user_id,
                    remarks=row.get('remarks', '')
                )
                bill.outstanding_amount = max(0.0, bill.outstanding_amount - amt)
                db.session.add(p)
                bill.update_lifecycle_status()

            db.session.commit()
            success_count += 1
        except Exception as e:
            db.session.rollback()
            fail_count += 1
            errors_list.append({'row': item['row'], 'reason': str(e)})

    # Record Admin Upload History
    history = AdminUploadHistory(
        data_category=category_key,
        file_name=filename,
        total_records=len(valid_records),
        success_records=success_count,
        failed_records=fail_count,
        duplicate_records=0,
        uploaded_by=user_id,
        error_summary_json=json.dumps(errors_list)
    )
    db.session.add(history)
    db.session.commit()

    return {
        'history_id': history.history_id,
        'success_count': success_count,
        'failed_count': fail_count,
        'total_attempted': len(valid_records)
    }
