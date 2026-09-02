"""
Dépendances FastAPI & Injection de Dépendances pour Aegis.

Gère l'initialisation du container AegisContainer en singleton et fournit
le client AegisClient aux endpoints REST.
"""

from aegis.sdk.client import AegisClient, AegisContainer

# Singleton de production / mémoire
_global_container = AegisContainer()
_global_client = AegisClient(_global_container)


def get_aegis_container() -> AegisContainer:
    """Retourne l'instance globale d'AegisContainer."""
    return _global_container


def get_aegis_client() -> AegisClient:
    """Fournit une instance d'AegisClient aux routers FastAPI."""
    return _global_client


def reset_global_container() -> None:
    """Re-initialise le container (utile pour la suite de tests)."""
    global _global_container, _global_client
    _global_container = AegisContainer()
    _global_client = AegisClient(_global_container)
