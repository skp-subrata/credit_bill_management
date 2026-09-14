import json
import io
import csv
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response
from database import db
from models import (
    SyncBatch, HISIPStaging, HISPayerMapping, DoctorMaster, HISDoctorMapping, 
    HISSyncSettings, HospitalUnit, Payer, Patient, IPAdmission
)
from utils.auth import login_required, permission_required, get_current_user
from utils.his_sync.hash_utils import calculate_file_hash
from utils.his_sync.parsers import parse_his_file
from utils.his_sync.normalizers import normalize_string
from utils.his_sync.validator import validate_staging_batch
from utils.his_sync.sync_engine import process_sync_batch
from utils.audit import log_audit
from config import Config

his_sync_bp = Blueprint('his_sync', __name__, url_prefix='/his-sync')

# --- 1. UPLOAD & PREVIEW SCREEN ---
@his_sync_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@permission_required('manage_system')
def upload():
    if request.method == 'POST':
        source_system = request.form.get('source_system', 'HIS_EXCEL')
        sync_mode = request.form.get('sync_mode', 'INCREMENTAL_SYNC')
        auto_sync = request.form.get('auto_sync') == 'on'
        remarks = request.form.get('remarks', '').strip()

        file_obj = request.files.get('file')
        if not file_obj or not file_obj.filename:
            flash('Please select an Excel (.xlsx) or CSV (.csv) file to upload.', 'error')
            return redirect(url_for('his_sync.upload'))

        file_bytes = file_obj.read()
        file_hash = calculate_file_hash(file_bytes)

        # Check Duplicate File Upload
        existing_batch = SyncBatch.query.filter_by(source_file_hash=file_hash).first()
        if existing_batch:
            flash(f"Duplicate file warning! This exact file was previously uploaded in Batch #{existing_batch.batch_id} on {existing_batch.uploaded_at.strftime('%Y-%m-%d %H:%M')}.", 'warning')

        # Parse Rows
        try:
            parsed_rows = parse_his_file(file_obj.filename, file_bytes)
        except Exception as err:
            flash(f"Could not parse file '{file_obj.filename}': {str(err)}. Please ensure it is a valid Excel (.xlsx) or CSV (.csv) file.", 'error')
            return redirect(url_for('his_sync.upload'))

        if not parsed_rows:
            flash(f"The file '{file_obj.filename}' is empty, corrupted, or missing expected 36 HIS headers.", 'error')
            return redirect(url_for('his_sync.upload'))

        # Create Sync Batch
        batch = SyncBatch(
            source_system=source_system,
            source_type='FILE_UPLOAD',
            source_file_name=file_obj.filename,
            source_file_hash=file_hash,
            uploaded_by=session.get('user_id'),
            total_records=len(parsed_rows),
            batch_status='UPLOADED',
            remarks=remarks
        )
        db.session.add(batch)
        db.session.flush()

        # Bulk Insert Raw Staging Rows
        staging_objs = []
        for idx, r in enumerate(parsed_rows, start=1):
            stg = HISIPStaging(
                batch_id=batch.batch_id,
                row_number=idx,
                uhid=r.get('UHID', ''),
                patientname=r.get('PATIENTNAME', ''),
                ipnumber=r.get('IPNUMBER', ''),
                gender=r.get('GENDER', ''),
                age=r.get('AGE', ''),
                admitteddate=r.get('ADMITTEDDATE', ''),
                planingdate=r.get('PLANINGDATE', ''),
                closingdate=r.get('CLOSINGDATE', ''),
                primarydoctor=r.get('PRIMARYDOCTOR', ''),
                nursecheckedouttime=r.get('NURSECHECKEDOUTTIME', ''),
                admiting_doctor=r.get('ADMITING_DOCTOR', ''),
                admiting_doctor_dept=r.get('ADMITING_DOCTOR_DEPT', ''),
                treating_doctor=r.get('TREATING_DOCTOR', ''),
                treating_doctor_dept=r.get('TREATING_DOCTOR_DEPT', ''),
                interimdate=r.get('INTERIMDATE', ''),
                discharge_billdate=r.get('DISCHARGE_BILLDATE', ''),
                bed_occupied=r.get('BED_OCCUPIED', ''),
                specialization=r.get('SPECIALIZATION', ''),
                specializationdesc=r.get('SPECIALIZATIONDESC', ''),
                bedno=r.get('BEDNO', ''),
                bedtype=r.get('BEDTYPE', ''),
                billablebed=r.get('BILLABLEBED', ''),
                bednumber=r.get('BEDNUMBER', ''),
                wardname=r.get('WARDNAME', ''),
                companyname=r.get('COMPANYNAME', ''),
                refraldoctor=r.get('REFRALDOCTOR', ''),
                currentstatus=r.get('CURRENTSTATUS', ''),
                reasonandremarks=r.get('REASONANDREMARKS', ''),
                contactno=r.get('CONTACTNO', ''),
                address1=r.get('ADDRESS1', ''),
                countryname=r.get('COUNTRYNAME', ''),
                statename=r.get('STATENAME', ''),
                cityname=r.get('CITYNAME', ''),
                districtname=r.get('DISTRICTNAME', ''),
                createdby=r.get('CREATEDBY', ''),
                locationid=r.get('LOCATIONID', ''),
                raw_payload=json.dumps(r),
                validation_status='PENDING'
            )
            staging_objs.append(stg)

        db.session.bulk_save_objects(staging_objs)
        db.session.commit()

        # Run Staging Validation Engine
        validate_staging_batch(batch.batch_id)

        log_audit('UPLOAD_HIS_FILE', 'SyncBatch', batch.batch_id, None, {'file_name': file_obj.filename, 'total_rows': len(parsed_rows)})
        flash(f"File '{file_obj.filename}' staged & validated! Batch #{batch.batch_id} ({len(parsed_rows)} records).", 'success')
        # Auto Sync Option Execution
        if auto_sync:
            process_sync_batch(batch.batch_id, user_id=session.get('user_id'))
            flash(f"File '{file_obj.filename}' staged, validated & automatically synced! Batch #{batch.batch_id} ({len(parsed_rows)} records processed).", 'success')
        else:
            flash(f"File '{file_obj.filename}' staged & validated! Batch #{batch.batch_id} ({len(parsed_rows)} records). Click 'Execute Sync Engine' to sync into target tables.", 'success')

        log_audit('UPLOAD_HIS_FILE', 'SyncBatch', batch.batch_id, None, {'file_name': file_obj.filename, 'total_rows': len(parsed_rows), 'auto_sync': auto_sync})
        return redirect(url_for('his_sync.batch_detail', batch_id=batch.batch_id))

    units = HospitalUnit.query.filter_by(status='ACTIVE').all()
    return render_template('his_sync/upload.html', units=units)

