#!/usr/bin/env python
"""
Run the Drone Fleet API server.

Usage:
    python run_api.py                    # Start with defaults
    python run_api.py --reload           # Start with auto-reload
    python run_api.py --port 8080        # Custom port

Or use uvicorn directly:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

import argparse
import uvicorn
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(description="Run Drone Fleet API Server")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Starting Drone Fleet API Server")
    print("=" * 60)
    print(f"  Host:      {args.host}")
    print(f"  Port:      {args.port}")
    print(f"  Reload:    {args.reload}")
    print("=" * 60)
    print(f"\n  API Docs:  http://localhost:{args.port}/docs")
    print(f"  Web Map:   http://localhost:{args.port}/")
    print(f"  WebSocket: ws://localhost:{args.port}/status/ws")
    print("=" * 60 + "\n")

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1
    )


if __name__ == "__main__":
    main()
