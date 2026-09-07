"""
Système de Validation et Sanitization Extensible pour Aegis.

Permet une configuration dynamique des règles de validation et l'ajout de validateurs
personnalisés sans modifier le code cœur du système.
"""

import re
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

from aegis.core.config_loader import ValidationConfig, get_config


class ValidationError(Exception):
    """Erreur levée lors de la validation."""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation error for field '{field}': {message}")


class ValidationResult:
    """Résultat d'une validation avec détails sur les erreurs."""

    def __init__(self, is_valid: bool, errors: Optional[List[ValidationError]] = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def add_error(self, error: ValidationError) -> None:
        """Ajoute une erreur de validation."""
        self.errors.append(error)
        self.is_valid = False

    def merge(self, other: "ValidationResult") -> None:
        """Fusionne ce résultat avec un autre."""
        self.errors.extend(other.errors)
        self.is_valid = self.is_valid and other.is_valid

    @property
    def error_messages(self) -> List[str]:
        """Retourne les messages d'erreur sous forme de liste."""
        return [error.message for error in self.errors]


T = TypeVar("T")


class Validator(ABC):
    """Interface abstraite pour les validateurs."""

    @abstractmethod
    def validate(self, value: Any, field_name: str = "value") -> ValidationResult:
        """Valide une valeur et retourne le résultat."""
        pass

    @abstractmethod
    def sanitize(self, value: Any) -> Any:
        """Nettoie/sanitise une valeur."""
        pass


@dataclass(frozen=True, slots=True)
class EmailValidator(Validator):
    """Validateur d'emails configurable."""

    regex: str = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    check_deliverability: bool = False
    allowed_domains: Set[str] = field(default_factory=set)
    blocked_domains: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Compile la regex pour la performance."""
        object.__setattr__(self, "_compiled_regex", re.compile(self.regex))

    def validate(self, value: Any, field_name: str = "email") -> ValidationResult:
        """Valide un email."""
        result = ValidationResult(is_valid=True)

        if not value or not isinstance(value, str):
            result.add_error(ValidationError(field_name, "Email must be a non-empty string", value))
            return result

        email = value.strip().lower()

        # Validation regex
        compiled_regex = getattr(self, "_compiled_regex", re.compile(self.regex))
        if not compiled_regex.match(email):
            result.add_error(ValidationError(field_name, f"Email format is invalid: {email}", value))

        # Validation des domaines autorisés
        if self.allowed_domains:
            domain = email.split("@")[1] if "@" in email else ""
            if domain not in self.allowed_domains:
                result.add_error(ValidationError(field_name, f"Email domain '{domain}' is not allowed", value))

        # Validation des domaines bloqués
        if self.blocked_domains:
            domain = email.split("@")[1] if "@" in email else ""
            if domain in self.blocked_domains:
                result.add_error(ValidationError(field_name, f"Email domain '{domain}' is blocked", value))

        return result

    def sanitize(self, value: Any) -> str:
        """Nettoie un email (trim, lowercase)."""
        if not value or not isinstance(value, str):
            return ""
        return value.strip().lower()


@dataclass(frozen=True, slots=True)
class PasswordValidator(Validator):
    """Validateur de mots de passe configurable."""

    min_length: int = 8
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special_chars: bool = True
    forbidden_patterns: List[str] = field(default_factory=list)
    forbidden_common_passwords: Set[str] = field(
        default_factory=lambda: {"password", "123456", "qwerty", "admin", "letmein", "welcome"}
    )

    def validate(self, value: Any, field_name: str = "password") -> ValidationResult:
        """Valide un mot de passe."""
        result = ValidationResult(is_valid=True)

        if not value or not isinstance(value, str):
            result.add_error(ValidationError(field_name, "Password must be a non-empty string", value))
            return result

        password = value

        # Validation longueur
        if len(password) < self.min_length:
            result.add_error(
                ValidationError(field_name, f"Password must be at least {self.min_length} characters long", value)
            )

        if len(password) > self.max_length:
            result.add_error(
                ValidationError(field_name, f"Password must not exceed {self.max_length} characters", value)
            )

        # Validation majuscules
        if self.require_uppercase and not any(c.isupper() for c in password):
            result.add_error(ValidationError(field_name, "Password must contain at least one uppercase letter", value))

        # Validation minuscules
        if self.require_lowercase and not any(c.islower() for c in password):
            result.add_error(ValidationError(field_name, "Password must contain at least one lowercase letter", value))

        # Validation chiffres
        if self.require_numbers and not any(c.isdigit() for c in password):
            result.add_error(ValidationError(field_name, "Password must contain at least one number", value))

        # Validation caractères spéciaux
        if self.require_special_chars:
            special_chars = set(string.punctuation)
            if not any(c in special_chars for c in password):
                result.add_error(
                    ValidationError(field_name, "Password must contain at least one special character", value)
                )

        # Validation patterns interdits
        for pattern in self.forbidden_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                result.add_error(ValidationError(field_name, f"Password contains forbidden pattern: {pattern}", value))

        # Validation mots de passe courants
        if password.lower() in self.forbidden_common_passwords:
            result.add_error(ValidationError(field_name, "Password is too common and easily guessable", value))

        return result

    def sanitize(self, value: Any) -> str:
        """Nettoie un mot de passe (trim)."""
        if not value or not isinstance(value, str):
            return ""
        return value.strip()


@dataclass(frozen=True, slots=True)
class StringValidator(Validator):
    """Validateur de chaînes de caractères générique."""

    min_length: int = 0
    max_length: int = 1000
    allowed_chars: Optional[str] = None  # Si défini, seuls ces caractères sont autorisés
    forbidden_chars: Optional[str] = None  # Si défini, ces caractères sont interdits
    regex_pattern: Optional[str] = None
    trim: bool = True
    lowercase: bool = False
    uppercase: bool = False

    def __post_init__(self) -> None:
        """Compile la regex si fournie."""
        if self.regex_pattern:
            object.__setattr__(self, "_compiled_regex", re.compile(self.regex_pattern))
        else:
            object.__setattr__(self, "_compiled_regex", None)

    def validate(self, value: Any, field_name: str = "string") -> ValidationResult:
        """Valide une chaîne de caractères."""
        result = ValidationResult(is_valid=True)

        if value is None:
            if self.min_length > 0:
                result.add_error(ValidationError(field_name, "String cannot be None", value))
            return result

        if not isinstance(value, str):
            result.add_error(ValidationError(field_name, "Value must be a string", value))
            return result

        string_value = value

        # Validation longueur
        if len(string_value) < self.min_length:
            result.add_error(
                ValidationError(field_name, f"String must be at least {self.min_length} characters long", value)
            )

        if len(string_value) > self.max_length:
            result.add_error(ValidationError(field_name, f"String must not exceed {self.max_length} characters", value))

        # Validation caractères autorisés
        if self.allowed_chars:
            if not all(c in self.allowed_chars for c in string_value):
                result.add_error(
                    ValidationError(
                        field_name, f"String contains characters not in allowed set: {self.allowed_chars}", value
                    )
                )

        # Validation caractères interdits
        if self.forbidden_chars:
            if any(c in self.forbidden_chars for c in string_value):
                result.add_error(
                    ValidationError(field_name, f"String contains forbidden characters: {self.forbidden_chars}", value)
                )

        # Validation regex
        compiled_regex = getattr(self, "_compiled_regex", None)
        if compiled_regex and not compiled_regex.match(string_value):
            result.add_error(
                ValidationError(field_name, f"String does not match required pattern: {self.regex_pattern}", value)
            )

        return result

    def sanitize(self, value: Any) -> str:
        """Nettoie une chaîne de caractères."""
        if not value or not isinstance(value, str):
            return ""

        result = value

        if self.trim:
            result = result.strip()

        if self.lowercase:
            result = result.lower()

        if self.uppercase:
            result = result.upper()

        return result


@dataclass(frozen=True, slots=True)
class NumericValidator(Validator):
    """Validateur de nombres générique."""

    min_value: Optional[float] = None
    max_value: Optional[float] = None
    integer_only: bool = False
    allow_negative: bool = True
    allow_zero: bool = True

    def validate(self, value: Any, field_name: str = "number") -> ValidationResult:
        """Valide un nombre."""
        result = ValidationResult(is_valid=True)

        if value is None:
            result.add_error(ValidationError(field_name, "Number cannot be None", value))
            return result

        # Vérification du type
        if self.integer_only:
            if not isinstance(value, int):
                result.add_error(ValidationError(field_name, "Value must be an integer", value))
                return result
        else:
            if not isinstance(value, (int, float)):
                result.add_error(ValidationError(field_name, "Value must be a number", value))
                return result

        numeric_value = float(value)

        # Validation valeur minimale
        if self.min_value is not None and numeric_value < self.min_value:
            result.add_error(ValidationError(field_name, f"Value must be at least {self.min_value}", value))

        # Validation valeur maximale
        if self.max_value is not None and numeric_value > self.max_value:
            result.add_error(ValidationError(field_name, f"Value must not exceed {self.max_value}", value))

        # Validation nombres négatifs
        if not self.allow_negative and numeric_value < 0:
            result.add_error(ValidationError(field_name, "Negative values are not allowed", value))

        # Validation zéro
        if not self.allow_zero and numeric_value == 0:
            result.add_error(ValidationError(field_name, "Zero value is not allowed", value))

        return result

    def sanitize(self, value: Any) -> float:
        """Nettoie et convertit en nombre."""
        if value is None:
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0


class CustomValidator(Validator):
    """Validateur personnalisé utilisant une fonction lambda."""

    def __init__(
        self, validate_func: Callable[[Any], ValidationResult], sanitize_func: Optional[Callable[[Any], Any]] = None
    ):
        self._validate_func = validate_func
        self._sanitize_func = sanitize_func or (lambda x: x)

    def validate(self, value: Any, field_name: str = "custom") -> ValidationResult:
        """Valide en utilisant la fonction personnalisée."""
        return self._validate_func(value)

    def sanitize(self, value: Any) -> Any:
        """Nettoie en utilisant la fonction personnalisée."""
        return self._sanitize_func(value)


class ValidationRegistry:
    """Registre des validateurs disponibles."""

    def __init__(self) -> None:
        self._validators: Dict[str, Validator] = {}
        self._field_validators: Dict[str, Dict[str, Validator]] = {}

    def register_validator(self, name: str, validator: Validator) -> None:
        """Enregistre un validateur nommé."""
        self._validators[name] = validator

    def register_field_validator(self, field_name: str, validator: Validator) -> None:
        """Enregistre un validateur pour un champ spécifique."""
        if field_name not in self._field_validators:
            self._field_validators[field_name] = {}
        self._field_validators[field_name][type(validator).__name__] = validator

    def get_validator(self, name: str) -> Optional[Validator]:
        """Récupère un validateur par son nom."""
        return self._validators.get(name)

    def get_field_validators(self, field_name: str) -> List[Validator]:
        """Récupère tous les validateurs pour un champ."""
        return list(self._field_validators.get(field_name, {}).values())

    def validate_field(self, field_name: str, value: Any) -> ValidationResult:
        """Valide un champ avec tous ses validateurs enregistrés."""
        result = ValidationResult(is_valid=True)
        validators = self.get_field_validators(field_name)

        for validator in validators:
            validation_result = validator.validate(value, field_name)
            result.merge(validation_result)

        return result


class ValidationEngine:
    """Moteur de validation principal avec configuration dynamique."""

    def __init__(self, config: Optional[ValidationConfig] = None):
        self._config = config or get_config().validation
        self._registry = ValidationRegistry()
        self._initialize_default_validators()

    def _initialize_default_validators(self) -> None:
        """Initialise les validateurs par défaut depuis la configuration."""
        # Validateur d'email
        email_validator = EmailValidator(
            regex=self._config.email_regex, check_deliverability=self._config.email_check_deliverability
        )
        self._registry.register_validator("email", email_validator)
        self._registry.register_field_validator("email", email_validator)

        # Validateur de mot de passe
        password_validator = PasswordValidator(
            min_length=self._config.password_min_length,
            require_uppercase=self._config.password_require_uppercase,
            require_lowercase=self._config.password_require_lowercase,
            require_numbers=self._config.password_require_numbers,
            require_special_chars=self._config.password_require_special_chars,
        )
        self._registry.register_validator("password", password_validator)
        self._registry.register_field_validator("password", password_validator)

        # Validateur de chaîne par défaut
        string_validator = StringValidator()
        self._registry.register_validator("string", string_validator)

        # Validateur numérique par défaut
        numeric_validator = NumericValidator()
        self._registry.register_validator("numeric", numeric_validator)

    def register_custom_validator(self, name: str, validator: Validator) -> None:
        """Enregistre un validateur personnalisé."""
        self._registry.register_validator(name, validator)

    def register_field_validator(self, field_name: str, validator: Validator) -> None:
        """Enregistre un validateur pour un champ spécifique."""
        self._registry.register_field_validator(field_name, validator)

    def validate(self, field_name: str, value: Any, validator_name: Optional[str] = None) -> ValidationResult:
        """Valide une valeur avec un validateur spécifique ou les validateurs de champ."""
        if validator_name:
            validator = self._registry.get_validator(validator_name)
            if validator:
                return validator.validate(value, field_name)
            else:
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(field_name, f"Validator '{validator_name}' not found", value)],
                )
        else:
            return self._registry.validate_field(field_name, value)

    def sanitize(self, field_name: str, value: Any, validator_name: Optional[str] = None) -> Any:
        """Nettoie une valeur avec un validateur spécifique."""
        if validator_name:
            validator = self._registry.get_validator(validator_name)
            if validator:
                return validator.sanitize(value)
        else:
            validators = self._registry.get_field_validators(field_name)
            if validators:
                return validators[0].sanitize(value)  # Utilise le premier validateur
        return value

    def validate_dict(self, data: Dict[str, Any]) -> ValidationResult:
        """Valide un dictionnaire complet avec les validateurs de champ enregistrés."""
        result = ValidationResult(is_valid=True)

        for field_name, value in data.items():
            field_result = self.validate(field_name, value)
            result.merge(field_result)

        return result

    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Nettoie un dictionnaire complet avec les validateurs de champ enregistrés."""
        sanitized = {}

        for field_name, value in data.items():
            sanitized[field_name] = self.sanitize(field_name, value)

        return sanitized


# Instance globale du moteur de validation
_global_validation_engine: Optional[ValidationEngine] = None


def get_validation_engine() -> ValidationEngine:
    """Retourne l'instance globale du moteur de validation."""
    global _global_validation_engine
    if _global_validation_engine is None:
        _global_validation_engine = ValidationEngine()
    return _global_validation_engine


def reset_validation_engine() -> None:
    """Réinitialise le moteur de validation (utile pour les tests)."""
    global _global_validation_engine
    _global_validation_engine = None
