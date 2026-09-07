"""
Système de Configuration Déclarative Dynamique pour Aegis.

Charge et valide la configuration depuis un fichier YAML et des variables d'environnement,
permettant une personnalisation complète sans modification du code source.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ConfigurationError(Exception):
    """Erreur levée lors de la validation de la configuration."""

    pass


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Configuration du driver de stockage."""

    driver: str = "inmemory"
    sqlalchemy_url: str = "sqlite:///./aegis.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


@dataclass(frozen=True, slots=True)
class PolicyEngineConfig:
    """Configuration des moteurs de politiques."""

    primary: str = "rbac"
    composite_strategy: str = "first_applicable"
    composite_engines: List[str] = field(default_factory=lambda: ["rbac"])


@dataclass(frozen=True, slots=True)
class AuthenticationConfig:
    """Configuration des stratégies d'authentification."""

    strategies: List[str] = field(default_factory=lambda: ["password"])
    password_algorithm: str = field(default="pbkdf2_sha256")
    password_iterations: int = 100000
    oidc_providers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TenancyConfig:
    """Configuration du multi-tenancy."""

    mode: str = "flat"  # flat, single, hierarchical
    isolation_type: str = "row_level"  # row_level, database, schema
    hierarchy_enabled: bool = False
    hierarchy_levels: List[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SessionConfig:
    """Configuration de la gestion des sessions."""

    enabled: bool = True
    backend: str = "redis"  # redis, memory, database
    redis_url: str = "redis://localhost:6379/0"
    ttl: int = 3600
    max_sessions_per_user: int = 5
    global_revocation_enabled: bool = True


@dataclass(frozen=True, slots=True)
class AuditConfig:
    """Configuration de l'audit et de l'outbox."""

    outbox_enabled: bool = True
    outbox_backend: str = "database"  # database, redis, kafka
    batch_size: int = 50
    worker_enabled: bool = True
    worker_concurrency: int = 2
    retention_days: int = 90
    anonymization_enabled: bool = True


@dataclass(frozen=True, slots=True)
class GDPRConfig:
    """Configuration de la conformité RGPD."""

    enabled: bool = True
    right_to_erasure_enabled: bool = True
    anonymization_delay_days: int = 30
    hard_delete_after_days: int = 365
    data_export_enabled: bool = True
    data_export_format: str = "json"


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Configuration du cache."""

    enabled: bool = True
    backend: str = "redis"  # redis, memory
    redis_url: str = "redis://localhost:6379/1"
    ttl: int = 300
    auth_decisions_enabled: bool = True
    auth_decisions_ttl: int = 60


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Configuration du système de validation."""

    strict_mode: bool = True
    custom_validators: List[str] = field(default_factory=list)
    email_regex: str = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    email_check_deliverability: bool = False
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special_chars: bool = True


@dataclass(frozen=True, slots=True)
class PluginConfig:
    """Configuration du système de plugins."""

    enabled: bool = True
    directories: List[str] = field(default_factory=lambda: ["./plugins"])
    hooks: List[str] = field(
        default_factory=lambda: [
            "pre_use_case",
            "post_use_case",
            "pre_authorization",
            "post_authorization",
            "pre_authentication",
            "post_authentication",
        ]
    )


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Configuration de la sécurité."""

    secret_key: str = ""
    cors_enabled: bool = True
    cors_origins: str = "*"
    cors_allow_credentials: bool = True
    rate_limiting_enabled: bool = True
    rate_limiting_rpm: int = 60
    rate_limiting_burst: int = 10
    encryption_enabled: bool = False
    encryption_algorithm: str = "aes-256-gcm"


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    """Configuration de l'observabilité."""

    metrics_enabled: bool = True
    metrics_backend: str = "prometheus"
    metrics_port: int = 9090
    tracing_enabled: bool = False
    tracing_backend: str = "jaeger"
    logging_format: str = "json"
    correlation_id_enabled: bool = True
    correlation_id_header: str = "X-Request-ID"


@dataclass(frozen=True, slots=True)
class APIConfig:
    """Configuration de l'API."""

    framework: str = "fastapi"
    host: str = "0.0.0.0"
    port: int = 8000
    docs_enabled: bool = True
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"


@dataclass(frozen=True, slots=True)
class TestingConfig:
    """Configuration des tests."""

    mock_external_services: bool = True
    use_test_database: bool = True
    parallel: bool = False
    coverage_enabled: bool = True
    coverage_min_percentage: int = 80


@dataclass(frozen=True, slots=True)
class AegisConfig:
    """Configuration complète d'Aegis."""

    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    storage: StorageConfig = field(default_factory=StorageConfig)
    policy_engines: PolicyEngineConfig = field(default_factory=PolicyEngineConfig)
    authentication: AuthenticationConfig = field(default_factory=AuthenticationConfig)
    tenancy: TenancyConfig = field(default_factory=TenancyConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    gdpr: GDPRConfig = field(default_factory=GDPRConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    api: APIConfig = field(default_factory=APIConfig)
    testing: TestingConfig = field(default_factory=TestingConfig)


class ConfigLoader:
    """Chargeur de configuration avec support YAML et variables d'environnement."""

    DEFAULT_CONFIG_PATHS = [
        "aegis.config.yaml",
        "aegis.config.yml",
        "config/aegis.config.yaml",
        "config/aegis.config.yml",
        ".aegis/config.yaml",
    ]

    def __init__(self, config_path: Optional[str | Path] = None):
        self.config_path = self._find_config_path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self._config: Optional[AegisConfig] = None

    def _find_config_path(self, config_path: Optional[str | Path]) -> Optional[Path]:
        """Trouve le fichier de configuration."""
        if config_path:
            path = Path(config_path)
            if path.exists():
                return path
            return None

        for default_path in self.DEFAULT_CONFIG_PATHS:
            path = Path(default_path)
            if path.exists():
                return path

        return None

    def _substitute_env_vars(self, value: Any) -> Any:
        """Substitue les variables d'environnement dans les valeurs."""
        if isinstance(value, str):
            # Pattern ${VAR_NAME} ou $VAR_NAME
            pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"

            def replace_env_var(match: Any) -> str:
                var_name = match.group(1) or match.group(2)
                return os.getenv(var_name, match.group(0))

            return re.sub(pattern, replace_env_var, value)

        elif isinstance(value, dict):
            return {k: self._substitute_env_vars(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self._substitute_env_vars(item) for item in value]

        return value

    def load(self) -> AegisConfig:
        """Charge et valide la configuration."""
        if self._config is not None:
            return self._config

        self._raw_config = self._load_yaml_file()
        self._raw_config = self._substitute_env_vars(self._raw_config)

        self._config = self._build_config_object()
        self._validate_config()

        return self._config

    def _load_yaml_file(self) -> Dict[str, Any]:
        """Charge le fichier YAML."""
        if not self.config_path or not YAML_AVAILABLE:
            return {}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Erreur lors du chargement du fichier de configuration: {e}") from e

    def _build_config_object(self) -> AegisConfig:
        """Construit l'objet de configuration depuis les données brutes."""
        raw = self._raw_config

        return AegisConfig(
            environment=raw.get("environment", {}).get("mode", "development"),
            debug=raw.get("environment", {}).get("debug", True),
            log_level=raw.get("environment", {}).get("log_level", "INFO"),
            storage=self._build_storage_config(raw.get("storage", {})),
            policy_engines=self._build_policy_engine_config(raw.get("policy_engines", {})),
            authentication=self._build_authentication_config(raw.get("authentication", {})),
            tenancy=self._build_tenancy_config(raw.get("tenancy", {})),
            sessions=self._build_session_config(raw.get("sessions", {})),
            audit=self._build_audit_config(raw.get("audit", {})),
            gdpr=self._build_gdpr_config(raw.get("gdpr", {})),
            cache=self._build_cache_config(raw.get("cache", {})),
            validation=self._build_validation_config(raw.get("validation", {})),
            plugins=self._build_plugin_config(raw.get("plugins", {})),
            security=self._build_security_config(raw.get("security", {})),
            observability=self._build_observability_config(raw.get("observability", {})),
            api=self._build_api_config(raw.get("api", {})),
            testing=self._build_testing_config(raw.get("testing", {})),
        )

    def _build_storage_config(self, raw: Dict[str, Any]) -> StorageConfig:
        """Construit la configuration de stockage."""
        sqlalchemy_config = raw.get("sqlalchemy", {})
        return StorageConfig(
            driver=raw.get("driver", "inmemory"),
            sqlalchemy_url=sqlalchemy_config.get("url", "sqlite:///./aegis.db"),
            pool_size=sqlalchemy_config.get("pool_size", 5),
            max_overflow=sqlalchemy_config.get("max_overflow", 10),
            echo=sqlalchemy_config.get("echo", False),
        )

    def _build_policy_engine_config(self, raw: Dict[str, Any]) -> PolicyEngineConfig:
        """Construit la configuration des moteurs de politiques."""
        composite_config = raw.get("composite", {})
        return PolicyEngineConfig(
            primary=raw.get("primary", "rbac"),
            composite_strategy=composite_config.get("strategy", "first_applicable"),
            composite_engines=composite_config.get("engines", ["rbac"]),
        )

    def _build_authentication_config(self, raw: Dict[str, Any]) -> AuthenticationConfig:
        """Construit la configuration d'authentification."""
        password_config = raw.get("password", {})
        oidc_config = raw.get("oidc", {})
        return AuthenticationConfig(
            strategies=raw.get("strategies", ["password"]),
            password_algorithm=password_config.get("algorithm", "pbkdf2_sha256"),
            password_iterations=password_config.get("iterations", 100000),
            oidc_providers=oidc_config.get("providers", []),
        )

    def _build_tenancy_config(self, raw: Dict[str, Any]) -> TenancyConfig:
        """Construit la configuration de multi-tenancy."""
        isolation_config = raw.get("isolation", {})
        hierarchy_config = raw.get("hierarchy", {})
        return TenancyConfig(
            mode=raw.get("mode", "flat"),
            isolation_type=isolation_config.get("type", "row_level"),
            hierarchy_enabled=hierarchy_config.get("enabled", False),
            hierarchy_levels=hierarchy_config.get("levels", []),
        )

    def _build_session_config(self, raw: Dict[str, Any]) -> SessionConfig:
        """Construit la configuration des sessions."""
        redis_config = raw.get("redis", {})
        return SessionConfig(
            enabled=raw.get("enabled", True),
            backend=raw.get("backend", "redis"),
            redis_url=redis_config.get("url", "redis://localhost:6379/0"),
            ttl=raw.get("ttl", 3600),
            max_sessions_per_user=raw.get("max_sessions_per_user", 5),
            global_revocation_enabled=raw.get("global_revocation_enabled", True),
        )

    def _build_audit_config(self, raw: Dict[str, Any]) -> AuditConfig:
        """Construit la configuration de l'audit."""
        outbox_config = raw.get("outbox", {})
        retention_config = raw.get("retention", {})
        return AuditConfig(
            outbox_enabled=outbox_config.get("enabled", True),
            outbox_backend=outbox_config.get("backend", "database"),
            batch_size=outbox_config.get("batch_size", 50),
            worker_enabled=outbox_config.get("worker_enabled", True),
            worker_concurrency=outbox_config.get("worker_concurrency", 2),
            retention_days=retention_config.get("days", 90),
            anonymization_enabled=retention_config.get("anonymization_enabled", True),
        )

    def _build_gdpr_config(self, raw: Dict[str, Any]) -> GDPRConfig:
        """Construit la configuration RGPD."""
        erasure_config = raw.get("right_to_erasure", {})
        export_config = raw.get("data_export", {})
        return GDPRConfig(
            enabled=raw.get("enabled", True),
            right_to_erasure_enabled=erasure_config.get("enabled", True),
            anonymization_delay_days=erasure_config.get("anonymization_delay_days", 30),
            hard_delete_after_days=erasure_config.get("hard_delete_after_days", 365),
            data_export_enabled=export_config.get("enabled", True),
            data_export_format=export_config.get("format", "json"),
        )

    def _build_cache_config(self, raw: Dict[str, Any]) -> CacheConfig:
        """Construit la configuration du cache."""
        redis_config = raw.get("redis", {})
        auth_config = raw.get("authorization_decisions", {})
        return CacheConfig(
            enabled=raw.get("enabled", True),
            backend=raw.get("backend", "redis"),
            redis_url=redis_config.get("url", "redis://localhost:6379/1"),
            ttl=raw.get("ttl", 300),
            auth_decisions_enabled=auth_config.get("enabled", True),
            auth_decisions_ttl=auth_config.get("ttl", 60),
        )

    def _build_validation_config(self, raw: Dict[str, Any]) -> ValidationConfig:
        """Construit la configuration de validation."""
        email_config = raw.get("email", {})
        password_config = raw.get("password", {})
        return ValidationConfig(
            strict_mode=raw.get("strict_mode", True),
            custom_validators=raw.get("custom_validators", []),
            email_regex=email_config.get("regex", r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
            email_check_deliverability=email_config.get("check_deliverability", False),
            password_min_length=password_config.get("min_length", 8),
            password_require_uppercase=password_config.get("require_uppercase", True),
            password_require_lowercase=password_config.get("require_lowercase", True),
            password_require_numbers=password_config.get("require_numbers", True),
            password_require_special_chars=password_config.get("require_special_chars", True),
        )

    def _build_plugin_config(self, raw: Dict[str, Any]) -> PluginConfig:
        """Construit la configuration des plugins."""
        return PluginConfig(
            enabled=raw.get("enabled", True),
            directories=raw.get("directories", ["./plugins"]),
            hooks=raw.get(
                "hooks",
                [
                    "pre_use_case",
                    "post_use_case",
                    "pre_authorization",
                    "post_authorization",
                    "pre_authentication",
                    "post_authentication",
                ],
            ),
        )

    def _build_security_config(self, raw: Dict[str, Any]) -> SecurityConfig:
        """Construit la configuration de sécurité."""
        cors_config = raw.get("cors", {})
        rate_limit_config = raw.get("rate_limiting", {})
        encryption_config = raw.get("encryption", {})
        return SecurityConfig(
            secret_key=raw.get("secret_key", ""),
            cors_enabled=cors_config.get("enabled", True),
            cors_origins=cors_config.get("origins", "*"),
            cors_allow_credentials=cors_config.get("allow_credentials", True),
            rate_limiting_enabled=rate_limit_config.get("enabled", True),
            rate_limiting_rpm=rate_limit_config.get("requests_per_minute", 60),
            rate_limiting_burst=rate_limit_config.get("burst", 10),
            encryption_enabled=encryption_config.get("enabled", False),
            encryption_algorithm=encryption_config.get("algorithm", "aes-256-gcm"),
        )

    def _build_observability_config(self, raw: Dict[str, Any]) -> ObservabilityConfig:
        """Construit la configuration d'observabilité."""
        metrics_config = raw.get("metrics", {})
        tracing_config = raw.get("tracing", {})
        logging_config = raw.get("logging", {})
        correlation_config = raw.get("correlation_id", {})
        return ObservabilityConfig(
            metrics_enabled=metrics_config.get("enabled", True),
            metrics_backend=metrics_config.get("backend", "prometheus"),
            metrics_port=metrics_config.get("port", 9090),
            tracing_enabled=tracing_config.get("enabled", False),
            tracing_backend=tracing_config.get("backend", "jaeger"),
            logging_format=logging_config.get("format", "json"),
            correlation_id_enabled=correlation_config.get("enabled", True),
            correlation_id_header=correlation_config.get("header_name", "X-Request-ID"),
        )

    def _build_api_config(self, raw: Dict[str, Any]) -> APIConfig:
        """Construit la configuration de l'API."""
        return APIConfig(
            framework=raw.get("framework", "fastapi"),
            host=raw.get("host", "0.0.0.0"),
            port=raw.get("port", 8000),
            docs_enabled=raw.get("docs_enabled", True),
            docs_url=raw.get("docs_url", "/docs"),
            redoc_url=raw.get("redoc_url", "/redoc"),
        )

    def _build_testing_config(self, raw: Dict[str, Any]) -> TestingConfig:
        """Construit la configuration des tests."""
        coverage_config = raw.get("coverage", {})
        return TestingConfig(
            mock_external_services=raw.get("mock_external_services", True),
            use_test_database=raw.get("use_test_database", True),
            parallel=raw.get("parallel", False),
            coverage_enabled=coverage_config.get("enabled", True),
            coverage_min_percentage=coverage_config.get("min_percentage", 80),
        )

    def _validate_config(self) -> None:
        """Valide la configuration chargée."""
        if self._config is None:
            return

        config = self._config

        # Validation des valeurs enum
        valid_modes = ["development", "test", "production"]
        if config.environment not in valid_modes:
            raise ConfigurationError(f"environment.mode doit être l'un de {valid_modes}")

        valid_storage_drivers = ["inmemory", "sqlalchemy", "django"]
        if config.storage.driver not in valid_storage_drivers:
            raise ConfigurationError(f"storage.driver doit être l'un de {valid_storage_drivers}")

        valid_policy_engines = ["rbac", "abac", "rebac", "composite"]
        if config.policy_engines.primary not in valid_policy_engines:
            raise ConfigurationError(f"policy_engines.primary doit être l'un de {valid_policy_engines}")

        valid_tenancy_modes = ["flat", "single", "hierarchical"]
        if config.tenancy.mode not in valid_tenancy_modes:
            raise ConfigurationError(f"tenancy.mode doit être l'un de {valid_tenancy_modes}")

        # Validation de la clé secrète en production
        if config.environment == "production" and not config.security.secret_key:
            raise ConfigurationError("security.secret_key est obligatoire en production")

        # Validation des taux de limitation
        if config.security.rate_limiting_rpm <= 0:
            raise ConfigurationError("security.rate_limiting_rpm doit être positif")

        # Validation du TTL de cache
        if config.cache.ttl <= 0:
            raise ConfigurationError("cache.ttl doit être positif")


# Instance globale du chargeur de configuration
_global_config_loader: Optional[ConfigLoader] = None
_global_config: Optional[AegisConfig] = None


def load_config(config_path: Optional[str | Path] = None) -> AegisConfig:
    """Charge la configuration Aegis."""
    global _global_config_loader, _global_config

    if _global_config is not None and config_path is None:
        return _global_config

    _global_config_loader = ConfigLoader(config_path)
    _global_config = _global_config_loader.load()

    return _global_config


def get_config() -> AegisConfig:
    """Retourne la configuration chargée."""
    if _global_config is None:
        return load_config()
    return _global_config


def reset_config() -> None:
    """Réinitialise la configuration (utile pour les tests)."""
    global _global_config_loader, _global_config
    _global_config_loader = None
    _global_config = None