# --- SAMPLE FILE GENERATOR & DOWNLOAD ROUTE ---
@his_sync_bp.route('/download-sample', defaults={'fmt': 'xlsx'})
@his_sync_bp.route('/download-sample/<fmt>')
@login_required
def download_sample(fmt):
    headers = [
        'UHID', 'PATIENTNAME', 'IPNUMBER', 'GENDER', 'AGE',
        'ADMITTEDDATE', 'PLANINGDATE', 'CLOSINGDATE', 'PRIMARYDOCTOR', 'NURSECHECKEDOUTTIME',
        'ADMITING_DOCTOR', 'ADMITING_DOCTOR_DEPT', 'TREATING_DOCTOR', 'TREATING_DOCTOR_DEPT',
        'INTERIMDATE', 'DISCHARGE_BILLDATE', 'BED_OCCUPIED', 'SPECIALIZATION', 'SPECIALIZATIONDESC',
        'BEDNO', 'BEDTYPE', 'BILLABLEBED', 'BEDNUMBER', 'WARDNAME',
        'COMPANYNAME', 'REFRALDOCTOR', 'CURRENTSTATUS', 'REASONANDREMARKS', 'CONTACTNO',
        'ADDRESS1', 'COUNTRYNAME', 'STATENAME', 'CITYNAME', 'DISTRICTNAME',
        'CREATEDBY', 'LOCATIONID'
    ]

    unit = HospitalUnit.query.filter_by(status='ACTIVE').first()
    loc_id = unit.unit_code if unit else 'MH-BLR-01'

    sample_rows = [
        {
            'UHID': 'UHID-2026-101', 'PATIENTNAME': 'SUPRITI SWAIN', 'IPNUMBER': 'IP-2026-001',
            'GENDER': 'Female', 'AGE': '34 Yrs', 'ADMITTEDDATE': '01.09.2026 10:30',
            'PLANINGDATE': '04.09.2026 12:00', 'CLOSINGDATE': '04.09.2026 15:50',
            'PRIMARYDOCTOR': 'Dr. Rajesh Sharma', 'NURSECHECKEDOUTTIME': '04.09.2026 15:00',
            'ADMITING_DOCTOR': 'Dr. Rajesh Sharma', 'ADMITING_DOCTOR_DEPT': 'Cardiology',
            'TREATING_DOCTOR': 'Dr. Rajesh Sharma', 'TREATING_DOCTOR_DEPT': 'Cardiology',
            'INTERIMDATE': '', 'DISCHARGE_BILLDATE': '04.09.2026 15:30', 'BED_OCCUPIED': 'Bed-102',
            'SPECIALIZATION': 'CARD', 'SPECIALIZATIONDESC': 'Cardiology', 'BEDNO': '102',
            'BEDTYPE': 'Deluxe', 'BILLABLEBED': 'Deluxe', 'BEDNUMBER': '102', 'WARDNAME': 'Cardiac ICU',
            'COMPANYNAME': 'Star Health & Allied Insurance', 'REFRALDOCTOR': 'Dr. Mehta',
            'CURRENTSTATUS': 'DISCHARGED', 'REASONANDREMARKS': 'Routine discharge post recovery',
            'CONTACTNO': '9876543210', 'ADDRESS1': '124 MG Road', 'COUNTRYNAME': 'India',
            'STATENAME': 'Karnataka', 'CITYNAME': 'Bangalore', 'DISTRICTNAME': 'Bangalore Urban',
            'CREATEDBY': 'HIS_ADMIN', 'LOCATIONID': loc_id
        },
        {
            'UHID': 'UHID-2026-102', 'PATIENTNAME': 'AMIT KUMAR', 'IPNUMBER': 'IP-2026-002',
            'GENDER': 'Male', 'AGE': '45 Yrs', 'ADMITTEDDATE': '05.09.2026 14:15',
            'PLANINGDATE': '', 'CLOSINGDATE': '', 'PRIMARYDOCTOR': 'Dr. Anita Verma',
            'NURSECHECKEDOUTTIME': '', 'ADMITING_DOCTOR': 'Dr. Anita Verma',
            'ADMITING_DOCTOR_DEPT': 'Neurology', 'TREATING_DOCTOR': 'Dr. Anita Verma',
            'TREATING_DOCTOR_DEPT': 'Neurology', 'INTERIMDATE': '', 'DISCHARGE_BILLDATE': '',
            'BED_OCCUPIED': 'Bed-204', 'SPECIALIZATION': 'NEURO', 'SPECIALIZATIONDESC': 'Neurology',
            'BEDNO': '204', 'BEDTYPE': 'Semi-Private', 'BILLABLEBED': 'Semi-Private',
            'BEDNUMBER': '204', 'WARDNAME': 'Neuro Ward', 'COMPANYNAME': 'Star Health & Allied Insurance',
            'REFRALDOCTOR': '', 'CURRENTSTATUS': 'ADMITTED', 'REASONANDREMARKS': 'Under observation',
            'CONTACTNO': '9123456789', 'ADDRESS1': '56 Indiranagar', 'COUNTRYNAME': 'India',
            'STATENAME': 'Karnataka', 'CITYNAME': 'Bangalore', 'DISTRICTNAME': 'Bangalore Urban',
            'CREATEDBY': 'HIS_ADMIN', 'LOCATIONID': loc_id
        },
        {
            'UHID': 'UHID-2026-103', 'PATIENTNAME': 'PRIYA SHARMA', 'IPNUMBER': 'IP-2026-003',
            'GENDER': 'Female', 'AGE': '28 Yrs', 'ADMITTEDDATE': '06.09.2026 09:00',
            'PLANINGDATE': '08.09.2026 11:00', 'CLOSINGDATE': '08.09.2026 14:00',
            'PRIMARYDOCTOR': 'Dr. Suresh Menon', 'NURSECHECKEDOUTTIME': '08.09.2026 13:30',
            'ADMITING_DOCTOR': 'Dr. Suresh Menon', 'ADMITING_DOCTOR_DEPT': 'Orthopedics',
            'TREATING_DOCTOR': 'Dr. Suresh Menon', 'TREATING_DOCTOR_DEPT': 'Orthopedics',
            'INTERIMDATE': '', 'DISCHARGE_BILLDATE': '08.09.2026 14:00', 'BED_OCCUPIED': 'Bed-301',
            'SPECIALIZATION': 'ORTHO', 'SPECIALIZATIONDESC': 'Orthopedics', 'BEDNO': '301',
            'BEDTYPE': 'General Ward', 'BILLABLEBED': 'General Ward', 'BEDNUMBER': '301',
            'WARDNAME': 'Ortho Ward', 'COMPANYNAME': 'CASH', 'REFRALDOCTOR': '',
            'CURRENTSTATUS': 'DISCHARGED', 'REASONANDREMARKS': 'Fracture treatment complete',
            'CONTACTNO': '9988776655', 'ADDRESS1': '88 Koramangala', 'COUNTRYNAME': 'India',
            'STATENAME': 'Karnataka', 'CITYNAME': 'Bangalore', 'DISTRICTNAME': 'Bangalore Urban',
            'CREATEDBY': 'HIS_ADMIN', 'LOCATIONID': loc_id
        }
    ]

    if fmt == 'xlsx':
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "HIS_IP_Import"
            ws.append(headers)
            for r in sample_rows:
                ws.append([r.get(h, '') for h in headers])

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': 'attachment; filename="sample_his_ip_import.xlsx"'}
            )
        except Exception:
            pass

    # Fallback / CSV format
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for r in sample_rows:
        writer.writerow(r)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename="sample_his_ip_import.csv"'}
    )

