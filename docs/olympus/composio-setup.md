# Composio BYOK OAuth Integration — Setup Guide

> **Purpose:** Comprehensive reference for integrating Gmail, GitHub, and Slack OAuth connections into Olympus UI via Composio, where each user brings their own Composio account (BYOK).
> **Compiled:** 2026-05-27
> **Source:** [docs.composio.dev](https://docs.composio.dev), [GitHub: ComposioHQ/composio](https://github.com/ComposioHQ/composio)

---

## 1. Composio Account Creation & API Keys

### Human User Signup

1. Go to **[composio.dev](https://composio.dev)** and click **"Get Started"** (→ `https://dashboard.composio.dev/login`)
2. Create a free account (email/password or Google/GitHub OAuth)
3. After signup, go to **[Settings](https://dashboard.composio.dev/settings)** to get your API key
4. The API key format: `ak_xxxxxxxxxxxx` (prefixed with `ak_`)

### Agent/Programmatic Signup

Composio supports agent-native signup without human intervention:

```bash
curl -sS -X POST 'https://agents.composio.dev/api/signup' \
  -H 'content-type: application/json' \
  -d '{}' \
  -o ~/.composio/anonymous_user_data.json
```

The response includes:
```json
{
  "status": "ready",
  "slug": "amber-cedar-otter",
  "email": "amber-cedar-otter@agent.composio.ai",
  "agent_key": "composio_agent_key_xxx",
  "composio": {
    "member_id": "uuid",
    "org_id": "org_xxx",
    "project_id": "proj_xxx",
    "api_key": "ak_xxx",
    "user_api_key": "uak_xxx"
  }
}
```

> **For Olympus UI:** Users will sign up on composio.dev and paste their API key into Olympus. Each user runs their own Composio account — BYOK model.

### Key References

| Resource | URL |
|----------|-----|
| **Dashboard** | `https://dashboard.composio.dev` |
| **API Key (Settings)** | `https://dashboard.composio.dev/settings` |
| **Auth Configs** | `https://dashboard.composio.dev/~/project/auth-configs` |
| **Project Settings (Auth Screen branding)** | `https://dashboard.composio.dev/~/project/settings/auth-screen` |
| **Agent Signup** | `https://agents.composio.dev` |
| **Docs Home** | `https://docs.composio.dev` |
| **GitHub Repo** | `https://github.com/ComposioHQ/composio` |

---

## 2. OAuth Flow Architecture

### How Composio Handles Auth

Composio provides **Connect Links** — hosted pages at `connect.composio.dev/link/ln_*` where users authenticate with their services. The overall flow:

```
Olympus UI  →  session.authorize("gmail")  →  Connect Link URL
                                               │
User clicks link  →  OAuth provider (Google/GitHub/Slack)
                                               │
Provider redirects  →  backend.composio.dev/api/v3.1/toolkits/auth/callback
                                               │
Composio stores token  →  redirects to callbackUrl (Olympus UI)
```

### Three Authentication Approaches

| Approach | When to Use | Key Method |
|----------|-------------|------------|
| **In-chat auth** | Agent prompts user during conversation | Default session behavior (`manage_connections=True`) |
| **Manual auth** | Pre-authenticate before chat, custom UI | `session.authorize("gmail")` |
| **Custom auth configs** | BYOK OAuth credentials, white-labeling, custom scopes | Create auth config in dashboard, pass `auth_configs` to session |

> **For Olympus UI BYOK:** We use **Manual auth** with **Custom auth configs** (BYOK OAuth credentials). Each user creates auth configs with their own OAuth apps in their Composio dashboard.

---

## 3. OAuth Callback URL & Redirect Pattern

### Composio's Primary Redirect URI

When registering an OAuth app with Google, GitHub, or Slack, set the redirect URI to:

```
https://backend.composio.dev/api/v3.1/toolkits/auth/callback
```

This is where the OAuth provider sends the authorization code. Composio captures it and exchanges it for tokens.

### Custom Redirect URI (White-Labeling)

To hide `backend.composio.dev` from the browser address bar, proxy through your own domain:

```
https://yourdomain.com/api/composio-redirect
```

Your endpoint must **302 redirect** the browser to `https://backend.composio.dev/api/v3.1/toolkits/auth/callback` with the same query parameters. Do NOT fetch server-side — the browser must be redirected.

Example (FastAPI):
```python
@app.get("/api/composio-redirect")
def composio_redirect(request: Request):
    return RedirectResponse(
        url=f"https://backend.composio.dev/api/v3.1/toolkits/auth/callback?{request.url.query}"
    )
```

### Post-Auth Callback URL (Where Users Land)

Pass a `callbackUrl` to control where users go AFTER OAuth completes:

```python
connection_request = session.authorize(
    "gmail",
    callback_url="https://olympus.local/settings/integrations"
)
```

Composio appends these query parameters:
- `status` → `success` or `failed`
- `connected_account_id` → e.g. `ca_abc123`

Result URL:
```
https://olympus.local/settings/integrations?status=success&connected_account_id=ca_abc123
```

> **Note on `localhost:53824`:** This port does NOT appear in Composio's documentation. It may refer to the Olympus dev server port or a local callback endpoint. Composio's built-in redirect uses `backend.composio.dev`. Olympus should use its own domain (or `localhost:5173` in dev) as the `callbackUrl`.

---

## 4. Client ID Requirements (Custom OAuth Apps)

### Why Create Custom OAuth Apps?

- **White-labeling:** Users see your app name, not "Composio wants to access..."
- **Custom scopes:** Request permissions beyond Composio defaults
- **Dedicated rate limits:** Your own quota vs. shared Composio quota
- **Faster polling triggers:** Custom apps can use shorter polling intervals

### Process Overview

1. Create a custom auth config in Composio dashboard
2. Register an OAuth app with the provider (Google, GitHub, Slack)
3. Copy Client ID + Client Secret back into Composio
4. Pass the auth config ID when creating sessions

### Per-Service OAuth App Registration

#### Gmail / Google
- **Console:** `https://console.cloud.google.com/apis/credentials`
- **Auth type:** OAuth 2.0 Web Application
- **Required scopes:** `https://www.googleapis.com/auth/gmail.modify` (read/write/delete), `https://www.googleapis.com/auth/gmail.compose` (send), `https://www.googleapis.com/auth/gmail.labels` (label management)
- **Redirect URI:** `https://backend.composio.dev/api/v3.1/toolkits/auth/callback`
- **Setup guide:** `https://composio.dev/auth/googleapps`

#### GitHub
- **Console:** `https://github.com/settings/developers` → OAuth Apps → New OAuth App
- **Auth type:** OAuth 2.0
- **Required scopes:** `repo`, `user`, `read:org`, `admin:org` (depending on needs)
- **Redirect URI:** `https://backend.composio.dev/api/v3.1/toolkits/auth/callback`
- **Setup guide:** `https://composio.dev/auth/github`

#### Slack
- **Console:** `https://api.slack.com/apps` → Create New App → From scratch
- **Auth type:** OAuth 2.0 with Bot Token + User Token
- **Required scopes:** `channels:read`, `chat:write`, `users:read`, `reactions:read` (depending on needs)
- **Redirect URI:** `https://backend.composio.dev/api/v3.1/toolkits/auth/callback`
- **Setup guide:** `https://composio.dev/auth/slack`

### Creating Auth Configs in Composio Dashboard

1. Go to `https://dashboard.composio.dev/~/project/auth-configs`
2. Click **Create Auth Config**
3. Select toolkit (Gmail, GitHub, or Slack)
4. Choose OAuth2 scheme
5. Toggle **"Use your own developer credentials"**
6. Enter Client ID and Client Secret
7. Click **Create** → copy the auth config ID (e.g. `ac_xxxxx`)

---

## 5. Olympus UI Integration Code Pattern

### Python SDK (for Olympus Backend)

```python
from composio import Composio

# Each user provides their own API key
composio = Composio(api_key=user_api_key)

# Create a session with specific toolkits and custom auth configs
session = composio.create(
    user_id="user_123",
    toolkits=["gmail", "github", "slack"],
    auth_configs={
        "gmail": "ac_user_gmail_config",
        "github": "ac_user_github_config",
        "slack": "ac_user_slack_config",
    },
    manage_connections=False,  # Handle auth in Olympus UI, not in-chat
)

# Check which toolkits are connected
toolkits = session.toolkits()
connected = {t.slug for t in toolkits.items if t.connection.is_active}

# Generate Connect Link for unconnected toolkits
for slug in ["gmail", "github", "slack"]:
    if slug not in connected:
        connection_request = session.authorize(
            slug,
            callback_url=f"https://olympus.local/settings/integrations?toolkit={slug}"
        )
        print(f"Connect {slug}: {connection_request.redirect_url}")
        # Redirect URL format: https://connect.composio.dev/link/ln_abc123
        connection_request.wait_for_connection()
```

### TypeScript SDK (for Olympus Frontend direct use — not recommended for BYOK)

```typescript
import { Composio } from '@composio/core';

const composio = new Composio({ apiKey: userApiKey });
const session = await composio.create("user_123", {
  toolkits: ["gmail", "github", "slack"],
  authConfigs: {
    gmail: "ac_user_gmail_config",
    github: "ac_user_github_config",
    slack: "ac_user_slack_config",
  },
  manageConnections: false,
});

const connectionRequest = await session.authorize("gmail", {
  callbackUrl: "https://olympus.local/settings/integrations?toolkit=gmail",
});

console.log(connectionRequest.redirectUrl);
// → https://connect.composio.dev/link/ln_abc123

const connectedAccount = await connectionRequest.waitForConnection(60000);
```

### Required Environment

```bash title=".env"
COMPOSIO_API_KEY=ak_xxxxxxxxxxxx  # User's own API key
```

Install:
```bash
pip install composio composio-openai-agents python-dotenv
# or
npm install @composio/core @composio/openai-agents dotenv
```

---

## 6. Composio Managed Auth (No-Own-App Alternative)

### Using Composio's Default OAuth Apps

If users don't want to create their own OAuth apps, Composio provides **managed OAuth** for Gmail, GitHub, Slack, and many other services. This works out of the box — no OAuth app registration needed.

```python
# Just create a session — no custom auth config needed
session = composio.create(user_id="user_123")

# When a tool needs auth, Composio handles it with managed credentials
connection_request = session.authorize("gmail")
# User clicks link → authenticates → done
```

**Tradeoffs:**
- Pro: Zero setup, works immediately
- Con: Users see "Composio wants to access your account" on consent screens
- Con: Shared rate limits across all Composio users
- Con: Cannot customize OAuth scopes

### Managed Auth vs Custom Auth — Decision Matrix

| Factor | Use Managed Auth | Use Custom Auth |
|--------|:-----------------:|:----------------:|
| Getting started fast | ✅ | ❌ |
| Production OAuth branding | ❌ | ✅ |
| Custom OAuth scopes | ❌ | ✅ |
| Dedicated rate limits | ❌ | ✅ |
| Faster trigger polling (<15 min) | ❌ | ✅ |
| Zero maintenance | ✅ | ❌ |

---

## 7. Olympus UI BYOK User Flow Design

### What Each User Does

```
1. User visits composio.dev → creates free account → gets API key
2. User creates OAuth apps for Gmail, GitHub, Slack in their respective dev consoles
3. User enters credentials into Composio dashboard (creates auth configs)
4. User pastes Composio API key + auth config IDs into Olympus UI Settings → Integrations
5. Olympus UI calls session.authorize() for each toolkit → shows Connect Links
6. User clicks links → authenticates with each service → lands back on Olympus
7. Olympus UI verifies connected_account_id → marks toolkit as "Connected ✓"
```

### Olympus UI Integration Tab State

```
╔══════════════════════════════════════╗
║  Integrations                        ║
╟──────────────────────────────────────╢
║  Composio API Key: [ak_****] [Save]  ║
║                                      ║
║  Gmail    ○ Not connected  [Connect] ║
║  GitHub   ● Connected ✓    [Reconnect] ║
║  Slack    ○ Not connected  [Connect] ║
║                                      ║
║  Auth Configs (Custom OAuth)          ║
║  Gmail:    [ac_gmail_xxxx]           ║
║  GitHub:   [ac_github_xxxx]          ║
║  Slack:    [ac_slack_xxxx]           ║
║                          [Save IDs]  ║
╚══════════════════════════════════════╝
```

---

## 8. Documentation Links Reference

### Core Composio Docs

| Document | URL |
|----------|-----|
| **Quickstart** | `https://docs.composio.dev/docs/quickstart` |
| **Authentication Overview** | `https://docs.composio.dev/docs/authentication` |
| **Managed vs Custom Auth** | `https://docs.composio.dev/docs/custom-app-vs-managed-app` |
| **Custom Auth Configs** | `https://docs.composio.dev/docs/auth-configuration/custom-auth-configs` |
| **Manual Authentication** | `https://docs.composio.dev/docs/authenticating-users/manually-authenticating` |
| **In-Chat Authentication** | `https://docs.composio.dev/docs/authenticating-users/in-chat-authentication` |
| **Configuring Sessions** | `https://docs.composio.dev/docs/configuring-sessions` |
| **White-Labeling Auth** | `https://docs.composio.dev/docs/white-labeling-authentication` |
| **Agent Signup** | `https://docs.composio.dev/docs/signing-up-as-an-agent` |
| **API Reference** | `https://docs.composio.dev/reference` |

### Toolkit-Specific OAuth Guides

| Service | Setup Guide URL |
|---------|----------------|
| **Gmail / Google** | `https://composio.dev/auth/googleapps` |
| **GitHub** | `https://composio.dev/auth/github` |
| **Slack** | `https://composio.dev/auth/slack` |
| **All Toolkits** | `https://composio.dev/auth` |

### Managed Auth Toolkit List

| URL |
|-----|
| `https://docs.composio.dev/toolkits/managed-auth` |

---

## 9. SDK & API Quick Reference

### Python SDK
```bash
pip install composio
```

```python
from composio import Composio

composio = Composio(api_key="ak_xxx")
session = composio.create(user_id="user_123", toolkits=["gmail", "github", "slack"])

# Auth
conn = session.authorize("gmail", callback_url="https://my.app/callback")
conn.wait_for_connection()

# Tools
tools = session.tools()
toolkits = session.toolkits()

# MCP URL
mcp_url = session.mcp.url
```

### TypeScript SDK
```bash
npm install @composio/core
```

```typescript
import { Composio } from '@composio/core';

const composio = new Composio({ apiKey: "ak_xxx" });
const session = await composio.create("user_123", {
  toolkits: ["gmail", "github", "slack"],
});

const conn = await session.authorize("gmail", {
  callbackUrl: "https://my.app/callback",
});
await conn.waitForConnection(60000);
```

### Key ID Prefixes

| Prefix | Meaning |
|--------|---------|
| `ak_` | Composio API Key |
| `uak_` | User API Key (for CLI login) |
| `ac_` | Auth Config ID |
| `ca_` | Connected Account ID |
| `ln_` | Connect Link ID |
| `proj_` | Project ID |
| `org_` | Organization ID |

---

## 10. Key Design Decisions for Olympus

### D1: BYOK Model per User
Each Olympus user creates their own free Composio account. The Olympus backend stores each user's `COMPOSIO_API_KEY` and auth config IDs. No shared credentials between users.

### D2: Manual Auth Flow
Olympus uses `session.authorize()` (manual auth), not in-chat auth. The Integrations tab is the dedicated connection UI. Set `manage_connections=False` to disable in-chat prompts.

### D3: Custom Auth Configs (Optional)
Users can use Composio managed auth initially (zero OAuth setup), then graduate to custom auth configs when they want white-labeling or custom scopes. Olympus should support both.

### D4: Callback URL Strategy
Use the Olympus UI URL as the `callbackUrl` for post-auth landing. In development: `http://localhost:5173/settings/integrations`. In production: the deployment's real URL. The OAuth redirect URI for provider apps is always `https://backend.composio.dev/api/v3.1/toolkits/auth/callback` (or your proxy).

### D5: API Key Storage
Store per-user Composio API keys in the Olympus backend (not in browser localStorage). The frontend talks to the Olympus backend, which in turn calls Composio.

---

## 11. Build Task Mapping

| Olympus Build Task | Composio Setup Prerequisite |
|--------------------|-----------------------------|
| T14: Composio OAuth components | This document (composio-setup.md) |
| T14b: Wire integrations into Settings tab | User has API key + auth config IDs |
| T15: Onboarding integration wizard | Auto-detect unconnected toolkits |
| Stream B (T8-T13): Integration backend | Composio SDK installed on Olympus backend |

---

## Appendix: Full OAuth Flow Sequence

```
┌──────────┐     ┌───────────┐     ┌──────────────┐     ┌──────────┐
│ Olympus  │     │ Composio  │     │ OAuth Provider│    │  User    │
│ Backend  │     │ Backend   │     │ (Google/GH)  │     │ Browser  │
└────┬─────┘     └─────┬─────┘     └──────┬───────┘     └────┬─────┘
     │                  │                  │                  │
     │ session.authorize("gmail", callback_url)              │
     │─────────────────►│                  │                  │
     │                  │                  │                  │
     │ returns redirect_url (connect.composio.dev/link/ln_x) │
     │◄─────────────────│                  │                  │
     │                  │                  │                  │
     │ Show Connect Link to user           │                  │
     │─────────────────────────────────────────────────────►│
     │                  │                  │                  │
     │                  │   User clicks link → redirects to   │
     │                  │   OAuth provider with scopes        │
     │                  │                  │◄─────────────────│
     │                  │                  │                  │
     │                  │   User approves │                  │
     │                  │   OAuth consent  │                  │
     │                  │                  │─────────────────►│
     │                  │                  │                  │
     │                  │  Auth code → backend.composio.dev   │
     │                  │◄─────────────────│                  │
     │                  │                  │                  │
     │                  │  Exchange code for tokens            │
     │                  │  Store in connected account          │
     │                  │                  │                  │
     │                  │  Redirect to callback_url            │
     │                  │  + ?status=success                  │
     │                  │  + &connected_account_id=ca_xxx     │
     │                  │────────────────────────────────────►│
     │                  │                  │                  │
     │  Olympus reads status + connected_account_id           │
     │◄─────────────────────────────────────────────────────│
     │                  │                  │                  │
     │  Mark toolkit as "Connected ✓"                         │
     │                  │                  │                  │
```
