"""Root entry point for local development.

Run locally:
    uv run python main.py

Or via the installed script:
    uv run resp-mcp-server
"""

from resp_mcp.server import main

if __name__ == "__main__":
    main()
