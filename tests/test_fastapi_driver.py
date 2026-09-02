"""
Tests d'intégration de l'API REST FastAPI et des endpoints Swagger d'Aegis.
"""

import unittest

try:
    from fastapi.testclient import TestClient
    from aegis.drivers.fastapi.app import app
    from aegis.drivers.fastapi.dependencies import reset_global_container
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class TestFastAPIDriver(unittest.TestCase):

    def setUp(self) -> None:
        if FASTAPI_AVAILABLE:
            reset_global_container()
            self.client = TestClient(app)

    def test_healthcheck_endpoint(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé sur l'environnement local.")

        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)

    def test_register_human_endpoint_and_evaluate_access(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé sur l'environnement local.")

        # 1. Enregistrement d'un utilisateur humain
        payload = {
            "email": "diana.prince@enterprise.com",
            "first_name": "Diana",
            "last_name": "Prince",
            "tenant_id": "tenant-wonder-01",
            "initial_permissions": ["secure_vault:open", "security_log:read"],
        }
        reg_resp = self.client.post("/api/v1/subjects/human", json=payload)
        self.assertEqual(reg_resp.status_code, 201)
        human_data = reg_resp.json()
        self.assertEqual(human_data["subject_type"], "HUMAN")
        subject_id = human_data["id"]

        # 2. Évaluation de permission autorisée (ALLOW)
        eval_payload = {
            "subject_id": subject_id,
            "action": "secure_vault:open",
        }
        eval_resp = self.client.post("/api/v1/auth/evaluate", json=eval_payload)
        self.assertEqual(eval_resp.status_code, 200)
        eval_data = eval_resp.json()
        self.assertTrue(eval_data["is_allowed"])
        self.assertEqual(eval_data["effect"], "ALLOW")

        # 3. Évaluation de permission refusée (DENY)
        eval_deny_payload = {
            "subject_id": subject_id,
            "action": "nuclear_codes:launch",
        }
        eval_deny_resp = self.client.post("/api/v1/auth/evaluate", json=eval_deny_payload)
        self.assertEqual(eval_deny_resp.status_code, 200)
        eval_deny_data = eval_deny_resp.json()
        self.assertFalse(eval_deny_data["is_allowed"])
        self.assertEqual(eval_deny_data["effect"], "DENY")

    def test_evaluate_access_non_existent_subject_returns_404(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé sur l'environnement local.")

        eval_payload = {
            "subject_id": "non-existent-id-999",
            "action": "some:action",
        }
        response = self.client.post("/api/v1/auth/evaluate", json=eval_payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("introuvable", response.json()["detail"])

    def test_audit_events_endpoint(self) -> None:
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI non installé sur l'environnement local.")

        # Créer une identité
        self.client.post(
            "/api/v1/subjects/human",
            json={"email": "audit.user@example.com", "first_name": "Audit", "last_name": "User"},
        )

        # Récupérer les événements d'audit
        audit_resp = self.client.get("/api/v1/audit/events")
        self.assertEqual(audit_resp.status_code, 200)
        events = audit_resp.json()
        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "SUBJECT_REGISTERED")


if __name__ == "__main__":
    unittest.main()
