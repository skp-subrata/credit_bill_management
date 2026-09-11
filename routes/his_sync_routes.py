import json
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

his_sync_bp = Blueprint('his_sync', __name__, url_prefix='/his-sync')

# --- 1. UPLOAD & PREVIEW SCREEN ---
@his_sync_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@permission_required('manage_system')
def upload():
    if request.method == 'POST':
        source_system = request.form.get('source_system', 'HIS_EXCEL')
        sync_mode = request.form.get('sync_mode', 'INCREMENTAL_SYNC')
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
        parsed_rows = parse_his_file(file_obj.filename, file_bytes)
        if not parsed_rows:
            flash('The uploaded file is empty or missing expected 36 HIS headers.', 'error')
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
        return redirect(url_for('his_sync.batch_detail', batch_id=batch.batch_id))

    units = HospitalUnit.query.filter_by(status='ACTIVE').all()
    return render_template('his_sync/upload.html', units=units)

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
    batches = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).all()
    return render_template('his_sync/history.html', batches=batches)

# --- 4. VALIDATION ERRORS & REPROCESS ---
@his_sync_bp.route('/errors')
@login_required
@permission_required('manage_system')
def errors():
    batch_id = request.args.get('batch_id', type=int)
    query = HISIPStaging.query.filter(HISIPStaging.validation_status.in_(['INVALID', 'MAPPING_PENDING']))
    if batch_id:
        query = query.filter_by(batch_id=batch_id)
    error_rows = query.order_by(HISIPStaging.staging_id.desc()).limit(200).all()
    batches = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).all()
    return render_template('his_sync/errors.html', error_rows=error_rows, batches=batches, selected_batch_id=batch_id)

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

    payer_mappings = HISPayerMapping.query.order_by(HISPayerMapping.mapping_id.desc()).all()
    payers = Payer.query.filter_by(status='ACTIVE').all()
    units = HospitalUnit.query.filter_by(status='ACTIVE').all()

    return render_template('his_sync/mappings.html', mappings=payer_mappings, payers=payers, units=units)

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
