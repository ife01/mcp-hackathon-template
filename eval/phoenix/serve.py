"""Start a local Phoenix server for the respiratory eval harness.

Run from repo root:
    uv run python eval/phoenix/serve.py

Phoenix UI:   http://localhost:6006
OTLP traces:  http://localhost:6006/v1/traces
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        import phoenix as px
    except ImportError:
        print(
            "arize-phoenix not installed. Run: uv sync --group dev",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Starting Phoenix server...")
    print("  UI:     http://localhost:6006")
    print("  Traces: http://localhost:6006/v1/traces")
    print("\nKeep this terminal open while running experiments.")
    print("Press Ctrl+C to stop.\n")
    px.launch_app()


if __name__ == "__main__":
    main()
