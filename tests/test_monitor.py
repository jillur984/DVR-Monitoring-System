import unittest
import monitor

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

if __name__ == "__main__":
    unittest.main()
