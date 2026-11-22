"""Start a loopback-only Phoenix UI/collector with repository-local storage."""

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

from eval.phoenix.config import ROOT

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=6006)
    parser.add_argument("--grpc-port", type=int, default=4317)
    args = parser.parse_args()
    os.environ["PHOENIX_HOST"] = "127.0.0.1"
    os.environ.setdefault("PHOENIX_WORKING_DIR", str(ROOT / ".phoenix"))
    os.environ.setdefault("PHOENIX_TELEMETRY_ENABLED", "false")
    os.environ.setdefault("PHOENIX_DISABLE_AGENT_ASSISTANT", "true")
    os.environ.setdefault("PHOENIX_LOG_MIGRATIONS", "false")
    os.environ.setdefault("PHOENIX_DB_LOGGING_LEVEL", "WARNING")
    from phoenix.server.main import main as phoenix_main

    sys.argv = [
        sys.argv[0],
        "serve",
        "--port",
        str(args.port),
        "--grpc-port",
        str(args.grpc_port),
        "--no-internet",
    ]
    phoenix_main()


if __name__ == "__main__":
    main()