# --- 2. BATCH DETAIL & CONFIRM SYNC ---
@his_sync_bp.route('/batches/<int:batch_id>')
@login_required
@permission_required('manage_system')
def batch_detail(batch_id):
    batch = SyncBatch.query.get_or_404(batch_id)
    staging_preview = HISIPStaging.query.filter_by(batch_id=batch_id).limit(50).all()
    return render_template('his_sync/batch_detail.html', batch=batch, staging=staging_preview)

@his_sync_bp.route('/batches/<int:batch_id>/execute', methods=['POST'])
@login_required
@permission_required('manage_system')
def execute_sync(batch_id):
    batch = SyncBatch.query.get_or_404(batch_id)
    process_sync_batch(batch.batch_id, user_id=session.get('user_id'))
    flash(f"Sync Engine execution completed for Batch #{batch.batch_id}! Successful: {batch.successful_records}, Failed: {batch.failed_records}.", 'success')
    return redirect(url_for('his_sync.batch_detail', batch_id=batch.batch_id))

# --- 3. SYNC HISTORY ---
@his_sync_bp.route('/history')
@login_required
@permission_required('manage_system')
def history():
    page = request.args.get('page', 1, type=int)
    batches_pagination = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    return render_template('his_sync/history.html', batches=batches_pagination.items, pagination=batches_pagination)

