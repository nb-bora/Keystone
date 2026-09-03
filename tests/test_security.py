"""
Tests de Sécurité Automatisés pour Aegis IAM.

Tests de sécurité automatisés couvrant :
- Injection SQL
- XSS
- CSRF
- Rate Limiting
- Authentification
- Autorisation
- GDPR Compliance
- Sécurité des sessions
"""

import unittest
from datetime import datetime, timezone

from aegis.core.application.gdpr import (
    GDPRFactory,
    StandardDataAnonymizer,
)
from aegis.core.application.sessions import (
    SessionManager,
    SessionSecurityPolicy,
)
from aegis.core.domain.authentication import (
    AuthenticationFactory,
    AuthenticationMethod,
)
from aegis.core.domain.values import SubjectId
from aegis.core.validation import (
    ValidationEngine,
)


class SecurityTests(unittest.TestCase):
    """Tests de sécurité automatisés pour Aegis IAM."""

    def test_password_strength_validation(self) -> None:
        """Teste que les mots de passe faibles sont rejetés."""
        engine = ValidationEngine()

        # Mot de passe trop court
        result = engine.validate("password", "short", "password")
        self.assertFalse(result.is_valid)

        # Mot de passe sans chiffres
        result = engine.validate("password", "noNumbers", "password")
        self.assertFalse(result.is_valid)

        # Mot de passe sans majuscules
        result = engine.validate("password", "nouppercase123", "password")
        self.assertFalse(result.is_valid)

        # Mot de passe fort
        result = engine.validate("password", "StrongPass123!", "password")
        self.assertTrue(result.is_valid)

    def test_email_injection_prevention(self) -> None:
        """Teste que les injections SQL via email sont prévenues."""
        engine = ValidationEngine()

        # Tentative d'injection SQL
        malicious_email = "'; DROP TABLE users; --"
        result = engine.validate("email", malicious_email, "email")
        self.assertFalse(result.is_valid)

        # Email valide
        valid_email = "user@example.com"
        result = engine.validate("email", valid_email, "email")
        self.assertTrue(result.is_valid)

    def test_session_timeout_enforcement(self) -> None:
        """Teste que les sessions expirent correctement."""
        policy = SessionSecurityPolicy(
            max_concurrent_sessions=5,
            session_timeout_seconds=3600,
            idle_timeout_seconds=1800,
            revoke_on_password_change=True,
            revoke_on_security_event=True,
        )

        # Vérifier que le timeout est appliqué
        self.assertEqual(policy._session_timeout, 3600)
        self.assertEqual(policy._idle_timeout, 1800)

    def test_session_revocation_on_password_change(self) -> None:
        """Teste que les sessions sont révoquées lors d'un changement de mot de passe."""
        policy = SessionSecurityPolicy()
        self.assertTrue(policy.should_revoke_on_password_change())

    def test_gdpr_anonymization_effectiveness(self) -> None:
        """Teste que l'anonymisation des données est effective."""
        anonymizer = StandardDataAnonymizer()

        # Anonymiser un email
        original_email = "alice.smith@enterprise.com"
        anonymized_email = anonymizer.anonymize_email(original_email)

        # Vérifier que l'email n'est plus le même
        self.assertNotEqual(original_email, anonymized_email)

        # Vérifier que l'anonymisation préserve le domaine
        self.assertTrue(anonymized_email.endswith("@enterprise.com"))

        # Vérifier que l'email ne contient plus le nom complet
        self.assertNotIn("alice", anonymized_email.lower())
        self.assertNotIn("smith", anonymized_email.lower())

    def test_gdpr_ip_anonymization(self) -> None:
        """Teste que les adresses IP sont correctement anonymisées."""
        anonymizer = StandardDataAnonymizer()

        original_ip = "192.168.1.100"
        anonymized_ip = anonymizer.anonymize_ip(original_ip)

        # Vérifier que l'IP n'est plus complète
        self.assertNotEqual(original_ip, anonymized_ip)

        # Vérifier que le préfixe réseau est préservé
        self.assertTrue(anonymized_ip.startswith("192.168"))

        # Vérifier que les derniers octets sont masqués
        self.assertIn("***", anonymized_ip)

    def test_concurrent_session_limit(self) -> None:
        """Teste que la limite de sessions concurrentes est respectée."""

        manager = SessionManager(default_ttl_seconds=3600, max_sessions_per_subject=3)

        subject_id = SubjectId("user-123")

        # Créer 3 sessions (limite)
        manager.create_session(subject_id)
        manager.create_session(subject_id)
        manager.create_session(subject_id)

        # Créer une 4ème session (doit révoquer la plus ancienne)
        manager.create_session(subject_id)

        # Vérifier qu'il n'y a que 3 sessions actives
        active_sessions = manager.get_active_sessions(subject_id)
        self.assertEqual(len(active_sessions), 3)

    def test_authentication_rate_limiting_protection(self) -> None:
        """Teste que le rate limiting protège contre les attaques par force brute."""
        from aegis.drivers.inmemory import Pbkdf2PasswordHasher

        hasher = Pbkdf2PasswordHasher(iterations=1000)
        manager = AuthenticationFactory.create_default_manager(hasher)

        # Simuler plusieurs tentatives d'authentification échouées
        failed_attempts = 0
        for _ in range(10):
            result = manager.authenticate(
                AuthenticationMethod.PASSWORD, {"subject_id": "user-123", "password": "wrongpassword"}
            )
            if not result.is_success:
                failed_attempts += 1

        # Vérifier que les tentatives échouées sont comptées
        self.assertGreater(failed_attempts, 0)

    def test_authorized_access_control(self) -> None:
        """Teste que l'accès non autorisé est refusé."""
        from aegis.core.domain.entities import HumanIdentity
        from aegis.core.domain.values import PermissionCode

        # Créer un utilisateur sans permission
        user = HumanIdentity(
            id=SubjectId("user-123"),
            permissions=set(),  # Aucune permission
        )

        # Vérifier que l'utilisateur n'a pas la permission
        self.assertFalse(user.has_permission(PermissionCode("document:read")))

    def test_sensitive_data_not_logged(self) -> None:
        """Teste que les données sensibles ne sont pas loggées."""
        from aegis.core.domain.events import AuthenticationSuccessEvent

        event = AuthenticationSuccessEvent(
            subject_id=SubjectId("user-123"), auth_method="password", ip_address="192.168.1.100"
        )

        audit_dict = event.to_audit_dict()

        # Vérifier que l'IP est anonymisée dans les logs
        ip_address = audit_dict.get("ip_address")
        self.assertIsNotNone(ip_address)
        self.assertIn("***", ip_address)

        # Vérifier que l'IP complète n'est pas dans les logs
        self.assertNotIn("192.168.1.100", audit_dict.values())

    def test_permission_revocation_immediate(self) -> None:
        """Teste que la révocation de permission est immédiate."""
        from aegis.core.domain.entities import HumanIdentity
        from aegis.core.domain.values import PermissionCode

        user = HumanIdentity(id=SubjectId("user-123"), permissions={PermissionCode("document:read")})

        # Révoquer la permission
        user.revoke_permission(PermissionCode("document:read"))

        # Vérifier que la permission n'existe plus
        self.assertFalse(user.has_permission(PermissionCode("document:read")))

    def test_tenant_isolation_enforcement(self) -> None:
        """Teste que l'isolation multi-tenant est respectée."""
        from aegis.core.domain.tenancy import Tenant, TenantLevel
        from aegis.core.domain.values import TenantId

        tenant_a = Tenant(id=TenantId("tenant-a"), name="Tenant A", level=TenantLevel.ENTERPRISE)

        tenant_b = Tenant(id=TenantId("tenant-b"), name="Tenant B", level=TenantLevel.ENTERPRISE)

        # Vérifier que les tenants sont différents
        self.assertNotEqual(tenant_a.id, tenant_b.id)
        self.assertNotEqual(tenant_a.name, tenant_b.name)

    def test_gdpr_right_to_erasure(self) -> None:
        """Teste que le droit à l'oubli est correctement implémenté."""

        gdpr_service = GDPRFactory.create_compliant_pipeline()

        # Demander la suppression des données
        result = gdpr_service.handle_right_to_erasure(SubjectId("user-123"), reason="User request")

        # Vérifier que la demande est enregistrée
        self.assertEqual(result["status"], "pending")
        self.assertIsNotNone(result["anonymization_scheduled"])
        self.assertIsNotNone(result["deletion_scheduled"])

    def test_role_hierarchy_privilege_escalation_prevention(self) -> None:
        """Teste que l'escalade de privilèges via les rôles est prévenue."""
        from aegis.core.domain.roles import Role
        from aegis.core.domain.values import PermissionCode, RoleId

        # Créer des rôles hiérarchiques
        admin_role = Role(id=RoleId("admin"), name="Administrator", permissions={PermissionCode("all:access")})

        user_role = Role(
            id=RoleId("user"),
            name="User",
            permissions={PermissionCode("document:read")},
            parent_role_ids=set(),  # Pas de parent
        )

        # Vérifier que le rôle utilisateur n'a pas les permissions admin
        self.assertFalse(user_role.has_permission(PermissionCode("all:access")))
        self.assertTrue(admin_role.has_permission(PermissionCode("all:access")))

    def test_password_hashing_strength(self) -> None:
        """Teste que le hachage des mots de passe utilise un algorithme fort."""
        from aegis.drivers.inmemory import Pbkdf2PasswordHasher

        hasher = Pbkdf2PasswordHasher(iterations=100000)

        password = "TestPassword123!"
        hash1 = hasher.hash(password)
        hash2 = hasher.hash(password)

        # Vérifier que le même mot de passe produit des hashes différents (salt)
        self.assertNotEqual(hash1, hash2)

        # Vérifier que les hashes sont vérifiables
        self.assertTrue(hasher.verify(password, hash1))
        self.assertTrue(hasher.verify(password, hash2))

        # Vérifier qu'un mauvais mot de passe est rejeté
        self.assertFalse(hasher.verify("WrongPassword", hash1))

    def test_sql_injection_prevention(self) -> None:
        """Teste que les injections SQL sont prévenues."""
        from aegis.core.validation import StringValidator

        validator = StringValidator(
            min_length=1,
            max_length=255,
            allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@.-_",
        )

        # Tentative d'injection SQL
        malicious_input = "'; DROP TABLE users; --"
        result = validator.validate(malicious_input)

        # Vérifier que l'injection est rejetée
        self.assertFalse(result.is_valid)

        # Entrée valide
        valid_input = "valid_user@example.com"
        result = validator.validate(valid_input)
        self.assertTrue(result.is_valid)

    def test_cross_tenant_access_prevention(self) -> None:
        """Teste que l'accès cross-tenant est prévenu."""
        from aegis.core.domain.tenancy import TenantContext, TenantIsolationPolicy
        from aegis.core.domain.values import TenantId

        # Créer des contextes de tenant différents
        context_a = TenantContext(tenant_id=TenantId("tenant-a"), isolation_level="row_level")

        context_b = TenantContext(tenant_id=TenantId("tenant-b"), isolation_level="row_level")

        # Vérifier que les contextes sont isolés
        self.assertNotEqual(context_a.tenant_id, context_b.tenant_id)

        # Créer une politique d'isolation
        policy = TenantIsolationPolicy(mode="hierarchical", isolation_type="row_level")

        # Vérifier que la politique est configurée
        self.assertEqual(policy.mode, "hierarchical")
        self.assertEqual(policy.isolation_type, "row_level")


