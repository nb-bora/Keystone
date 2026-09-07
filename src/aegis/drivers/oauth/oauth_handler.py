"""
Module OAuth 2.0 pour Aegis IAM.

Supporte l'authentification via Google, GitHub et LinkedIn avec OAuth 2.0.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx


@dataclass(frozen=True, slots=True)
class OAuthProviderConfig:
    """Configuration d'un provider OAuth."""

    name: str
    display_name: str
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    userinfo_url: str
    scopes: List[str]


class OAuthHandler:
    """Handler pour l'authentification OAuth 2.0."""

    def __init__(self, providers: List[OAuthProviderConfig]) -> None:
        self._providers = {p.name: p for p in providers}
        self._http_client = httpx.AsyncClient(timeout=30.0)

    def get_authorization_url(self, provider_name: str, redirect_uri: str, state: Optional[str] = None) -> str:
        """Génère l'URL d'autorisation OAuth."""
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' non configuré")

        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(provider.scopes),
        }

        if state:
            params["state"] = state

        return f"{provider.authorization_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, provider_name: str, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Échange un code d'autorisation contre un token d'accès."""
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' non configuré")

        data = {
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        response = await self._http_client.post(provider.token_url, data=data)
        response.raise_for_status()

        return response.json()

    async def get_user_info(self, provider_name: str, access_token: str) -> Dict[str, Any]:
        """Récupère les informations utilisateur depuis le provider."""
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' non configuré")

        headers = {}

        # GitHub, Google et LinkedIn utilisent Authorization header
        if provider_name in ("github", "google", "linkedin"):
            auth_header = f"Bearer {access_token}"
            headers["Authorization"] = auth_header

        response = await self._http_client.get(provider.userinfo_url, headers=headers)
        response.raise_for_status()

        return response.json()

    async def close(self) -> None:
        """Ferme le client HTTP."""
        await self._http_client.aclose()


# Configurations par défaut pour les providers courants
def create_google_provider(client_id: str, client_secret: str) -> OAuthProviderConfig:
    """Crée une configuration Google OAuth."""
    return OAuthProviderConfig(
        name="google",
        display_name="Google",
        client_id=client_id,
        client_secret=client_secret,
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",  # noqa: S106
        userinfo_url="https://www.googleapis.com/oauth2/v3/userinfo",
        scopes=["openid", "email", "profile"],
    )


def create_github_provider(client_id: str, client_secret: str) -> OAuthProviderConfig:
    """Crée une configuration GitHub OAuth."""
    return OAuthProviderConfig(
        name="github",
        display_name="GitHub",
        client_id=client_id,
        client_secret=client_secret,
        authorization_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",  # noqa: S106
        userinfo_url="https://api.github.com/user",
        scopes=["user:email", "read:user"],
    )


def create_linkedin_provider(client_id: str, client_secret: str) -> OAuthProviderConfig:
    """Crée une configuration LinkedIn OAuth."""
    return OAuthProviderConfig(
        name="linkedin",
        display_name="LinkedIn",
        client_id=client_id,
        client_secret=client_secret,
        authorization_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",  # noqa: S106
        userinfo_url="https://api.linkedin.com/v2/people/~",
        scopes=["r_liteprofile", "r_emailaddress"],
    )