# --- 4. VALIDATION ERRORS & REPROCESS ---
@his_sync_bp.route('/errors')
@login_required
@permission_required('manage_system')
def errors():
    page = request.args.get('page', 1, type=int)
    batch_id = request.args.get('batch_id', type=int)
    query = HISIPStaging.query.filter(HISIPStaging.validation_status.in_(['INVALID', 'MAPPING_PENDING']))
    if batch_id:
        query = query.filter_by(batch_id=batch_id)
    errors_pagination = query.order_by(HISIPStaging.staging_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    batches = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).all()
    return render_template('his_sync/errors.html', error_rows=errors_pagination.items, pagination=errors_pagination, batches=batches, selected_batch_id=batch_id)

# --- 5. RECONCILIATION REPORT ---
@his_sync_bp.route('/reconciliation')
@login_required
@permission_required('manage_system')
def reconciliation():
    batch_id = request.args.get('batch_id', type=int)
    batch = SyncBatch.query.get(batch_id) if batch_id else SyncBatch.query.order_by(SyncBatch.batch_id.desc()).first()
    batches = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).all()

    recon_data = None
    if batch:
        recon_data = {
            "source_records": batch.total_records,
            "new_records": batch.new_records,
            "updated_records": batch.updated_records,
            "unchanged_records": batch.unchanged_records,
            "invalid_records": batch.invalid_records,
            "mapping_pending": batch.mapping_pending_records,
            "failed_records": batch.failed_records,
            "successful_records": batch.successful_records
        }

    return render_template('his_sync/reconciliation.html', recon=recon_data, batch=batch, batches=batches)

