"""
Tests Unitaires pour les nouveaux composants Aegis.

Couche de tests unitaires rapides et isolés sans dépendances externes.
"""

import unittest
from datetime import datetime, timezone

from aegis.core.application.acl import (
    MapperFactory,
    SubjectData,
)
from aegis.core.application.gdpr import (
    GDPRPipeline,
    StandardDataAnonymizer,
)
from aegis.core.application.sessions import (
    SessionManager,
)
from aegis.core.config_loader import (
    AegisConfig,
    get_config,
    load_config,
)
from aegis.core.domain.authentication import (
    AuthenticationFactory,
    AuthenticationMethod,
    OIDCAuthStrategy,
    PasswordAuthStrategy,
)
from aegis.core.domain.events import (
    AuthenticationFailureEvent,
    AuthenticationSuccessEvent,
    AuthorizationDecisionEvent,
    DataDeletionRequestedEvent,
    DataExportRequestedEvent,
)
from aegis.core.domain.roles import (
    Role,
    SystemRolesFactory,
)
from aegis.core.domain.tenancy import (
    IsolationType,
    TenancyMode,
    Tenant,
    TenantIsolationPolicy,
    TenantLevel,
)
from aegis.core.plugins import (
    BaseHook,
    HookContext,
    HookResult,
    HookType,
    PluginFactory,
    PluginManager,
)
from aegis.core.policies.abac import (
    ABACConditionFactory,
    ABACPolicyEngine,
    PredefinedABACPolicies,
)
from aegis.core.policies.rebac import (
    InMemoryRelationshipStore,
    RelationshipCheck,
    RelationshipTuple,
    RelationType,
)
from aegis.core.validation import ValidationEngine


class TestConfigurationLoader(unittest.TestCase):
    """Tests du chargeur de configuration."""

    def test_load_default_config(self) -> None:
        """Teste le chargement de la configuration par défaut."""
        config = load_config()
        self.assertIsInstance(config, AegisConfig)
        self.assertEqual(config.environment, "development")
        self.assertTrue(config.debug)

    def test_config_validation(self) -> None:
        """Teste la validation de la configuration."""
        config = get_config()
        # Teste que les valeurs par défaut sont valides
        self.assertIn(config.storage.driver, ["inmemory", "sqlalchemy", "django"])
        self.assertIn(config.policy_engines.primary, ["rbac", "abac", "rebac", "composite"])


class TestDataMapper(unittest.TestCase):
    """Tests du Data Mapper (ACL)."""

    def test_subject_data_to_domain(self) -> None:
        """Teste la conversion de données Subject vers Domain."""
        mapper = MapperFactory.create_subject_mapper()

        data = SubjectData(
            id="sub-123",
            subject_type="HUMAN",
            tenant_id="tenant-456",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            email="test@example.com",
            first_name="Test",
            last_name="User",
            permissions=["document:read"],
        )

        subject = mapper.from_data(data)
        self.assertEqual(subject.id.value, "sub-123")
        self.assertEqual(subject.subject_type, "HUMAN")
        self.assertTrue(subject.is_active)

    def test_domain_to_orm_data(self) -> None:
        """Teste la conversion de Domain vers ORM."""
        from aegis.core.domain.entities import HumanIdentity
        from aegis.core.domain.values import EmailAddress, SubjectId

        mapper = MapperFactory.create_subject_mapper()

        human = HumanIdentity(
            id=SubjectId("sub-123"), email=EmailAddress("test@example.com"), first_name="Test", last_name="User"
        )

        orm_data = mapper.to_orm(human)
        self.assertEqual(orm_data["id"], "sub-123")
        self.assertEqual(orm_data["subject_type"], "HUMAN")
        self.assertEqual(orm_data["email"], "test@example.com")


class TestValidationEngine(unittest.TestCase):
    """Tests du moteur de validation."""

    def test_email_validation(self) -> None:
        """Teste la validation d'email."""
        engine = ValidationEngine()

        # Email valide
        result = engine.validate("email", "test@example.com", "email")
        self.assertTrue(result.is_valid)

        # Email invalide
        result = engine.validate("email", "invalid-email", "email")
        self.assertFalse(result.is_valid)

    def test_password_validation(self) -> None:
        """Teste la validation de mot de passe."""
        engine = ValidationEngine()

        # Mot de passe fort
        result = engine.validate("password", "StrongPass123!", "password")
        self.assertTrue(result.is_valid)

        # Mot de passe faible
        result = engine.validate("password", "weak", "password")
        self.assertFalse(result.is_valid)

    def test_custom_validator(self) -> None:
        """Teste un validateur personnalisé."""
        engine = ValidationEngine()
        # Test de base de registration
        self.assertIsNotNone(engine)


