"""
Tests unitaires pour le moteur de politiques RBAC et Composite.
"""

import unittest

from aegis.core.domain.entities import HumanIdentity
from aegis.core.domain.values import EmailAddress, PermissionCode, SubjectId
from aegis.core.policies.composite import CascadeStrategy, CompositePolicyEngine
from aegis.core.policies.rbac import RBACPolicyEngine


class TestRBACPolicyEngine(unittest.TestCase):

    def test_rbac_evaluation_allow(self) -> None:
        engine = RBACPolicyEngine()
        human = HumanIdentity(id=SubjectId("user-1"), email=EmailAddress("bob@example.com"))
        human.grant_permission(PermissionCode("report:read"))

        decision = engine.evaluate(human, "report:read")
        self.assertTrue(decision.is_allowed)
        self.assertEqual(decision.effect.value, "ALLOW")

    def test_rbac_evaluation_deny_unassigned_permission(self) -> None:
        engine = RBACPolicyEngine()
        human = HumanIdentity(id=SubjectId("user-1"))

        decision = engine.evaluate(human, "report:delete")
        self.assertFalse(decision.is_allowed)
        self.assertTrue(decision.is_denied)

    def test_rbac_evaluation_deny_suspended_user(self) -> None:
        engine = RBACPolicyEngine()
        human = HumanIdentity(id=SubjectId("user-1"))
        human.grant_permission(PermissionCode("report:read"))
        human.suspend()

        decision = engine.evaluate(human, "report:read")
        self.assertFalse(decision.is_allowed)
        self.assertIn("inactif ou suspendu", decision.reason)

    def test_composite_engine_cascade_first_applicable(self) -> None:
        rbac1 = RBACPolicyEngine()
        rbac2 = RBACPolicyEngine()
        composite = CompositePolicyEngine(engines=[rbac1, rbac2], strategy=CascadeStrategy.FIRST_APPLICABLE)

        human = HumanIdentity(id=SubjectId("user-1"))
        human.grant_permission(PermissionCode("doc:view"))

        decision = composite.evaluate(human, "doc:view")
        self.assertTrue(decision.is_allowed)


if __name__ == "__main__":
    unittest.main()
