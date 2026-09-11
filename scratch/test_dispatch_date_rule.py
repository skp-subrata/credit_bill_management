import sys, os
sys.path.insert(0, os.path.abspath('.'))
from datetime import datetime
from utils.tat import get_dispatch_date_bounds, validate_dispatch_date
from app import app
from database import db
from models import Bill, BillDispatch, User

def run_tests():
    print("==================================================")
    print("Testing Dispatch Date Restriction Logic (Today - 3 days to Today)")
    print("==================================================")

    # Test 1: Today = 12 Sep 2026
    ref_12_sep = datetime(2026, 9, 12).date()
    min_d, max_d = get_dispatch_date_bounds(ref_12_sep)
    print(f"\n[Test 1] Today = 12 Sep 2026 -> Calculated Bounds: Min={min_d}, Max={max_d}")
    assert min_d == '2026-09-09', f"Expected 2026-09-09, got {min_d}"
    assert max_d == '2026-09-12', f"Expected 2026-09-12, got {max_d}"

    # Check 12 Sep test matrix
    cases_12_sep = [
        ('2026-09-08', False, "8 Sep (Before Min)"),
        ('2026-09-09', True, "9 Sep (Min Allowed)"),
        ('2026-09-10', True, "10 Sep (Allowed)"),
        ('2026-09-11', True, "11 Sep (Allowed)"),
        ('2026-09-12', True, "12 Sep (Max Allowed)"),
        ('2026-09-13', False, "13 Sep (Future Date)")
    ]

    for date_str, expected_valid, label in cases_12_sep:
        is_valid, msg = validate_dispatch_date(date_str, ref_date=ref_12_sep)
        status = "PASSED" if is_valid == expected_valid else "FAILED"
        print(f"  - {label} ({date_str}): Valid={is_valid} (Expected={expected_valid}) -> {status}")
        if not is_valid:
            print(f"    Error Msg: {msg}")
        assert is_valid == expected_valid, f"Failed for {label}"

    # Test 2: Today = 15 Sep 2026
    ref_15_sep = datetime(2026, 9, 15).date()
    min_d, max_d = get_dispatch_date_bounds(ref_15_sep)
    print(f"\n[Test 2] Today = 15 Sep 2026 -> Calculated Bounds: Min={min_d}, Max={max_d}")
    assert min_d == '2026-09-12' and max_d == '2026-09-15'
    assert validate_dispatch_date('2026-09-12', ref_date=ref_15_sep)[0] is True
    assert validate_dispatch_date('2026-09-15', ref_date=ref_15_sep)[0] is True
    assert validate_dispatch_date('2026-09-11', ref_date=ref_15_sep)[0] is False
    assert validate_dispatch_date('2026-09-16', ref_date=ref_15_sep)[0] is False

    # Test 3: Today = 20 Sep 2026
    ref_20_sep = datetime(2026, 9, 20).date()
    min_d, max_d = get_dispatch_date_bounds(ref_20_sep)
    print(f"\n[Test 3] Today = 20 Sep 2026 -> Calculated Bounds: Min={min_d}, Max={max_d}")
    assert min_d == '2026-09-17' and max_d == '2026-09-20'
    assert validate_dispatch_date('2026-09-17', ref_date=ref_20_sep)[0] is True
    assert validate_dispatch_date('2026-09-20', ref_date=ref_20_sep)[0] is True
    assert validate_dispatch_date('2026-09-16', ref_date=ref_20_sep)[0] is False

    # Test 4: Flask Route Integration Test
    print("\n[Test 4] Integration Test via Flask Test Client")
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role_code'] = 'admin'
            sess['active_unit_id'] = 1

        with app.app_context():
            bill = Bill.query.first()
            if bill:
                # GET bill detail page
                res = client.get(f'/billing/bills/{bill.bill_id}')
                assert res.status_code == 200
                html = res.get_data(as_text=True)
                assert 'Dispatch Date' in html
                assert 'min="' in html and 'max="' in html
                print(f"  - GET /billing/bills/{bill.bill_id} rendered successfully with min/max input attributes.")

                # POST invalid dispatch date (e.g. 2020-01-01)
                post_res = client.post(f'/billing/bills/{bill.bill_id}/dispatch', data={
                    'dispatch_date': '2020-01-01',
                    'dispatch_mode': 'COURIER'
                }, follow_redirects=True)
                post_html = post_res.get_data(as_text=True)
                assert 'invalid' in post_html.lower() or 'minimum allowed' in post_html.lower()
                print("  - POST with out-of-range date successfully rejected with error flash message.")

    print("\n==================================================")
    print("ALL DISPATCH DATE RESTRICTION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
