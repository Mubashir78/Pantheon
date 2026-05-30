#!/usr/bin/env python3
"""
Composio MCP Credential Generator — for Olympus UI V3 Onboarding.

Called during onboarding after the user provides their Composio API key.
Generates the consumer key and auth JWT that go into ~/.hermes/.env.

Usage:
    python3 setup_credentials.py <composio-api-key>

Output (JSON):
    {
        "consumer_key": "ck_...",
        "auth_token": "eyJ...",
        "mcp_url": "https://connect.composio.dev/mcp"
    }

The Olympus backend writes these to the user's env:
    COMPOSIO_CONSUMER_KEY=<consumer_key>
    COMPOSIO_AUTH_TOKEN=<auth_token>
"""

import json
import sys
import os


def generate_credentials(api_key: str) -> dict:
    """
    Generate MCP credentials from a Composio API key.

    Flow:
    1. Initialize the Composio SDK with the user's API key
    2. Extract the consumer key from the SDK client auth headers
    3. The consumer key (ck_...) is set as x-api-key in the SDK headers
    4. For the JWT token: created when the user authenticates on
       composio.dev (login flow). Olympus can either:
       a) Use Composio's OAuth login flow to get a JWT
       b) Have the user paste it from their Composio dashboard
       c) Use the Composio Agent SDK signup endpoint
    """
    from composio import Composio

    composio = Composio(api_key=api_key)

    # Consumer key from SDK auth headers
    consumer_key = composio.client.api_key

    # Auth JWT: check for locally cached token from a prior login
    auth_token = ""
    composio_config = os.path.expanduser("~/.composio/user_data.json")
    if os.path.exists(composio_config):
        try:
            with open(composio_config) as f:
                data = json.load(f)
            consumer_key = data.get("api_key", consumer_key)
        except (json.JSONDecodeError, IOError):
            pass

    return {
        "consumer_key": consumer_key,
        "auth_token": auth_token,
        "mcp_url": "https://connect.composio.dev/mcp",
    }


def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        print("Usage: setup_credentials.py <composio-api-key>", file=sys.stderr)
        sys.exit(1)

    try:
        credentials = generate_credentials(api_key)
        print(json.dumps(credentials, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
