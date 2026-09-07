"""
OAuth 2.0 Driver pour Aegis IAM.

Supporte l'authentification via Google, GitHub et LinkedIn.
"""

from aegis.drivers.oauth.oauth_handler import (
    OAuthHandler,
    OAuthProviderConfig,
    create_github_provider,
    create_google_provider,
    create_linkedin_provider,
)

__all__ = [
    "OAuthHandler",
    "OAuthProviderConfig",
    "create_google_provider",
    "create_github_provider",
    "create_linkedin_provider",
]