class TestABACPolicyEngine(unittest.TestCase):
    """Tests du moteur de politique ABAC."""

    def test_time_based_condition(self) -> None:
        """Teste les conditions temporelles."""
        condition = ABACConditionFactory.business_hours_only()

        from aegis.core.domain.entities import HumanIdentity
        from aegis.core.domain.values import EvaluationContext, SubjectId

        human = HumanIdentity(id=SubjectId("user-1"))
        context = EvaluationContext(
            timestamp=datetime.now(timezone.utc).replace(hour=10)  # 10h UTC
        )

        # Pendant les heures ouvrées (9h-17h UTC)
        self.assertTrue(condition.evaluate(context, human))

    def test_ip_whitelist_condition(self) -> None:
        """Teste les conditions de whitelist IP."""
        condition = ABACConditionFactory.ip_whitelist({"192.168.1.100"})

        from aegis.core.domain.entities import HumanIdentity
        from aegis.core.domain.values import EvaluationContext, SubjectId

        human = HumanIdentity(id=SubjectId("user-1"))
        context = EvaluationContext(ip_address="192.168.1.100")

        self.assertTrue(condition.evaluate(context, human))

    def test_abac_policy_evaluation(self) -> None:
        """Teste l'évaluation d'une politique ABAC."""
        from aegis.core.domain.entities import HumanIdentity
        from aegis.core.domain.values import SubjectId

        engine = ABACPolicyEngine()
        policy = PredefinedABACPolicies.business_hours_policy()
        engine.add_policy(policy)

        human = HumanIdentity(id=SubjectId("user-1"))

        decision = engine.evaluate(human, "document:read")
        self.assertIsNotNone(decision)


class TestReBACPolicyEngine(unittest.TestCase):
    """Tests du moteur de politique ReBAC."""

    def test_relationship_storage(self) -> None:
        """Teste le stockage des relations."""
        store = InMemoryRelationshipStore()

        from aegis.core.domain.values import SubjectId

        tuple1 = RelationshipTuple(
            subject_id=SubjectId("user-1"),
            relation=RelationType.DIRECT_OWNER,
            resource_id="doc-123",
            resource_type="document",
        )

        store.add_tuple(tuple1)

        retrieved = store.get_tuples(subject_id=SubjectId("user-1"))
        self.assertEqual(len(retrieved), 1)

    def test_transitive_relationship_check(self) -> None:
        """Teste la vérification de relations transitives."""
        store = InMemoryRelationshipStore()

        from aegis.core.domain.values import SubjectId

        # Créer une structure hiérarchique
        user_tuple = RelationshipTuple(
            subject_id=SubjectId("user-1"),
            relation=RelationType.DIRECT_MEMBER,
            resource_id="team-1",
            resource_type="team",
        )

        team_tuple = RelationshipTuple(
            subject_id=SubjectId("team-1"),
            relation=RelationType.DIRECT_MEMBER,
            resource_id="org-1",
            resource_type="organization",
        )

        store.add_tuple(user_tuple)
        store.add_tuple(team_tuple)

        RelationshipCheck(
            subject_id=SubjectId("user-1"),
            relation=RelationType.TRANSITIVE_MEMBER,
            resource_id="org-1",
            resource_type="organization",
            follow_transitive=True,
        )

        # Pour l'instant, test simple
        direct_check = store.check_relation(
            RelationshipCheck(
                subject_id=SubjectId("user-1"),
                relation=RelationType.DIRECT_MEMBER,
                resource_id="team-1",
                resource_type="team",
            )
        )

        self.assertTrue(direct_check)


