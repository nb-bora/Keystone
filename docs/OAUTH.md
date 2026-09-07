# OAuth 2.0 Authentication Guide

## 📋 Overview

Aegis IAM supports OAuth 2.0 authentication for seamless social login with popular providers:
- **Google**: Sign in with Google account
- **GitHub**: Sign in with GitHub account
- **LinkedIn**: Sign in with LinkedIn account

This guide walks you through setting up OAuth 2.0 authentication for your Aegis IAM application.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 User (Browser)                          │
└─────────────────────────────────────────────────────────┘
                     │
                     │ 1. Click "Sign in with Google"
                     │
┌─────────────────────────────────────────────────────────┐
│         Aegis IAM FastAPI Application                  │
│  /api/v1/auth/oauth/login                               │
│  → Returns authorization URL                            │
└─────────────────────────────────────────────────────────┘
                     │
                     │ 2. Redirect to Google
                     │
┌─────────────────────────────────────────────────────────┐
│              Google OAuth 2.0                           │
│  User authenticates with Google account                 │
└─────────────────────────────────────────────────────────┘
                     │
                     │ 3. Redirect with authorization code
                     │
┌─────────────────────────────────────────────────────────┐
│         Aegis IAM FastAPI Application                  │
│  /api/v1/auth/oauth/callback/google                     │
│  → Exchange code for access token                       │
│  → Retrieve user information                            │
│  → Create/update user in Aegis IAM                      │
└─────────────────────────────────────────────────────────┘
                     │
                     │ 4. Return user + access token
                     │
┌─────────────────────────────────────────────────────────┐
│              User (Logged In)                           │
└─────────────────────────────────────────────────────────┘
```

## 🔧 Setup Instructions

### Step 1: Create OAuth Applications

#### Google OAuth 2.0

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable "Google+ API" or "Google Identity"
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Application type: Web application
6. Authorized redirect URIs:
   - Development: `http://localhost:8000/api/v1/auth/oauth/callback/google`
   - Production: `https://yourdomain.com/api/v1/auth/oauth/callback/google`
7. Copy **Client ID** and **Client Secret**

#### GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the form:
   - Application name: `Aegis IAM`
   - Homepage URL: `http://localhost:8000` (or your production URL)
   - Authorization callback URL: `http://localhost:8000/api/v1/auth/oauth/callback/github`
4. Copy **Client ID** and **Client Secret**

#### LinkedIn OAuth 2.0

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers)
2. Create a new application
3. Fill in the required information
4. Add redirect URLs:
   - Development: `http://localhost:8000/api/v1/auth/oauth/callback/linkedin`
   - Production: `https://yourdomain.com/api/v1/auth/oauth/callback/linkedin`
5. Copy **Client ID** and **Client Secret**

### Step 2: Configure Environment Variables

Add the following environment variables to your `.env` file or system:

```bash
# Google OAuth
GOOGLE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-google-client-secret"

# GitHub OAuth
GITHUB_CLIENT_ID="your-github-client-id"
GITHUB_CLIENT_SECRET="your-github-client-secret"

# LinkedIn OAuth
LINKEDIN_CLIENT_ID="your-linkedin-client-id"
LINKEDIN_CLIENT_SECRET="your-linkedin-client-secret"
```

### Step 3: Install Dependencies

```bash
pip install -e ".[fastapi]"
```

This installs:
- `fastapi>=0.104.0`
- `uvicorn>=0.24.0`
- `httpx>=0.25.0` (for OAuth HTTP requests)

### Step 4: Start the FastAPI Application

```bash
uvicorn aegis.drivers.fastapi.app:app --reload --host 0.0.0.0 --port 8000
```

## 📚 API Endpoints

### 1. List Available OAuth Providers

**Endpoint:** `GET /api/v1/auth/oauth/providers`

**Description:** Returns a list of all configured OAuth 2.0 providers.

**Response:**
```json
[
  {
    "name": "google",
    "display_name": "Google"
  },
  {
    "name": "github",
    "display_name": "GitHub"
  },
  {
    "name": "linkedin",
    "display_name": "LinkedIn"
  }
]
```

### 2. Get OAuth Authorization URL

**Endpoint:** `POST /api/v1/auth/oauth/login`

**Description:** Generates the OAuth 2.0 authorization URL for the specified provider.

**Request Body:**
```json
{
  "provider": "google",
  "redirect_uri": "http://localhost:8000/api/v1/auth/oauth/callback/google"
}
```

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&response_type=code&scope=openid%20email%20profile&state=...",
  "state": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters:**
- `provider` (string, required): The OAuth provider name (`google`, `github`, `linkedin`)
- `redirect_uri` (string, required): The callback URL where the provider will redirect after authentication

### 3. OAuth Callback

**Endpoint:** `GET /api/v1/auth/oauth/callback/{provider}`

**Description:** Handles the OAuth 2.0 callback from the provider after user authentication.

**Query Parameters:**
- `code` (string, required): The authorization code from the provider
- `state` (string, required): The state parameter for CSRF protection
- `redirect_uri` (string, required): The redirect URI used in the initial request