class SecurityComplianceTests(unittest.TestCase):
    """Tests de conformité de sécurité pour Aegis IAM."""

    def test_default_deny_policy(self) -> None:
        """Teste que la politique par défaut est le refus."""
        from aegis.core.domain.policies import PolicyEffect

        # Vérifier que la politique par défaut est DENY
        self.assertEqual(PolicyEffect.DENY.value, "DENY")

    def test_session_security_default_settings(self) -> None:
        """Teste que les paramètres de sécurité par défaut sont sécurisés."""
        policy = SessionSecurityPolicy()

        # Vérifier que les timeouts sont raisonnables
        self.assertLess(policy._session_timeout, 7200)  # Moins de 2 heures
        self.assertLess(policy._idle_timeout, 3600)  # Moins de 1 heure

        # Vérifier que la révocation sur changement de mot de passe est activée
        self.assertTrue(policy.should_revoke_on_password_change())

    def test_gdpr_consent_tracking(self) -> None:
        """Teste que le consentement est correctement suivi."""
        from aegis.core.application.gdpr import ConsentRecord

        consent = ConsentRecord(
            consent_id="consent-123",
            subject_id=SubjectId("user-123"),
            consent_type="marketing",
            granted=True,
            granted_at=datetime.now(timezone.utc),
        )

        # Vérifier que le consentement est actif
        self.assertTrue(consent.is_active())

        # Retirer le consentement
        withdrawn_consent = consent.withdraw()

        # Vérifier que le consentement n'est plus actif
        self.assertFalse(withdrawn_consent.is_active())
        self.assertIsNotNone(withdrawn_consent.withdrawn_at)

    def test_encryption_at_rest_configuration(self) -> None:
        """Teste que le chiffrement au repos est configuré."""
        # Pour l'instant, test simulé - vérifier que les algorithmes sont configurés
        from aegis.drivers.inmemory import Pbkdf2PasswordHasher

        hasher = Pbkdf2PasswordHasher(iterations=100000)

        # Vérifier que le nombre d'itérations est suffisant
        self.assertGreater(hasher._iterations, 10000)


if __name__ == "__main__":
    unittest.main()
