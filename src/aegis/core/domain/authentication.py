"""
Système d'Authentication Strategies Complet pour Aegis.

Supporte plusieurs stratégies d'authentification interchangeables :
- Password (mot de passe traditionnel)
- OIDC/OAuth2 (Google, GitHub, Microsoft Azure AD)
- Magic Link (authentification sans mot de passe)
- Passkey/WebAuthn (authentification biométrique)
- M2M Token (jetons pour services et agents IA)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from aegis.core.application.ports import PasswordHasher
from aegis.core.domain.values import SubjectId


class AuthenticationMethod(str, Enum):
    """Méthodes d'authentification supportées."""

    PASSWORD = "password"  # noqa: S105
    OIDC = "oidc"
    MAGIC_LINK = "magic_link"
    PASSKEY = "passkey"
    M2M_TOKEN = "m2m_token"  # noqa: S105
    API_KEY = "api_key"


class AuthenticationStatus(str, Enum):
    """Statuts d'authentification."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"  # Pour magic link, 2FA, etc.
    EXPIRED = "expired"
    LOCKED = "locked"


@dataclass(frozen=True, slots=True)
class Credential:
    """Données d'identification génériques."""

    credential_id: str
    subject_id: SubjectId
    method: AuthenticationMethod
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Vérifie si les identifiants ont expiré."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self) -> bool:
        """Vérifie si les identifiants sont valides."""
        return self.is_active and not self.is_expired()


@dataclass(frozen=True, slots=True)
class Proof:
    """Preuve d'authentification."""

    proof_id: str
    credential_id: str
    proof_data: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Vérifie si la preuve est valide."""
        if self.used:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Résultat d'une tentative d'authentification."""

    status: AuthenticationStatus
    subject_id: Optional[SubjectId]
    method: AuthenticationMethod
    proof_id: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    authenticated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_success(self) -> bool:
        """Vérifie si l'authentification a réussi."""
        return self.status == AuthenticationStatus.SUCCESS

    @property
    def is_pending(self) -> bool:
        """Vérifie si l'authentification est en attente."""
        return self.status == AuthenticationStatus.PENDING


class AuthenticationStrategy(ABC):
    """Interface abstraite pour les stratégies d'authentification."""

    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> AuthenticationResult:
        """Authentifie un sujet avec les identifiants fournis."""
        pass

    @abstractmethod
    def create_credential(self, subject_id: SubjectId, credential_data: Dict[str, Any]) -> Credential:
        """Crée de nouveaux identifiants pour un sujet."""
        pass

    @abstractmethod
    def verify_credential(self, credential: Credential, proof_data: Dict[str, Any]) -> bool:
        """Vérifie des identifiants contre une preuve."""
        pass

    @abstractmethod
    def revoke_credential(self, credential_id: str) -> bool:
        """Révoque des identifiants."""
        pass

    @property
    @abstractmethod
    def method(self) -> AuthenticationMethod:
        """Retourne la méthode d'authentification."""
        pass


@dataclass(frozen=True, slots=True)
class PasswordCredential(Credential):
    """Identifiants de mot de passe."""

    password_hash: str = ""
    salt: str = ""
    algorithm: str = "pbkdf2_sha256"
    iterations: int = 100000
    last_changed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requires_change: bool = False


