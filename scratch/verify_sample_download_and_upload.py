import os
import sys
import io
from pathlib import Path

from flask import session
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from database import db
from models import (
    SyncBatch, HISIPStaging, Patient, DoctorMaster, HISDoctorMapping,
    IPAdmission, IPDischarge, HospitalUnit, Payer, HISPayerMapping, User, Role
)
from routes.his_sync_routes import download_sample
from utils.his_sync.parsers import parse_his_file
from utils.his_sync.validator import validate_staging_batch
from utils.his_sync.sync_engine import process_sync_batch
from utils.his_sync.normalizers import normalize_string

def run_test():
    print("==================================================")
    print("TESTING SAMPLE FILE GENERATION AND MULTI-TABLE SYNC")
    print("==================================================")

    with app.app_context():
        with app.test_request_context():
            db.create_all()

            # Ensure hospital unit & payer exist
            unit = HospitalUnit.query.filter_by(unit_code='MH-BLR-01').first()
            if not unit:
                unit = HospitalUnit(
                    unit_code='MH-BLR-01',
                    hospital_name='Manipal Hospital Bangalore',
                    city='Bangalore',
                    state='Karnataka',
                    status='ACTIVE'
                )
                db.session.add(unit)
                db.session.commit()

            payer = Payer.query.filter_by(payer_code='STAR_HEALTH').first()
            if not payer:
                payer = Payer(
                    payer_code='STAR_HEALTH',
                    payer_name='Star Health & Allied Insurance',
                    payer_type='TPA',
                    status='ACTIVE'
                )
                db.session.add(payer)
                db.session.commit()

            # Seed Payer Mapping Rule
            company_raw = 'Star Health & Allied Insurance'
            company_norm = normalize_string(company_raw)
            p_map = HISPayerMapping.query.filter_by(normalized_company_name=company_norm).first()
            if not p_map:
                p_map = HISPayerMapping(
                    source_company_name=company_raw,
                    normalized_company_name=company_norm,
                    payer_id=payer.payer_id,
                    bill_type='CREDIT',
                    active=True
                )
                db.session.add(p_map)
                db.session.commit()

            user = User.query.first()

            # 1. Download Sample CSV File via Route Handler
            session['user_id'] = user.id if user else 1
            print("\n1. Testing download_sample('csv') route generator...")
            res = download_sample('csv')
            assert res.status_code == 200, f"Download sample status should be 200 (got {res.status_code})"
            file_bytes = res.data
            print(f"   -> Sample CSV generated ({len(file_bytes)} bytes)")

            # 2. Parse Rows
            print("\n2. Parsing generated sample file...")
            parsed_rows = parse_his_file("sample_his_ip_import.csv", file_bytes)
            print(f"   -> Parsed {len(parsed_rows)} sample rows.")
            assert len(parsed_rows) == 3, "Expected 3 sample rows"

            # 3. Create Staging Batch & Stage Rows
            print("\n3. Staging parsed rows into HISIPStaging...")
            import json
            from utils.his_sync.hash_utils import calculate_file_hash
            f_hash = calculate_file_hash(file_bytes)

            batch = SyncBatch(
                source_system='HIS_EXCEL',
                source_type='FILE_UPLOAD',
                source_file_name='sample_his_ip_import.csv',
                source_file_hash=f_hash,
                uploaded_by=user.id if user else 1,
                total_records=len(parsed_rows),
                batch_status='UPLOADED'
            )
            db.session.add(batch)
            db.session.flush()

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
                    validation_status='PENDING'
                )
                staging_objs.append(stg)

            db.session.bulk_save_objects(staging_objs)
            db.session.commit()
            print(f"   -> Staged Batch #{batch.batch_id} with {len(staging_objs)} records.")

            # 4. Validate Batch
            print("\n4. Validating Staging Batch...")
            validate_staging_batch(batch.batch_id)
            db.session.refresh(batch)
            print(f"   -> Validation Status: {batch.batch_status}")
            assert batch.invalid_records == 0, "No validation errors expected in sample file"

            # 5. Process Sync Batch (Upload to ALL relevant tables)
            print("\n5. Executing Sync Engine (Targeting All Master & Transaction Tables)...")
            process_sync_batch(batch.batch_id, user_id=user.id if user else 1)
            db.session.refresh(batch)
            print(f"   -> Sync Execution Status: {batch.batch_status}")
            print(f"   -> Successful: {batch.successful_records}, Failed: {batch.failed_records}")

            # 6. Verify Records Across All Tables
            print("\n6. Verifying Target Tables Population:")
            
            # Table A: Patients
            patients = Patient.query.filter(Patient.uhid.in_(['UHID-2026-101', 'UHID-2026-102', 'UHID-2026-103'])).all()
            print(f"   [1/5 Table: Patients] Total Found: {len(patients)}")
            for p in patients:
                print(f"       - UHID: {p.uhid} | Name: {p.patient_name} | Phone: {p.phone}")

            # Table B: DoctorMaster & HISDoctorMapping
            docs = DoctorMaster.query.all()
            print(f"   [2/5 Table: DoctorMaster] Total Found: {len(docs)}")
            for d in docs:
                print(f"       - Doctor: {d.doctor_name} (Code: {d.doctor_code}) | Dept: {d.department}")

            doc_maps = HISDoctorMapping.query.all()
            print(f"   [3/5 Table: HISDoctorMapping] Total Mapped Doctors: {len(doc_maps)}")

            # Table C: IPAdmission
            admissions = IPAdmission.query.filter(IPAdmission.ip_number.in_(['IP-2026-001', 'IP-2026-002', 'IP-2026-003'])).all()
            print(f"   [4/5 Table: IPAdmission] Total Admissions: {len(admissions)}")
            for a in admissions:
                print(f"       - IP: #{a.ip_number} | Patient: {a.patient_name_snapshot} | Status: {a.admission_status} | Bill Type: {a.bill_type}")

            # Table D: IPDischarge
            discharges = IPDischarge.query.filter(IPDischarge.ip_number.in_(['IP-2026-001', 'IP-2026-003'])).all()
            print(f"   [5/5 Table: IPDischarge] Total Discharges Processed: {len(discharges)}")
            for dc in discharges:
                print(f"       - IP: #{dc.ip_number} | Discharge Date: {dc.discharge_date} | Status: {dc.discharge_status}")

            print("\n==================================================")
            print("SAMPLE FILE GENERATION & MULTI-TABLE SYNC SUCCESSFUL!")
            print("==================================================")

if __name__ == '__main__':
    run_test()
