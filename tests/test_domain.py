"""
Tests unitaires pour les Value Objects et Entities du Domaine Aegis.
"""

import unittest

from aegis.core.domain.entities import AIAgentActor, HumanIdentity, ServiceAccount
from aegis.core.domain.values import EmailAddress, PermissionCode, SubjectId


class TestDomainValuesAndEntities(unittest.TestCase):

    def test_subject_id_valid(self) -> None:
        sid = SubjectId("sub-123")
        self.assertEqual(sid.value, "sub-123")
        self.assertEqual(str(sid), "sub-123")

    def test_subject_id_invalid(self) -> None:
        with self.assertRaises(ValueError):
            SubjectId("")

    def test_email_address_validation_and_normalization(self) -> None:
        email = EmailAddress("  Test.User@Domain.COM  ")
        self.assertEqual(email.value, "test.user@domain.com")
        self.assertEqual(email.domain, "domain.com")
        self.assertEqual(email.anonymized(), "t***@domain.com")

    def test_email_address_invalid(self) -> None:
        with self.assertRaises(ValueError):
            EmailAddress("invalid-email-string")

    def test_human_identity_grant_and_revoke_permissions(self) -> None:
        human = HumanIdentity(
            id=SubjectId("user-1"),
            email=EmailAddress("alice@example.com"),
            first_name="Alice",
        )
        self.assertEqual(human.subject_type, "HUMAN")
        self.assertTrue(human.is_active)

        perm = PermissionCode("document:edit")
        self.assertFalse(human.has_direct_permission(perm))

        human.grant_permission(perm)
        self.assertTrue(human.has_direct_permission(perm))

        human.revoke_permission(perm)
        self.assertFalse(human.has_direct_permission(perm))

    def test_human_identity_suspend_and_activate(self) -> None:
        human = HumanIdentity(id=SubjectId("user-1"))
        self.assertTrue(human.is_active)

        human.suspend()
        self.assertFalse(human.is_active)

        human.activate()
        self.assertTrue(human.is_active)

    def test_service_account_scopes(self) -> None:
        sa = ServiceAccount(id=SubjectId("sa-1"), client_id="client-xyz")
        self.assertEqual(sa.subject_type, "SERVICE_ACCOUNT")
        self.assertFalse(sa.has_scope("read"))

        sa.grant_scope("read")
        self.assertTrue(sa.has_scope("read"))

    def test_ai_agent_actor(self) -> None:
        agent = AIAgentActor(
            id=SubjectId("agent-007"),
            agent_name="AutoCoder",
            max_autonomy_level=2,
        )
        self.assertEqual(agent.subject_type, "AI_AGENT")
        self.assertEqual(agent.max_autonomy_level, 2)

    def test_settings_loading(self) -> None:
        from aegis.core.config import settings
        self.assertIsNotNone(settings.environment)
        self.assertGreater(settings.port, 0)
        self.assertIsNotNone(settings.secret_key)


if __name__ == "__main__":
    unittest.main()
