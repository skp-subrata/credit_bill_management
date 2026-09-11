import os
import sys
import io
import csv
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from database import db
from models import (
    SyncBatch, HISIPStaging, HISPayerMapping, HISSyncSettings,
    HospitalUnit, Payer, Patient, IPAdmission, User, Role
)
from utils.his_sync.hash_utils import calculate_file_hash
from utils.his_sync.parsers import parse_his_file
from utils.his_sync.validator import validate_staging_batch
from utils.his_sync.sync_engine import process_sync_batch
from utils.his_sync.normalizers import normalize_string

def run_verification():
    print("==================================================")
    print("VERIFYING HIS DATA IMPORT AND SYNC MODULE")
    print("==================================================")

    with app.app_context():
        with app.test_request_context():
            # 1. Create DB Tables
            print("\n1. Ensuring database tables are created...")
            db.create_all()

            # Ensure schema migration for newly added columns in SQLite
            with db.engine.connect() as conn:
                col_rows = conn.execute(db.text("PRAGMA table_info(ip_admissions)")).fetchall()
                columns = [r[1] for r in col_rows] if col_rows else []
                if columns and 'billing_eligible' not in columns:
                    conn.execute(db.text("ALTER TABLE ip_admissions ADD COLUMN billing_eligible BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("   -> Applied schema migration: Added billing_eligible to ip_admissions.")

            print("   -> Database schema initialized.")

            # 2. Check / Seed Initial Hospital Unit & Master Payer & Payer Mapping
            print("\n2. Checking baseline master records...")
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
                print(f"   -> Seeded Unit: {unit.hospital_name} (ID: {unit.unit_id})")
            else:
                print(f"   -> Found Existing Unit: {unit.hospital_name} (ID: {unit.unit_id})")

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
                print(f"   -> Seeded Payer: {payer.payer_name} (ID: {payer.payer_id})")
            else:
                print(f"   -> Found Existing Payer: {payer.payer_name} (ID: {payer.payer_id})")

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
                print(f"   -> Seeded Payer Mapping: '{company_raw}' => Payer #{payer.payer_id}")
            else:
                print(f"   -> Found Payer Mapping: '{company_raw}' => Payer #{payer.payer_id}")

            # User for Audit & Upload
            user = User.query.first()
            if not user:
                role = Role.query.filter_by(role_code='super_admin').first()
                if not role:
                    role = Role(role_code='super_admin', role_name='Super Admin', description='Super Admin')
                    db.session.add(role)
                    db.session.flush()
                user = User(
                    employee_id='EMP-001',
                    name='System Admin',
                    email='admin@hospital.com',
                    password_hash='pbkdf2:sha256:...',
                    role_id=role.id,
                    hospital_unit_id=unit.unit_id
                )
                db.session.add(user)
                db.session.commit()

            # 3. Generate Mock HIS CSV file with 36 columns
            print("\n3. Generating mock 36-column HIS CSV file...")
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

            mock_rows = [
                {
                    'UHID': 'UHID-2026-001',
                    'PATIENTNAME': 'SUPRITI   SWAIN',
                    'IPNUMBER': 'IP-99001',
                    'GENDER': 'Female',
                    'AGE': '34 Yrs',
                    'ADMITTEDDATE': '01.09.2026 10:30',
                    'PLANINGDATE': '04.09.2026 12:00',
                    'CLOSINGDATE': '04.09.2026 15:50',
                    'PRIMARYDOCTOR': 'Dr. Rajesh Sharma',
                    'NURSECHECKEDOUTTIME': '04.09.2026 15:00',
                    'ADMITING_DOCTOR': 'Dr. Rajesh Sharma',
                    'ADMITING_DOCTOR_DEPT': 'Cardiology',
                    'TREATING_DOCTOR': 'Dr. Rajesh Sharma',
                    'TREATING_DOCTOR_DEPT': 'Cardiology',
                    'INTERIMDATE': '',
                    'DISCHARGE_BILLDATE': '04.09.2026 15:30',
                    'BED_OCCUPIED': 'Bed-102',
                    'SPECIALIZATION': 'CARD',
                    'SPECIALIZATIONDESC': 'Cardiology',
                    'BEDNO': '102',
                    'BEDTYPE': 'Deluxe',
                    'BILLABLEBED': 'Deluxe',
                    'BEDNUMBER': '102',
                    'WARDNAME': 'Cardiac ICU',
                    'COMPANYNAME': 'Star Health & Allied Insurance',
                    'REFRALDOCTOR': 'Dr. Mehta',
                    'CURRENTSTATUS': 'DISCHARGED',
                    'REASONANDREMARKS': 'Routine discharge post recovery',
                    'CONTACTNO': '9876543210',
                    'ADDRESS1': 'MG Road, Bangalore',
                    'COUNTRYNAME': 'India',
                    'STATENAME': 'Karnataka',
                    'CITYNAME': 'Bangalore',
                    'DISTRICTNAME': 'Bangalore Urban',
                    'CREATEDBY': 'HIS_ADMIN',
                    'LOCATIONID': 'MH-BLR-01'
                },
                {
                    'UHID': 'UHID-2026-002',
                    'PATIENTNAME': 'AMIT KUMAR',
                    'IPNUMBER': 'IP-99002',
                    'GENDER': 'Male',
                    'AGE': '45 Yrs',
                    'ADMITTEDDATE': '02.09.2026 14:15',
                    'PLANINGDATE': '',
                    'CLOSINGDATE': '',
                    'PRIMARYDOCTOR': 'Dr. Anita Verma',
                    'NURSECHECKEDOUTTIME': '',
                    'ADMITING_DOCTOR': 'Dr. Anita Verma',
                    'ADMITING_DOCTOR_DEPT': 'Neurology',
                    'TREATING_DOCTOR': 'Dr. Anita Verma',
                    'TREATING_DOCTOR_DEPT': 'Neurology',
                    'INTERIMDATE': '',
                    'DISCHARGE_BILLDATE': '',
                    'BED_OCCUPIED': 'Bed-204',
                    'SPECIALIZATION': 'NEURO',
                    'SPECIALIZATIONDESC': 'Neurology',
                    'BEDNO': '204',
                    'BEDTYPE': 'Semi-Private',
                    'BILLABLEBED': 'Semi-Private',
                    'BEDNUMBER': '204',
                    'WARDNAME': 'Neuro Ward',
                    'COMPANYNAME': 'Star Health & Allied Insurance',
                    'REFRALDOCTOR': '',
                    'CURRENTSTATUS': 'ADMITTED',
                    'REASONANDREMARKS': 'Under observation',
                    'CONTACTNO': '9123456789',
                    'ADDRESS1': 'Indiranagar, Bangalore',
                    'COUNTRYNAME': 'India',
                    'STATENAME': 'Karnataka',
                    'CITYNAME': 'Bangalore',
                    'DISTRICTNAME': 'Bangalore Urban',
                    'CREATEDBY': 'HIS_ADMIN',
                    'LOCATIONID': 'MH-BLR-01'
                }
            ]

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for row in mock_rows:
                writer.writerow(row)

            csv_bytes = output.getvalue().encode('utf-8')
            file_hash = calculate_file_hash(csv_bytes)
            print(f"   -> Created test CSV ({len(mock_rows)} rows, hash: {file_hash[:10]}...)")

            # 4. Parse Rows
            print("\n4. Parsing HIS File...")
            parsed_rows = parse_his_file("his_sample.csv", csv_bytes)
            print(f"   -> Parsed {len(parsed_rows)} rows successfully.")
            assert len(parsed_rows) == 2, "Expected 2 parsed rows"

            # 5. Staging Batch Insert
            print("\n5. Creating Staging Batch...")
            batch = SyncBatch(
                source_system='HIS_EXCEL',
                source_type='FILE_UPLOAD',
                source_file_name='his_sample.csv',
                source_file_hash=file_hash,
                uploaded_by=user.id,
                total_records=len(parsed_rows),
                batch_status='UPLOADED',
                remarks='Automated verification test'
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

            # 6. Staging Validation Engine
            print("\n6. Running Staging Validation Engine...")
            validate_staging_batch(batch.batch_id)
            db.session.refresh(batch)
            print(f"   -> Batch Status: {batch.batch_status}")
            print(f"   -> Valid: {batch.total_records - batch.invalid_records}, Invalid: {batch.invalid_records}, Mapping Pending: {batch.mapping_pending_records}")

            # 7. Sync Engine Execution
            print("\n7. Executing Sync Engine...")
            process_sync_batch(batch.batch_id, user_id=user.id)
            db.session.refresh(batch)
            print(f"   -> Batch Sync Status: {batch.batch_status}")
            print(f"   -> Successful: {batch.successful_records}, Failed: {batch.failed_records}")
            print(f"   -> New Records: {batch.new_records}, Updated Records: {batch.updated_records}")

            # 8. Assert Target Database Records
            print("\n8. Verifying Target Patients & Admissions...")
            p1 = Patient.query.filter_by(uhid='UHID-2026-001').first()
            assert p1 is not None, "Patient UHID-2026-001 should exist"
            print(f"   -> Patient 1 Found: {p1.patient_name} (Normalized Name: SUPRITI SWAIN)")

            adm1 = IPAdmission.query.filter_by(ip_number='IP-99001').first()
            assert adm1 is not None, "IP Admission IP-99001 should exist"
            print(f"   -> Admission 1 Found: IP #{adm1.ip_number}, Status: {adm1.admission_status}, Admission Date: {adm1.admission_date}")

            p2 = Patient.query.filter_by(uhid='UHID-2026-002').first()
            assert p2 is not None, "Patient UHID-2026-002 should exist"
            print(f"   -> Patient 2 Found: {p2.patient_name} (AMIT KUMAR)")

            adm2 = IPAdmission.query.filter_by(ip_number='IP-99002').first()
            assert adm2 is not None, "IP Admission IP-99002 should exist"
            print(f"   -> Admission 2 Found: IP #{adm2.ip_number}, Status: {adm2.admission_status}")

            print("\n==================================================")
            print("ALL HIS DATA SYNC VERIFICATIONS PASSED SUCCESSFULLY!")
            print("==================================================")

if __name__ == '__main__':
    run_verification()
