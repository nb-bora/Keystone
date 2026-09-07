"""
Router OAuth 2.0 pour FastAPI.

Endpoints pour l'authentification via Google, GitHub et LinkedIn.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from aegis.drivers.oauth import (
    OAuthHandler,
    OAuthProviderConfig,
    create_github_provider,
    create_google_provider,
    create_linkedin_provider,
)
from fastapi import APIRouter, HTTPException, Query


# Schemas pour les requêtes/réponses OAuth
class OAuthLoginRequest(BaseModel):
    """Requête de connexion OAuth."""

    provider: str
    redirect_uri: str


class OAuthLoginResponse(BaseModel):
    """Réponse de connexion OAuth."""

    auth_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Requête de callback OAuth."""

    code: str
    state: str


class OAuthUserInfoResponse(BaseModel):
    """Réponse avec les informations utilisateur."""

    provider: str
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None


class OAuthTokenResponse(BaseModel):
    """Réponse avec le token d'accès."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None


# Router OAuth
oauth_router = APIRouter(prefix="/api/v1/auth/oauth", tags=["OAuth Authentication"])


# Singleton OAuth Handler (initialisé au démarrage)
_oauth_handler: Optional[OAuthHandler] = None

# Storage pour les states OAuth (en production, utiliser Redis ou cache distribué)
_oauth_states: Dict[str, Dict[str, Any]] = {}


def get_oauth_handler() -> OAuthHandler:
    """Récupère l'handler OAuth singleton."""
    global _oauth_handler
    if _oauth_handler is None:
        raise HTTPException(status_code=500, detail="OAuth handler non initialisé")
    return _oauth_handler


def init_oauth_handler() -> OAuthHandler:
    """Initialise l'handler OAuth avec les variables d'environnement."""
    global _oauth_handler

    # Fermer l'handler existant s'il y en a un
    if _oauth_handler is not None:
        import asyncio
        asyncio.create_task(_oauth_handler.close())

    providers: List[OAuthProviderConfig] = []

    # Google
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        providers.append(
            create_google_provider(
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                redirect_uri="",
            )
        )

    # GitHub
    if os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"):
        providers.append(
            create_github_provider(
                client_id=os.getenv("GITHUB_CLIENT_ID"),
                client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
                redirect_uri="",
            )
        )

    # LinkedIn
    if os.getenv("LINKEDIN_CLIENT_ID") and os.getenv("LINKEDIN_CLIENT_SECRET"):
        providers.append(
            create_linkedin_provider(
                client_id=os.getenv("LINKEDIN_CLIENT_ID"),
                client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
                redirect_uri="",
            )
        )

    if not providers:
        raise ValueError("Aucun provider OAuth configuré dans les variables d'environnement")

    _oauth_handler = OAuthHandler(providers)
    return _oauth_handler


def cleanup_oauth_handler():
    """Nettoie l'handler OAuth à l'arrêt de l'application."""
    global _oauth_handler
    if _oauth_handler is not None:
        import asyncio
        asyncio.create_task(_oauth_handler.close())
        _oauth_handler = None


@oauth_router.get(
    "/providers",
    response_model=List[Dict[str, str]],
    summary="List Available OAuth Providers",
    description="Returns a list of all configured OAuth 2.0 providers (Google, GitHub, LinkedIn).",
    responses={
        200: {
            "description": "List of available OAuth providers",
            "content": {
                "application/json": {
                    "example": [
                        {"name": "google", "display_name": "Google"},
                        {"name": "github", "display_name": "GitHub"},
                        {"name": "linkedin", "display_name": "LinkedIn"},
                    ]
                }
            },
        }
    },
)
async def list_providers() -> List[Dict[str, str]]:
    """Liste les providers OAuth disponibles."""
    if _oauth_handler is None:
        return []

    return [
        {"name": name, "display_name": provider.display_name} for name, provider in _oauth_handler._providers.items()
    ]