**Response:**
```json
{
  "status": "success",
  "provider": "google",
  "user": {
    "provider": "google",
    "user_id": "123456789",
    "email": "user@example.com",
    "name": "John Doe",
    "picture": "https://example.com/photo.jpg",
    "given_name": "John",
    "family_name": "Doe"
  },
  "access_token": "ya29.a0AfH6SMB...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## 🔄 OAuth 2.0 Flow

### Step-by-Step Flow

1. **Frontend Initiates Login**
   ```javascript
   // Frontend (JavaScript/React/Vue/Angular)
   const response = await fetch('/api/v1/auth/oauth/login', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       provider: 'google',
       redirect_uri: 'http://localhost:8000/api/v1/auth/oauth/callback/google'
     })
   });
   const { auth_url } = await response.json();
   
   // Redirect user to OAuth provider
   window.location.href = auth_url;
   ```

2. **User Authenticates with Provider**
   - User is redirected to Google/GitHub/LinkedIn
   - User logs in with their credentials
   - User grants permissions to your application

3. **Provider Redirects Back**
   - Provider redirects to your callback URL with an authorization code
   - URL: `http://localhost:8000/api/v1/auth/oauth/callback/google?code=...&state=...`

4. **Backend Exchanges Code for Token**
   - Aegis IAM exchanges the authorization code for an access token
   - Retrieves user information from the provider
   - Creates or updates the user in the Aegis IAM system

5. **User is Logged In**
   - Backend returns user information and access token
   - Frontend stores the token and updates the UI

## 🔒 Security Considerations

### CSRF Protection

The OAuth flow uses a `state` parameter to protect against CSRF attacks:
- A random state is generated when initiating the login
- The state is validated in the callback
- Ensure the state matches between request and callback

### Secure Redirect URIs

- Always use HTTPS in production
- Whitelist authorized redirect URIs in your OAuth application settings
- Never accept arbitrary redirect URIs from user input

### Token Storage

- Store access tokens securely (HttpOnly cookies, secure storage)
- Implement token refresh mechanisms if using refresh tokens
- Revoke tokens on logout

### Rate Limiting

- Implement rate limiting on OAuth endpoints
- Monitor for suspicious activity
- Lock accounts after multiple failed attempts

## 🧪 Testing

### Local Testing

1. Set up OAuth applications with `http://localhost:8000` as the callback URL
2. Configure environment variables
3. Start the FastAPI application
4. Test the flow manually:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/oauth/login \
     -H "Content-Type: application/json" \
     -d '{"provider":"google","redirect_uri":"http://localhost:8000/api/v1/auth/oauth/callback/google"}'
   ```

### Production Testing

1. Update OAuth applications with production URLs
2. Use HTTPS for all endpoints
3. Test the complete flow end-to-end
4. Verify user creation and token generation

## 📝 User Information Mapping

### Google User Info

```json
{
  "sub": "123456789",
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://example.com/photo.jpg",
  "given_name": "John",
  "family_name": "Doe"
}
```

### GitHub User Info

```json
{
  "id": 12345678,
  "email": "user@example.com",
  "name": "John Doe",
  "login": "johndoe",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

### LinkedIn User Info

```json
{
  "id": "abc123",
  "email": "user@example.com",
  "localizedFirstName": "John",
  "localizedLastName": "Doe"
}
```

## 🚀 Integration Example

### React Frontend Example

```javascript
import React, { useState } from 'react';

function LoginButton() {
  const [isLoading, setIsLoading] = useState(false);

  const handleGoogleLogin = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/v1/auth/oauth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: 'google',
          redirect_uri: `${window.location.origin}/api/v1/auth/oauth/callback/google`
        })
      });
      const { auth_url } = await response.json();
      window.location.href = auth_url;
    } catch (error) {
      console.error('OAuth login failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button onClick={handleGoogleLogin} disabled={isLoading}>
      {isLoading ? 'Loading...' : 'Sign in with Google'}
    </button>
  );
}
```

## 🐛 Troubleshooting

### Common Issues

1. **"Provider not configured"**
   - Ensure environment variables are set
   - Restart the application after changing environment variables

2. **"Invalid redirect_uri"**
   - Check that the redirect URI matches exactly what's configured in the OAuth application
   - Include the full URL (scheme, host, path)

3. **"Code exchange failed"**
   - Ensure the authorization code is not expired
   - Check that the redirect URI matches the initial request

4. **"User info retrieval failed"**
   - Verify the access token is valid
   - Check that the userinfo URL is correct for the provider

## 📖 Additional Resources

- [OAuth 2.0 Specification](https://oauth.net/2/)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth Apps Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [LinkedIn OAuth 2.0 Documentation](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)

## 🎯 Next Steps

1. Implement user session management (JWT tokens, sessions)
2. Add user profile completion after OAuth login
3. Implement token refresh mechanisms
4. Add OAuth provider disconnection functionality
5. Implement social account linking (multiple providers per user)