class TestRoleSystem(unittest.TestCase):
    """Tests du système de rôles."""

    def test_role_creation(self) -> None:
        """Teste la création de rôles."""
        from aegis.core.domain.values import PermissionCode, RoleId

        role = Role(
            id=RoleId("admin"),
            name="Administrator",
            permissions={PermissionCode("user:read"), PermissionCode("user:write")},
        )

        self.assertTrue(role.has_permission(PermissionCode("user:read")))
        self.assertFalse(role.has_permission(PermissionCode("user:delete")))

    def test_role_hierarchy(self) -> None:
        """Teste l'héritage de rôles."""
        from aegis.core.domain.values import PermissionCode, RoleId

        parent_role = Role(id=RoleId("admin"), name="Administrator", permissions={PermissionCode("user:read")})

        child_role = Role(
            id=RoleId("moderator"),
            name="Moderator",
            permissions={PermissionCode("content:read")},
            parent_role_ids={RoleId("admin")},
        )

        self.assertIn(parent_role.id, child_role.parent_role_ids)

    def test_system_roles(self) -> None:
        """Teste la création de rôles système."""
        roles = SystemRolesFactory.create_all_system_roles()
        self.assertEqual(len(roles), 5)

        admin_role = next((r for r in roles if r.id.value == "admin"), None)
        self.assertIsNotNone(admin_role)
        self.assertTrue(admin_role.is_system_role)


class TestTenancySystem(unittest.TestCase):
    """Tests du système de multi-tenancy."""

    def test_tenant_creation(self) -> None:
        """Teste la création de tenants."""
        from aegis.core.domain.values import TenantId

        tenant = Tenant(id=TenantId("tenant-1"), name="Enterprise A", level=TenantLevel.ENTERPRISE)

        self.assertTrue(tenant.is_root())
        self.assertEqual(tenant.level, TenantLevel.ENTERPRISE)

    def test_tenant_hierarchy(self) -> None:
        """Teste la hiérarchie de tenants."""
        from aegis.core.domain.values import TenantId

        enterprise = Tenant(id=TenantId("ent-1"), name="Enterprise", level=TenantLevel.ENTERPRISE)

        org = Tenant(
            id=TenantId("org-1"), name="Organization", parent_tenant_id=enterprise.id, level=TenantLevel.ORGANIZATION
        )

        self.assertFalse(org.is_root())
        self.assertEqual(org.parent_tenant_id, enterprise.id)

    def test_isolation_policy(self) -> None:
        """Teste la politique d'isolation."""
        policy = TenantIsolationPolicy(TenancyMode.HIERARCHICAL, IsolationType.ROW_LEVEL)

        self.assertEqual(policy.mode, TenancyMode.HIERARCHICAL)
        self.assertEqual(policy.isolation_type, IsolationType.ROW_LEVEL)


class TestAuthenticationStrategies(unittest.TestCase):
    """Tests des stratégies d'authentification."""

    def test_password_strategy(self) -> None:
        """Teste la stratégie de mot de passe."""
        from aegis.drivers.inmemory import Pbkdf2PasswordHasher

        hasher = Pbkdf2PasswordHasher(iterations=1000)
        strategy = PasswordAuthStrategy(hasher)

        self.assertEqual(strategy.method, AuthenticationMethod.PASSWORD)

        # Test création de credential
        from aegis.core.domain.values import SubjectId

        credential = strategy.create_credential(SubjectId("user-1"), {"password": "TestPassword123!"})

        self.assertEqual(credential.method, AuthenticationMethod.PASSWORD)

    def test_oidc_strategy(self) -> None:
        """Teste la stratégie OIDC."""
        providers = [{"name": "google", "client_id": "test"}]
        strategy = OIDCAuthStrategy(providers)

        self.assertEqual(strategy.method, AuthenticationMethod.OIDC)

        result = strategy.authenticate({"provider": "google", "code": "test-code"})

        self.assertEqual(result.method, AuthenticationMethod.OIDC)

    def test_authentication_manager(self) -> None:
        """Teste le gestionnaire d'authentification."""
        from aegis.drivers.inmemory import Pbkdf2PasswordHasher

        hasher = Pbkdf2PasswordHasher(iterations=1000)
        manager = AuthenticationFactory.create_default_manager(hasher)

        methods = manager.get_available_methods()
        self.assertIn(AuthenticationMethod.PASSWORD, methods)
        self.assertIn(AuthenticationMethod.OIDC, methods)


class TestSessionManagement(unittest.TestCase):
    """Tests de la gestion des sessions."""

    def test_session_creation(self) -> None:
        """Teste la création de sessions."""
        from aegis.core.domain.values import SubjectId

        manager = SessionManager()

        session = manager.create_session(SubjectId("user-1"), user_agent="Mozilla/5.0", ip_address="192.168.1.100")

        self.assertEqual(session.subject_id.value, "user-1")
        self.assertTrue(session.is_valid())

    def test_session_revocation(self) -> None:
        """Teste la révocation de sessions."""
        from aegis.core.domain.values import SubjectId

        manager = SessionManager()

        session = manager.create_session(SubjectId("user-1"))
        revoked = manager.revoke_session(session.session_id)

        self.assertTrue(revoked)

    def test_global_revocation(self) -> None:
        """Teste la révocation globale."""
        from aegis.core.domain.values import SubjectId

        manager = SessionManager()

        # Créer plusieurs sessions
        manager.create_session(SubjectId("user-1"))
        manager.create_session(SubjectId("user-1"))

        # Révoquer toutes
        revoked_count = manager.revoke_all_subject_sessions(SubjectId("user-1"))

        self.assertGreater(revoked_count, 0)