@oauth_router.post(
    "/login",
    response_model=OAuthLoginResponse,
    summary="Get OAuth Authorization URL",
    description="Generates the OAuth 2.0 authorization URL for the specified provider. The user should be redirected to this URL to authenticate with the provider (Google, GitHub, LinkedIn).",
    responses={
        200: {
            "description": "Authorization URL generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&response_type=code&scope=openid%20email%20profile&state=...",
                        "state": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        400: {
            "description": "Invalid provider or missing parameters",
            "content": {"application/json": {"example": {"detail": "Provider 'invalid' non configuré"}}},
        },
    },
)
async def oauth_login(request: OAuthLoginRequest) -> OAuthLoginResponse:
    """Génère l'URL d'autorisation OAuth pour le provider spécifié."""
    handler = get_oauth_handler()

    # Valider le provider
    if request.provider not in handler._providers:
        raise HTTPException(status_code=400, detail=f"Provider '{request.provider}' non configuré")

    # Générer un state pour la sécurité CSRF
    state = str(uuid.uuid4())

    # Stocker le state avec le redirect_uri et l'expiration (10 minutes)
    _oauth_states[state] = {
        "redirect_uri": request.redirect_uri,
        "provider": request.provider,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
    }

    auth_url = handler.get_authorization_url(
        provider_name=request.provider, redirect_uri=request.redirect_uri, state=state
    )

    return OAuthLoginResponse(auth_url=auth_url, state=state)


@oauth_router.get(
    "/callback/{provider}",
    summary="OAuth 2.0 Callback Endpoint",
    description="Handles the OAuth 2.0 callback from the provider after user authentication. Exchanges the authorization code for an access token and retrieves user information.",
    responses={
        200: {
            "description": "Authentication successful, user information retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "provider": "google",
                        "user": {
                            "provider": "google",
                            "user_id": "123456789",
                            "email": "user@example.com",
                            "name": "John Doe",
                            "picture": "https://example.com/photo.jpg",
                            "given_name": "John",
                            "family_name": "Doe",
                        },
                        "access_token": "ya29.a0AfH6SMB...",
                        "token_type": "bearer",
                        "expires_in": 3600,
                    }
                }
            },
        },
        400: {
            "description": "Invalid OAuth code or provider error",
            "content": {"application/json": {"example": {"detail": "Erreur OAuth: ..."}}},
        },
        500: {
            "description": "Server error during OAuth processing",
            "content": {"application/json": {"example": {"detail": "Erreur OAuth: ..."}}},
        },
    },
)
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Code d'autorisation OAuth"),
    state: str = Query(..., description="State OAuth"),
) -> Dict[str, Any]:
    """Callback OAuth pour traiter la réponse du provider."""
    handler = get_oauth_handler()

    # Valider le state CSRF
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="State OAuth invalide ou expiré")

    state_data = _oauth_states[state]

    # Vérifier l'expiration du state
    if datetime.now(timezone.utc) > state_data["expires_at"]:
        del _oauth_states[state]
        raise HTTPException(status_code=400, detail="State OAuth expiré")

    # Vérifier que le provider correspond
    if state_data["provider"] != provider:
        del _oauth_states[state]
        raise HTTPException(status_code=400, detail="Provider mismatch")

    # Récupérer le redirect_uri stocké
    redirect_uri = state_data["redirect_uri"]

    # Supprimer le state après utilisation (one-time use)
    del _oauth_states[state]

    try:
        # Échanger le code contre un token d'accès
        token_data = await handler.exchange_code_for_token(
            provider_name=provider, code=code, redirect_uri=redirect_uri
        )

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Token d'accès non reçu")

        # Récupérer les informations utilisateur
        user_info = await handler.get_user_info(provider_name=provider, access_token=access_token)

        # Normaliser les données utilisateur selon le provider
        normalized_user = normalize_user_info(provider, user_info)

        # Créer ou mettre à jour l'utilisateur dans Aegis IAM
        # Pour l'instant, retourner les informations normalisées
        # TODO: Intégrer avec le repository Aegis pour créer l'utilisateur
        # TODO: Générer un JWT token ou session Aegis

        return {
            "status": "success",
            "provider": provider,
            "user": normalized_user,
            "access_token": access_token,
            "token_type": token_data.get("token_type", "bearer"),
            "expires_in": token_data.get("expires_in"),
        }

    except HTTPException:
        # Re-raise HTTPException pour les erreurs client
        raise
    except Exception as e:
        # Capture les erreurs inattendues comme erreurs serveur
        raise HTTPException(status_code=500, detail=f"Erreur OAuth: {str(e)}") from e


def normalize_user_info(provider: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise les informations utilisateur selon le provider."""
    if provider == "google":
        return {
            "provider": "google",
            "user_id": user_info.get("sub"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "given_name": user_info.get("given_name"),
            "family_name": user_info.get("family_name"),
        }
    elif provider == "github":
        return {
            "provider": "github",
            "user_id": str(user_info.get("id")),
            "email": user_info.get("email"),
            "name": user_info.get("name") or user_info.get("login"),
            "picture": user_info.get("avatar_url"),
            "login": user_info.get("login"),
        }
    elif provider == "linkedin":
        return {
            "provider": "linkedin",
            "user_id": user_info.get("id"),
            "email": user_info.get("email"),
            "name": f"{user_info.get('localizedFirstName', '')} {user_info.get('localizedLastName', '')}",
            "picture": None,
        }
    else:
        return user_info
