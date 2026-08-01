import os
import unittest

from src.dashboard import app


class TestDashboard(unittest.TestCase):
    def test_dashboard_template_exists_and_renders(self):
        template_path = os.path.join(app.template_folder, "dashboard.html")
        self.assertTrue(os.path.exists(template_path), msg=f"Template not found at {template_path}")

        client = app.test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