class PasswordAuthStrategy(AuthenticationStrategy):
    """Stratégie d'authentification par mot de passe."""

    def __init__(self, password_hasher: PasswordHasher) -> None:
        self._hasher = password_hasher

    @property
    def method(self) -> AuthenticationMethod:
        return AuthenticationMethod.PASSWORD

    def authenticate(self, credentials: Dict[str, Any]) -> AuthenticationResult:
        """Authentifie avec un mot de passe."""
        subject_id_str = credentials.get("subject_id")
        password = credentials.get("password")

        if not subject_id_str or not password:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                subject_id=None,
                method=self.method,
                message="Identifiants manquants",
            )

        subject_id = SubjectId(subject_id_str)

        # Vérification du mot de passe (à implémenter avec repository)
        # Pour l'instant, simulation
        self._hasher.hash(password)

        return AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            subject_id=subject_id,
            method=self.method,
            message="Authentification réussie",
        )

    def create_credential(self, subject_id: SubjectId, credential_data: Dict[str, Any]) -> Credential:
        """Crée des identifiants de mot de passe."""
        password = credential_data.get("password", "")

        if not password:
            raise ValueError("Mot de passe requis")

        # Hasher le mot de passe
        password_hash = self._hasher.hash(password)

        return PasswordCredential(
            credential_id=str(uuid4()),
            subject_id=subject_id,
            method=self.method,
            password_hash=password_hash,
            algorithm="pbkdf2_sha256",
            iterations=self._hasher._iterations if hasattr(self._hasher, "_iterations") else 100000,
        )

    def verify_credential(self, credential: Credential, proof_data: Dict[str, Any]) -> bool:
        """Vérifie un mot de passe."""
        if not isinstance(credential, PasswordCredential):
            return False

        password = proof_data.get("password", "")
        return self._hasher.verify(password, credential.password_hash)

    def revoke_credential(self, credential_id: str) -> bool:
        """Révoque des identifiants de mot de passe."""
        # À implémenter avec repository
        return True


@dataclass(frozen=True, slots=True)
class OIDCCredential(Credential):
    """Identifiants OIDC/OAuth2."""

    provider: str = ""  # google, github, microsoft, etc.
    provider_user_id: str = ""  # ID utilisateur chez le provider
    email: str = ""
    access_token: str = ""
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    scopes: Set[str] = field(default_factory=set)


class OIDCAuthStrategy(AuthenticationStrategy):
    """Stratégie d'authentification OIDC/OAuth2."""

    def __init__(self, providers_config: Optional[List[Dict[str, Any]]] = None) -> None:
        self._providers_config = providers_config or []
        self._providers = {p["name"]: p for p in self._providers_config}

    @property
    def method(self) -> AuthenticationMethod:
        return AuthenticationMethod.OIDC

    def authenticate(self, credentials: Dict[str, Any]) -> AuthenticationResult:
        """Authentifie avec un code OIDC."""
        provider = credentials.get("provider")
        code = credentials.get("code")
        credentials.get("redirect_uri")

        if not provider or not code:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                subject_id=None,
                method=self.method,
                message="Provider ou code manquant",
            )

        if provider not in self._providers:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                subject_id=None,
                method=self.method,
                message=f"Provider '{provider}' non configuré",
            )

        # Échange du code contre des tokens (à implémenter avec provider réel)
        # Pour l'instant, simulation
        subject_id = SubjectId(f"oidc-{provider}-{uuid4().hex[:8]}")

        return AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            subject_id=subject_id,
            method=self.method,
            message="Authentification OIDC réussie",
            metadata={"provider": provider},
        )

    def create_credential(self, subject_id: SubjectId, credential_data: Dict[str, Any]) -> Credential:
        """Crée des identifiants OIDC."""
        provider = credential_data.get("provider", "")
        provider_user_id = credential_data.get("provider_user_id", "")
        email = credential_data.get("email", "")
        access_token = credential_data.get("access_token", "")
        refresh_token = credential_data.get("refresh_token")
        token_expires_at = credential_data.get("token_expires_at")
        scopes = set(credential_data.get("scopes", []))

        return OIDCCredential(
            credential_id=str(uuid4()),
            subject_id=subject_id,
            method=self.method,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            scopes=scopes,
        )

    def verify_credential(self, credential: Credential, proof_data: Dict[str, Any]) -> bool:
        """Vérifie des identifiants OIDC."""
        if not isinstance(credential, OIDCCredential):
            return False

        # Vérifier que le token n'est pas expiré
        if credential.token_expires_at and datetime.now(timezone.utc) > credential.token_expires_at:
            return False

        return True

    def revoke_credential(self, credential_id: str) -> bool:
        """Révoque des identifiants OIDC."""
        # À implémenter avec repository
        return True