# --- 6. PAYER & DOCTOR MASTER MAPPINGS ---
@his_sync_bp.route('/mappings', methods=['GET', 'POST'])
@login_required
@permission_required('manage_system')
def mappings():
    if request.method == 'POST':
        source_company_name = request.form.get('source_company_name', '').strip()
        payer_id = int(request.form.get('payer_id'))
        bill_type = request.form.get('bill_type', 'CREDIT')
        unit_id = request.form.get('unit_id')

        norm_name = normalize_string(source_company_name)
        existing = HISPayerMapping.query.filter_by(normalized_company_name=norm_name).first()
        if existing:
            existing.payer_id = payer_id
            existing.bill_type = bill_type
            existing.unit_id = int(unit_id) if unit_id else None
            existing.active = True
            flash(f"Updated mapping rule for '{source_company_name}'.", 'success')
        else:
            mapping = HISPayerMapping(
                source_company_name=source_company_name,
                normalized_company_name=norm_name,
                payer_id=payer_id,
                bill_type=bill_type,
                unit_id=int(unit_id) if unit_id else None,
                active=True
            )
            db.session.add(mapping)
            flash(f"Created new mapping rule for '{source_company_name}'.", 'success')

        db.session.commit()
        return redirect(url_for('his_sync.mappings'))

    page = request.args.get('page', 1, type=int)
    mappings_pagination = HISPayerMapping.query.order_by(HISPayerMapping.mapping_id.desc()).paginate(page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False)
    payers = Payer.query.filter_by(status='ACTIVE').all()
    units = HospitalUnit.query.filter_by(status='ACTIVE').all()

    return render_template('his_sync/mappings.html', mappings=mappings_pagination.items, pagination=mappings_pagination, payers=payers, units=units)

# --- 7. SYNC SETTINGS ---
@his_sync_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@permission_required('manage_system')
def settings():
    setting = HISSyncSettings.query.first()
    if not setting:
        setting = HISSyncSettings(sync_mode='INCREMENTAL_SYNC')
        db.session.add(setting)
        db.session.commit()

    if request.method == 'POST':
        setting.sync_mode = request.form.get('sync_mode', 'INCREMENTAL_SYNC')
        setting.auto_sync_enabled = request.form.get('auto_sync_enabled') == 'on'
        setting.schedule_frequency = request.form.get('schedule_frequency', 'HOURLY')
        setting.email_ingestion_enabled = request.form.get('email_ingestion_enabled') == 'on'
        setting.email_folder = request.form.get('email_folder', 'Inbox/HIS')
        db.session.commit()
        flash('HIS Synchronization Settings updated!', 'success')
        return redirect(url_for('his_sync.settings'))

    return render_template('his_sync/settings.html', setting=setting)

# --- REST APIs (/api/v1/his-sync) ---
@his_sync_bp.route('/api/v1/batches', methods=['GET'])
@login_required
def api_list_batches():
    batches = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).limit(50).all()
    return jsonify([{
        "batch_id": b.batch_id,
        "file_name": b.source_file_name,
        "total": b.total_records,
        "status": b.batch_status,
        "uploaded_at": b.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')
    } for b in batches])
