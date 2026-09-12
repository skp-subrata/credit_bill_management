import sys, os, io
sys.path.insert(0, os.path.abspath('.'))
from app import app
from database import db
from models import HospitalUnit, Payer, HospitalPayer, Bill, AdminUploadHistory, User
from utils.admin_upload_engine import generate_template, validate_admin_upload, execute_admin_import
from werkzeug.datastructures import FileStorage

def run_tests():
    print("==================================================")
    print("Testing Centralized Admin Data Upload Module")
    print("==================================================")

    # 1. Template Generation Test
    print("\n[Test 1] Template Download Generation...")
    data_xlsx, mime_x, name_x = generate_template('hospital_payers', fmt='xlsx')
    assert len(data_xlsx) > 0 and 'Template_hospital_payers.xlsx' in name_x
    print(f"  - Generated Excel Template: {name_x} ({len(data_xlsx)} bytes)")

    data_csv, mime_c, name_c = generate_template('hospital_payers', fmt='csv')
    assert len(data_csv) > 0 and 'Template_hospital_payers.csv' in name_c
    print(f"  - Generated CSV Template: {name_c} ({len(data_csv)} bytes)")
    assert 'monthly_submission' in data_csv.decode('utf-8')

    # 2. Master Validation & Dependency Checks
    print("\n[Test 2] Master Dependency Validation Engine...")
    with app.app_context():
        unit = HospitalUnit.query.first()
        payer = Payer.query.first()
        admin_user = User.query.filter(User.role_id == 1).first() or User.query.first()

        if not unit or not payer or not admin_user:
            print("Missing DB prerequisites for unit/payer/user.")
            return

        # Valid Payer-Pair CSV content with Monthly Submission = Yes
        valid_csv_content = f"unit_code,payer_code,payer_code_at_unit,billing_type,credit_allowed,submission_tat_days,monthly_submission,dispatch_mode,status\n{unit.unit_code},{payer.payer_code},PAIR-TEST,CREDIT,Yes,20,Yes,COURIER,ACTIVE\n"
        
        file_obj = FileStorage(
            stream=io.BytesIO(valid_csv_content.encode('utf-8')),
            filename="test_hospital_payers.csv",
            content_type="text/csv"
        )

        report = validate_admin_upload('hospital_payers', file_obj)
        print(f"  - Validation Summary: Total={report['total_records']}, Valid={report['valid_count']}, Errors={report['error_count']}")
        assert report['valid_count'] == 1, f"Expected 1 valid record, got {report['valid_count']}"
        assert report['error_count'] == 0

        # Invalid Payer-Pair CSV content (Non-existent unit & non-existent payer)
        invalid_csv_content = "unit_code,payer_code,payer_code_at_unit,billing_type,credit_allowed,submission_tat_days,monthly_submission,dispatch_mode,status\nINVALID-UNIT,INVALID-PAYER,PAIR-X,CREDIT,Yes,15,No,COURIER,ACTIVE\n"
        invalid_file_obj = FileStorage(
            stream=io.BytesIO(invalid_csv_content.encode('utf-8')),
            filename="invalid_hospital_payers.csv",
            content_type="text/csv"
        )
        invalid_report = validate_admin_upload('hospital_payers', invalid_file_obj)
        print(f"  - Invalid File Summary: Total={invalid_report['total_records']}, Valid={invalid_report['valid_count']}, Errors={invalid_report['error_count']}")
        assert invalid_report['error_count'] == 1
        print(f"    Caught Expected Error: {invalid_report['errors'][0]['reason']}")

        # 3. End-to-End Import Execution Test
        print("\n[Test 3] Execute Admin Import into Database...")
        result = execute_admin_import('hospital_payers', report['valid_records'], admin_user.id, "test_hospital_payers.csv")
        print(f"  - Import Result: Success={result['success_count']}, Failed={result['failed_count']}")
        assert result['success_count'] == 1

        # Verify DB Record created
        hp_record = HospitalPayer.query.filter_by(unit_id=unit.unit_id, payer_id=payer.payer_id).first()
        assert hp_record is not None
        assert hp_record.monthly_submission is True
        assert hp_record.submission_tat_days == 20
        print(f"  - Verified HospitalPayer DB Record: MonthlySubmission={hp_record.monthly_submission}, TATDays={hp_record.submission_tat_days}")

        # Verify AdminUploadHistory logged
        history = AdminUploadHistory.query.get(result['history_id'])
        assert history is not None
        assert history.data_category == 'hospital_payers'
        assert history.success_records == 1
        print(f"  - Verified AdminUploadHistory Log #{history.history_id}: File={history.file_name}, Category={history.data_category}")

        admin_user_id = admin_user.id
        admin_user_role = getattr(admin_user, 'role', 'admin')

    # 4. RBAC Route Access Control Test
    print("\n[Test 4] RBAC Route Access Control Test...")
    with app.test_client() as client:
        # Non-admin session attempt
        with client.session_transaction() as sess:
            sess['user_id'] = 99
            sess['role_code'] = 'biller' # Non-admin role

        res = client.get('/admin/data-upload', follow_redirects=True)
        assert 'Access Denied' in res.get_data(as_text=True)
        print("  - Non-admin user successfully blocked from /admin/data-upload (Access Denied).")

        # Admin session attempt
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user_id
            sess['role_code'] = 'admin'

        res_admin = client.get('/admin/data-upload')
        assert res_admin.status_code == 200
        html = res_admin.get_data(as_text=True)
        assert 'Centralized Data Upload Module' in html
        assert 'Hospital / Unit Master' in html
        print("  - Admin user successfully granted access to /admin/data-upload.")

    print("\n==================================================")
    print("ALL CENTRALIZED ADMIN DATA UPLOAD TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
