import os
import tempfile
import unittest
import app as nexus_app

class NexusAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = nexus_app.DATABASE
        nexus_app.DATABASE = os.path.join(self.temp_dir.name, "test.db")
        nexus_app.init_db()
        nexus_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = nexus_app.app.test_client()

    def tearDown(self):
        nexus_app.DATABASE = self.original_db
        self.temp_dir.cleanup()

    def test_home_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_register_login_and_logout(self):
        response = self.client.post("/register", data={
            "name": "Test Student", "email": "test@example.com",
            "password": "strongpass123", "confirm_password": "strongpass123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)
        response = self.client.post("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/login", data={
            "email": "test@example.com", "password": "strongpass123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)

if __name__ == "__main__":
    unittest.main()
