# toconline-mcp

[![CI](https://github.com/joaovitoriasilva/toconline-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/joaovitoriasilva/toconline-mcp/actions/workflows/ci.yml)
[![Security](https://github.com/joaovitoriasilva/toconline-mcp/actions/workflows/security.yml/badge.svg)](https://github.com/joaovitoriasilva/toconline-mcp/actions/workflows/security.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for the [TOC Online](https://www.toconline.pt) Portuguese accounting platform API. Exposes 74 typed tools covering the full TOC Online API surface — customers, suppliers, catalog, sales, purchases, and auxiliary data — so any MCP-compatible AI assistant can manage your accounting directly.

## Features

- **74 MCP tools** across 11 domain modules
- **Secure OAuth2 with PKCE** — browser-based login with tokens stored in the system keychain
- **Automatic token refresh** — rotated refresh tokens persisted to keychain automatically
- **Read-only mode** — block all write operations with a single env var
- **Selective module loading** — load only the tool groups you need
- **Fully typed** — Pydantic models drive schema generation for every tool
- **Async** — non-blocking HTTP via `httpx`

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (recommended)
- A TOC Online account with API credentials

## Installation

```bash
# Clone and install dependencies
git clone https://github.com/joaovitoriasilva/toconline-mcp.git
cd toconline-mcp
uv sync
```

## Authentication

### 1. Get your API credentials

In TOC Online, go to **Empresa > Configurações > Dados API** and note your:
- **Client ID** (`TOCONLINE_CLIENT_ID`)
- **Client Secret** (`TOCONLINE_CLIENT_SECRET`)
- **OAuth URL** (`TOCONLINE_OAUTH_TOKEN_URL`)
- **API URL** (`TOCONLINE_BASE_URL`)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in TOCONLINE_CLIENT_ID and TOCONLINE_CLIENT_SECRET
```

### 3. Authenticate (one-time)

```bash
uv run toconline-mcp auth
```

This opens your browser for TOC Online login. After you authorize, you'll be redirected to the callback URL — paste the full URL (or just the code) back into the terminal. The CLI exchanges it for tokens using PKCE (S256) and stores the refresh token securely in your **system keychain** (macOS Keychain / GNOME Keyring / Windows Credential Manager).

After this, the MCP server renews tokens automatically — no further manual steps needed.

### Check auth status

```bash
uv run toconline-mcp auth --status
```

### Log out (remove stored credentials)

```bash
uv run toconline-mcp auth --logout
```

### Alternative authentication methods

For environments where the system keychain isn't available (CI, Docker, headless servers):

| Method | How | Security |
|---|---|---|
| **Keychain** (default) | `uv run toconline-mcp auth` | Encrypted by OS |
| **Static token** | Set `TOCONLINE_ACCESS_TOKEN` in `.env` | Plain text on disk |
| **Refresh token in .env** | Set `TOCONLINE_REFRESH_TOKEN` in `.env` | Plain text on disk |

Token resolution priority at startup:
1. `TOCONLINE_ACCESS_TOKEN` (env) — static, for quick testing
2. System keychain — secure default
3. `TOCONLINE_REFRESH_TOKEN` (env) — CI/Docker fallback

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `TOCONLINE_CLIENT_ID` | Yes | `""` | OAuth2 client ID |
| `TOCONLINE_CLIENT_SECRET` | Yes | `""` | OAuth2 client secret |
| `TOCONLINE_BASE_URL` | No | `https://api10.toconline.pt` | TOC Online API base URL |
| `TOCONLINE_OAUTH_TOKEN_URL` | No | `https://app10.toconline.pt/oauth/token` | OAuth2 token endpoint |
| `TOCONLINE_ACCESS_TOKEN` | No | `""` | Static Bearer token (skips OAuth) |
| `TOCONLINE_REFRESH_TOKEN` | No | `""` | Refresh token fallback for headless envs |
| `TOCONLINE_REDIRECT_URI` | No | `https://oauth.pstmn.io/v1/callback` | OAuth2 redirect URI |
| `TOCONLINE_READ_ONLY` | No | `false` | Block all write operations when `true` |
| `TOCONLINE_MAX_WRITE_CALLS_PER_SESSION` | No | `50` | Max write tool calls per MCP session (0 = unlimited) |
| `TOCONLINE_MODULES` | No | _(all)_ | Comma-separated list of modules to load |

## Usage

### Run locally (stdio)

```bash
uv run toconline-mcp
```

### Inspect with MCP Inspector

```bash
uv run mcp dev src/toconline_mcp/server.py
```

### Install to Claude Desktop

```bash
uv run mcp install src/toconline_mcp/server.py
```

Then add your environment variables to the Claude Desktop MCP server configuration.

## Docker

The server can run inside a container for headless or server deployments. Because Docker has no system keychain, authentication uses the `TOCONLINE_REFRESH_TOKEN` env var fallback.

### Prerequisites

1. Authenticate **once locally** to obtain a refresh token:

```bash
uv run toconline-mcp auth
```

2. Copy the token into your `.env` file:

```bash
# .env
TOCONLINE_CLIENT_ID=your_client_id
TOCONLINE_CLIENT_SECRET=your_client_secret
TOCONLINE_REFRESH_TOKEN=your_refresh_token
```

### Run with Docker Compose

```bash
# Full access (all modules, writes enabled)
docker compose up

# Read-only mode (limited modules, all writes blocked)
docker compose --profile readonly up
```

### Build and run manually

```bash
docker build -t toconline-mcp:latest .
docker run --env-file .env toconline-mcp:latest
```

## Tool Modules

| Module | Tools | Description |
|---|---|---|
| `customers` | 5 | List, get, create, update, delete customers |
| `suppliers` | 5 | List, get, create, update, delete suppliers |
| `addresses` | 5 | Manage postal addresses for any entity |
| `contacts` | 5 | Manage contact records for any entity |
| `products` | 4 | List, create, update, delete products |
| `services` | 4 | List, create, update, delete services |
| `sales_documents` | 11 | Invoices, quotes, finalization, PDF, email, AT communication |
| `sales_receipts` | 8 | Receipts, lines, email |
| `purchase_documents` | 9 | Purchase invoices, lines, PDF |
| `purchase_payments` | 8 | Purchase payments and lines |
| `auxiliary` | 10 | Taxes, countries, currencies, units, bank/cash accounts, expense categories, document series |

### Selective module loading

To load only a subset of modules, set `TOCONLINE_MODULES`:

```bash
TOCONLINE_MODULES=auxiliary,customers,sales_documents uv run toconline-mcp
```

### Read-only mode

To prevent any data modifications:

```bash
TOCONLINE_READ_ONLY=true uv run toconline-mcp
```

## Project Structure

```
toconline-mcp/
├── .env.example              # Environment variable template
├── .python-version           # Pinned Python version
├── .pre-commit-config.yaml   # Pre-commit hooks (lint, format, secret detection)
├── docker-compose.yml        # Docker Compose for containerised deployments
├── Dockerfile                # Container image definition
├── pyproject.toml
├── README.md
├── swagger.yaml              # TOC Online OpenAPI spec
├── uv.lock                   # Reproducible dependency lockfile
├── .github/
│   └── workflows/
│       ├── ci.yml            # Lint + test on every push/PR
│       ├── security.yml      # Dependency audit + secret scan
│       └── release.yml       # Publish to PyPI on version tag
├── src/
│   └── toconline_mcp/
│       ├── cli.py            # CLI entry point (auth, --status, --logout)
│       ├── server.py         # FastMCP entry point & module loader
│       ├── app.py            # FastMCP app instance & lifespan
│       ├── auth.py           # OAuth2 PKCE token management
│       ├── keychain.py       # Secure token storage via OS keychain
│       ├── client.py         # Async httpx wrapper
│       ├── settings.py       # Pydantic-settings configuration
│       └── tools/
│           ├── _base.py
│           ├── customers.py
│           ├── suppliers.py
│           ├── addresses.py
│           ├── contacts.py
│           ├── products.py
│           ├── services.py
│           ├── sales_documents.py
│           ├── sales_receipts.py
│           ├── purchase_documents.py
│           ├── purchase_payments.py
│           └── auxiliary.py
└── tests/
    ├── conftest.py
    ├── test_app.py
    ├── test_auth.py
    ├── test_base.py
    ├── test_client.py
    ├── test_keychain.py
    └── test_settings.py
```

## License

MIT — see [LICENSE](LICENSE) for details.
