import unittest
import os
import json
import config

class TestConfig(unittest.TestCase):

    def setUp(self):
        # Backup existing dvrs.json if present
        self.backup_file = config.DVRS_FILE + ".bak"
        if os.path.exists(config.DVRS_FILE):
            os.rename(config.DVRS_FILE, self.backup_file)

    def tearDown(self):
        # Restore backup
        if os.path.exists(config.DVRS_FILE):
            os.remove(config.DVRS_FILE)
        if os.path.exists(self.backup_file):
            os.rename(self.backup_file, config.DVRS_FILE)

    def test_load_and_add_dvr(self):
        dvrs = config.get_dvrs()
        self.assertGreaterEqual(len(dvrs), 1)

        # Add single DVR
        config.add_dvr("Dhaka Branch", "10.64.2.250", "admin", "pass123")
        updated_dvrs = config.get_dvrs()
        
        found = any(d["ip"] == "10.64.2.250" and d["site"] == "Dhaka Branch" for d in updated_dvrs)
        self.assertTrue(found)

    def test_bulk_import_dvrs(self):
        csv_data = """
        Dhaka Branch, 10.64.2.250, admin, test1
        Chittagong Branch, 10.64.130.250, admin, test2
        Sylhet Branch, 10.64.45.250
        10.64.50.250
        """
        count = config.bulk_import_dvrs(csv_data)
        self.assertEqual(count, 4)

        dvrs = config.get_dvrs()
        ips = [d["ip"] for d in dvrs]
        self.assertIn("10.64.2.250", ips)
        self.assertIn("10.64.130.250", ips)
        self.assertIn("10.64.45.250", ips)
        self.assertIn("10.64.50.250", ips)

    def test_remove_dvr(self):
        config.add_dvr("Test Remove", "10.99.99.99")
        config.remove_dvr("10.99.99.99")
        dvrs = config.get_dvrs()
        ips = [d["ip"] for d in dvrs]
        self.assertNotIn("10.99.99.99", ips)

if __name__ == "__main__":
    unittest.main()