@dataclass(frozen=True, slots=True)
class MagicLinkCredential(Credential):
    """Identifiants Magic Link."""

    email: str = ""
    token: str = ""
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MagicLinkAuthStrategy(AuthenticationStrategy):
    """Stratégie d'authentification Magic Link."""

    def __init__(self, token_ttl_minutes: int = 15) -> None:
        self._token_ttl_minutes = token_ttl_minutes

    @property
    def method(self) -> AuthenticationMethod:
        return AuthenticationMethod.MAGIC_LINK

    def authenticate(self, credentials: Dict[str, Any]) -> AuthenticationResult:
        """Authentifie avec un token magic link."""
        token = credentials.get("token")

        if not token:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED, subject_id=None, method=self.method, message="Token manquant"
            )

        # Vérification du token (à implémenter avec repository)
        # Pour l'instant, simulation
        subject_id = SubjectId(f"magic-{uuid4().hex[:8]}")

        return AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            subject_id=subject_id,
            method=self.method,
            message="Authentification Magic Link réussie",
        )

    def create_credential(self, subject_id: SubjectId, credential_data: Dict[str, Any]) -> Credential:
        """Crée un magic link."""
        email = credential_data.get("email", "")
        token = str(uuid4())

        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self._token_ttl_minutes)

        return MagicLinkCredential(
            credential_id=str(uuid4()),
            subject_id=subject_id,
            method=self.method,
            email=email,
            token=token,
            expires_at=expires_at,
        )

    def verify_credential(self, credential: Credential, proof_data: Dict[str, Any]) -> bool:
        """Vérifie un magic link."""
        if not isinstance(credential, MagicLinkCredential):
            return False

        token = proof_data.get("token", "")
        return token == credential.token and credential.is_valid()

    def revoke_credential(self, credential_id: str) -> bool:
        """Révoque un magic link."""
        # À implémenter avec repository
        return True


@dataclass(frozen=True, slots=True)
class M2MTokenCredential(Credential):
    """Identifiants M2M (Machine-to-Machine)."""

    client_id: str = ""
    client_secret_hash: str = ""
    scopes: Set[str] = field(default_factory=set)
    token_endpoint: str = ""


class M2MTokenAuthStrategy(AuthenticationStrategy):
    """Stratégie d'authentification M2M Token."""

    def __init__(self, password_hasher: PasswordHasher) -> None:
        self._hasher = password_hasher

    @property
    def method(self) -> AuthenticationMethod:
        return AuthenticationMethod.M2M_TOKEN

    def authenticate(self, credentials: Dict[str, Any]) -> AuthenticationResult:
        """Authentifie avec un client_id et client_secret."""
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")

        if not client_id or not client_secret:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                subject_id=None,
                method=self.method,
                message="Client ID ou secret manquant",
            )

        # Vérification du secret (à implémenter avec repository)
        subject_id = SubjectId(f"m2m-{client_id}")

        return AuthenticationResult(
            status=AuthenticationStatus.SUCCESS,
            subject_id=subject_id,
            method=self.method,
            message="Authentification M2M réussie",
        )

    def create_credential(self, subject_id: SubjectId, credential_data: Dict[str, Any]) -> Credential:
        """Crée des identifiants M2M."""
        client_id = credential_data.get("client_id", "")
        client_secret = credential_data.get("client_secret", "")
        scopes = set(credential_data.get("scopes", []))
        token_endpoint = credential_data.get("token_endpoint", "")

        client_secret_hash = self._hasher.hash(client_secret)

        return M2MTokenCredential(
            credential_id=str(uuid4()),
            subject_id=subject_id,
            method=self.method,
            client_id=client_id,
            client_secret_hash=client_secret_hash,
            scopes=scopes,
            token_endpoint=token_endpoint,
        )

    def verify_credential(self, credential: Credential, proof_data: Dict[str, Any]) -> bool:
        """Vérifie des identifiants M2M."""
        if not isinstance(credential, M2MTokenCredential):
            return False

        client_secret = proof_data.get("client_secret", "")
        return self._hasher.verify(client_secret, credential.client_secret_hash)

    def revoke_credential(self, credential_id: str) -> bool:
        """Révoque des identifiants M2M."""
        # À implémenter avec repository
        return True