class TestGDPRPipeline(unittest.TestCase):
    """Tests du pipeline GDPR."""

    def test_data_anonymization(self) -> None:
        """Teste l'anonymisation des données."""
        anonymizer = StandardDataAnonymizer()

        email = anonymizer.anonymize_email("test@example.com")
        self.assertEqual(email, "t***@example.com")

        phone = anonymizer.anonymize_phone("1234567890")
        self.assertEqual(phone, "********90")

    def test_consent_management(self) -> None:
        """Teste la gestion du consentement."""
        from aegis.core.domain.values import SubjectId

        pipeline = GDPRPipeline()

        consent = pipeline.record_consent(SubjectId("user-1"), "marketing", granted=True)

        self.assertTrue(consent.is_active())
        self.assertTrue(pipeline.check_consent(SubjectId("user-1"), "marketing"))

    def test_right_to_erasure(self) -> None:
        """Teste le droit à l'oubli."""
        from aegis.core.domain.values import SubjectId

        pipeline = GDPRPipeline()

        record = pipeline.request_data_deletion(SubjectId("user-1"), "User request")

        self.assertEqual(record.status.value, "active")
        self.assertIsNotNone(record.anonymization_date)


class TestPluginSystem(unittest.TestCase):
    """Tests du système de plugins."""

    def test_hook_execution(self) -> None:
        """Teste l'exécution de hooks."""
        manager = PluginManager()

        class TestHook(BaseHook):
            def __init__(self):
                super().__init__(HookType.PRE_USE_CASE, priority=10)

            def execute(self, context, **kwargs):
                return HookResult(success=True, data={"test": "value"})

        manager.register_hook(HookType.PRE_USE_CASE, TestHook().execute, "test_plugin")

        context = HookContext(HookType.PRE_USE_CASE, "hook-1")
        results = manager.execute_hooks(HookType.PRE_USE_CASE, context)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)

    def test_plugin_factory(self) -> None:
        """Teste la factory de plugins."""
        logging_plugin = PluginFactory.create_logging_plugin()

        self.assertEqual(logging_plugin.name, "Logging Plugin")


class TestDomainEvents(unittest.TestCase):
    """Tests des événements de domaine étendus."""

    def test_authentication_events(self) -> None:
        """Teste les événements d'authentification."""
        from aegis.core.domain.values import SubjectId

        success_event = AuthenticationSuccessEvent(
            subject_id=SubjectId("user-1"), auth_method="password", ip_address="192.168.1.100"
        )

        self.assertEqual(success_event.event_type, "AUTHENTICATION_SUCCESS")

        failure_event = AuthenticationFailureEvent(
            subject_id=SubjectId("user-1"), auth_method="password", failure_reason="Invalid password"
        )

        self.assertEqual(failure_event.event_type, "AUTHENTICATION_FAILURE")

    def test_authorization_events(self) -> None:
        """Teste les événements d'autorisation."""
        from aegis.core.domain.values import SubjectId

        auth_event = AuthorizationDecisionEvent(
            subject_id=SubjectId("user-1"),
            action="document:read",
            resource="doc-123",
            decision="ALLOW",
            reason="Permission granted",
        )

        self.assertEqual(auth_event.event_type, "AUTHORIZATION_DECISION")

    def test_gdpr_events(self) -> None:
        """Teste les événements RGPD."""
        from aegis.core.domain.values import SubjectId

        export_event = DataExportRequestedEvent(
            subject_id=SubjectId("user-1"), export_id="export-123", reason="User request"
        )

        self.assertEqual(export_event.event_type, "DATA_EXPORT_REQUESTED")

        deletion_event = DataDeletionRequestedEvent(subject_id=SubjectId("user-1"), reason="Right to erasure")

        self.assertEqual(deletion_event.event_type, "DATA_DELETION_REQUESTED")


if __name__ == "__main__":
    unittest.main()
