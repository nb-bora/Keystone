"""
Tests unitaires pour les Healthchecks Triple-Niveaux et le Middleware de Corrélation X-Request-ID.
"""

import unittest

try:
    from fastapi.testclient import TestClient

    from aegis.drivers.fastapi.app import app
    from aegis.drivers.fastapi.dependencies import reset_global_container

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class TestHealthAndObservability(unittest.TestCase):
    def setUp(self) -> None:
        if FASTAPI_AVAILABLE:
            reset_global_container()
            self.client = TestClient(app)

    def test_liveness_probe_returns_200_ok(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé.")

        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "aegis-api")

    def test_readiness_probe_structure(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé.")

        response = self.client.get("/health/ready")
        self.assertIn(response.status_code, [200, 503])
        data = response.json()
        self.assertIn("checks", data)
        self.assertIn("database", data["checks"])

    def test_startup_probe_returns_200_ok(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé.")

        response = self.client.get("/health/startup")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["initialized"])

    def test_correlation_id_middleware(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé.")

        custom_id = "test-correlation-uuid-998877"
        response = self.client.get("/health/live", headers={"X-Request-ID": custom_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), custom_id)

    def test_metrics_endpoint(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé.")

        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("aegis_info", data)


if __name__ == "__main__":
    unittest.main()
