import unittest
from unittest.mock import patch
import monitor
import src.monitor as monitor_impl

class TestMonitor(unittest.TestCase):

    def test_check_all_dvrs_concurrently(self):
        sample_dvrs = [
            {"site": "Branch 1", "ip": "127.0.0.1", "username": "admin", "password": "123"},
            {"site": "Branch 2", "ip": "10.255.255.255", "username": "admin", "password": "123"}
        ]
        results = monitor.check_all_dvrs_concurrently(sample_dvrs)
        self.assertEqual(len(results), 2)
        sites = [r["site"] for r in results]
        self.assertIn("Branch 1", sites)
        self.assertIn("Branch 2", sites)

    def test_build_scheduled_alert_candidates_filters_only_relevant_issues(self):
        results = [
            {"site": "A", "online": False, "hdd_count": 0, "hdd_status": "OFFLINE"},
            {"site": "B", "online": True, "hdd_count": 2, "hdd_status": "HDD OK"},
            {"site": "C", "online": True, "hdd_count": 0, "hdd_status": "ERROR"},
        ]

        candidates = monitor.build_scheduled_alert_candidates(results)

        self.assertEqual([item["site"] for item in candidates], ["A", "C"])

    def test_should_send_scheduled_digest_only_once_per_slot(self):
        now = monitor.datetime(2026, 8, 3, 9, 30, 0)
        sent_slots = {}

        first = monitor.should_send_scheduled_digest(now, {"scheduled_alert_times": ["09:30", "17:00"]}, sent_slots)
        second = monitor.should_send_scheduled_digest(now, {"scheduled_alert_times": ["09:30", "17:00"]}, sent_slots)

        self.assertTrue(first)
        self.assertFalse(second)

    def test_validate_dvr_access_rejects_incorrect_credentials(self):
        dvr = {"site": "Bad DVR", "ip": "10.0.0.5", "username": "wrong", "password": "bad"}
        with patch.object(monitor_impl, "get_dvr_status", return_value=(True, 0, {"auth_error": True}, "AUTH_REQUIRED (401)")):
            valid, message, is_warn = monitor_impl.validate_dvr_access(dvr)

        self.assertFalse(valid)
        self.assertIn("credentials", message.lower())

    def test_validate_dvr_access_accepts_valid_credentials(self):
        dvr = {"site": "Good DVR", "ip": "10.0.0.6", "username": "admin", "password": "123"}
        with patch.object(monitor_impl, "get_dvr_status", return_value=(True, 12, {"device_time": "2026-08-03"}, "OK")):
            valid, message, is_warn = monitor_impl.validate_dvr_access(dvr)

        self.assertTrue(valid)
        self.assertIn("verified", message.lower())
        self.assertFalse(is_warn)

    def test_validate_dvr_access_allows_offline_with_warning(self):
        dvr = {"site": "Offline DVR", "ip": "10.0.0.7", "username": "admin", "password": "123"}
        with patch.object(monitor_impl, "get_dvr_status", return_value=(False, 5000, None, "OFFLINE")):
            valid, message, is_warn = monitor_impl.validate_dvr_access(dvr)

        self.assertTrue(valid)
        self.assertTrue(is_warn)
        self.assertIn("unreachable", message.lower())

if __name__ == "__main__":
    unittest.main()