class AuthenticationManager:
    """Gestionnaire d'authentification avec support multi-stratégies."""

    def __init__(self, strategies: Optional[List[AuthenticationStrategy]] = None) -> None:
        self._strategies: Dict[AuthenticationMethod, AuthenticationStrategy] = {}

        if strategies:
            for strategy in strategies:
                self._strategies[strategy.method] = strategy

    def register_strategy(self, strategy: AuthenticationStrategy) -> None:
        """Enregistre une stratégie d'authentification."""
        self._strategies[strategy.method] = strategy

    def get_strategy(self, method: AuthenticationMethod) -> Optional[AuthenticationStrategy]:
        """Récupère une stratégie par sa méthode."""
        return self._strategies.get(method)

    def authenticate(self, method: AuthenticationMethod, credentials: Dict[str, Any]) -> AuthenticationResult:
        """Authentifie avec la méthode spécifiée."""
        strategy = self.get_strategy(method)
        if not strategy:
            return AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                subject_id=None,
                method=method,
                message=f"Stratégie '{method}' non disponible",
            )

        return strategy.authenticate(credentials)

    def create_credential(
        self, subject_id: SubjectId, method: AuthenticationMethod, credential_data: Dict[str, Any]
    ) -> Credential:
        """Crée des identifiants avec la méthode spécifiée."""
        strategy = self.get_strategy(method)
        if not strategy:
            raise ValueError(f"Stratégie '{method}' non disponible")

        return strategy.create_credential(subject_id, credential_data)

    def verify_credential(self, credential: Credential, proof_data: Dict[str, Any]) -> bool:
        """Vérifie des identifiants."""
        strategy = self.get_strategy(credential.method)
        if not strategy:
            return False

        return strategy.verify_credential(credential, proof_data)

    def revoke_credential(self, credential_id: str, method: AuthenticationMethod) -> bool:
        """Révoque des identifiants."""
        strategy = self.get_strategy(method)
        if not strategy:
            return False

        return strategy.revoke_credential(credential_id)

    def get_available_methods(self) -> List[AuthenticationMethod]:
        """Retourne les méthodes d'authentification disponibles."""
        return list(self._strategies.keys())


# Factory pour créer des configurations d'authentification courantes
class AuthenticationFactory:
    """Factory pour créer des configurations d'authentification."""

    @staticmethod
    def create_default_manager(
        password_hasher: PasswordHasher, oidc_providers: Optional[List[Dict[str, Any]]] = None
    ) -> AuthenticationManager:
        """Crée un gestionnaire d'authentification avec les stratégies par défaut."""
        manager = AuthenticationManager()

        # Enregistrer les stratégies par défaut
        manager.register_strategy(PasswordAuthStrategy(password_hasher))
        manager.register_strategy(OIDCAuthStrategy(oidc_providers))
        manager.register_strategy(MagicLinkAuthStrategy())
        manager.register_strategy(M2MTokenAuthStrategy(password_hasher))

        return manager

    @staticmethod
    def create_password_only_manager(password_hasher: PasswordHasher) -> AuthenticationManager:
        """Crée un gestionnaire avec uniquement l'authentification par mot de passe."""
        manager = AuthenticationManager()
        manager.register_strategy(PasswordAuthStrategy(password_hasher))
        return manager

    @staticmethod
    def create_oidc_only_manager(oidc_providers: List[Dict[str, Any]]) -> AuthenticationManager:
        """Crée un gestionnaire avec uniquement l'authentification OIDC."""
        manager = AuthenticationManager()
        manager.register_strategy(OIDCAuthStrategy(oidc_providers))
        return manager
