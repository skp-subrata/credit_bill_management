import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from config import Config
from app import app
from database import db
from models import User, HospitalUnit, Patient, Payer, HospitalPayer, Bill, IPAdmission, OPEpisode, AuditLog, AdminUploadHistory, SyncBatch, HISIPStaging, HISPayerMapping

class TestPagination15(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_config_items_per_page(self):
        self.assertEqual(Config.ITEMS_PER_PAGE, 15)

    def test_routes_pagination_rendering(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['employee_id'] = 'EMP001'
            sess['role_code'] = 'super_admin'
            sess['role_name'] = 'Super Admin'
            sess['active_unit_id'] = 1

        routes_to_test = [
            '/billing/bills',
            '/encounters/ip/admissions',
            '/encounters/op/episodes',
            '/masters/units',
            '/masters/patients',
            '/masters/payers',
            '/masters/hospital-payers',
            '/admin/users',
            '/admin/audit-logs',
            '/admin/data-upload',
            '/his-sync/history',
            '/his-sync/errors',
            '/his-sync/mappings'
        ]

        for route in routes_to_test:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Failed loading route {route}")
            print(f"[OK] Route '{route}' responded HTTP 200 OK")

if __name__ == '__main__':
    unittest.main()

