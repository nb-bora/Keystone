"""
Tests d'intégration et Use Cases avec le SDK AegisClient.
"""

import unittest

from aegis.drivers.inmemory import Pbkdf2PasswordHasher
from aegis.sdk.client import AegisClient, AegisContainer


class TestUseCasesAndSDK(unittest.TestCase):
    def test_full_sdk_workflow(self) -> None:
        container = AegisContainer()
        client = AegisClient(container)

        # 1. Enregistrement d'un utilisateur humain
        human = client.register_human(
            email="carol@example.com",
            first_name="Carol",
            last_name="Danvers",
            initial_permissions={"project:create", "project:read"},
        )

        self.assertIsNotNone(human.email)
        self.assertEqual(human.email.value, "carol@example.com")
        subject_id = human.id.value

        # 2. Test d'évaluation de permission autorisée
        self.assertTrue(client.can(subject_id, "project:create"))
        self.assertTrue(client.can(subject_id, "project:read"))

        # 3. Test d'évaluation de permission non autorisée
        self.assertFalse(client.can(subject_id, "project:delete"))

        # 4. Vérification du Transactional Outbox
        pending_events = container.outbox.get_pending_events()
        self.assertEqual(len(pending_events), 1)
        event = pending_events[0]
        self.assertEqual(event.event_type, "SUBJECT_REGISTERED")
        self.assertEqual(event.to_audit_dict()["email_anonymized"], "c***@example.com")

    def test_register_duplicate_email_raises_error(self) -> None:
        client = AegisClient()
        client.register_human(email="duplicate@example.com")

        with self.assertRaises(ValueError):
            client.register_human(email="duplicate@example.com")

    def test_password_hasher_security(self) -> None:
        hasher = Pbkdf2PasswordHasher(iterations=1000)
        raw_password = "SuperSecretPassword123!"

        hashed = hasher.hash(raw_password)
        self.assertTrue(hashed.startswith("pbkdf2_sha256$1000$"))

        self.assertTrue(hasher.verify(raw_password, hashed))
        self.assertFalse(hasher.verify("WrongPassword", hashed))


if __name__ == "__main__":
    unittest.main()
