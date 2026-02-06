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
import atexit
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
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="Open an ngrok tunnel for external access"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="katamorphic-oren-equilaterally.ngrok-free.dev",
        help="ngrok static domain for a stable URL"
    )

    args = parser.parse_args()

    # Start ngrok tunnel if requested
    public_url = None
    if args.tunnel:
        try:
            from pyngrok import ngrok
            connect_kwargs = {"addr": args.port, "proto": "http"}
            if args.domain:
                connect_kwargs["domain"] = args.domain
            tunnel = ngrok.connect(**connect_kwargs)
            public_url = tunnel.public_url
            atexit.register(ngrok.disconnect, tunnel.public_url)
        except Exception as e:
            print(f"\n  WARNING: Could not start ngrok tunnel: {e}")
            print("  Install pyngrok (pip install pyngrok) and sign up at https://ngrok.com")
            print("  Then run: ngrok config add-authtoken <your-token>\n")

    print("\n" + "=" * 60)
    print("  Starting Drone Fleet API Server")
    print("=" * 60)
    print(f"  Host:      {args.host}")
    print(f"  Port:      {args.port}")
    print(f"  Reload:    {args.reload}")
    if public_url:
        print(f"  Tunnel:    {public_url}")
    print("=" * 60)
    print(f"\n  Local:     http://localhost:{args.port}/docs")
    if public_url:
        print(f"  Public:    {public_url}/docs")
        print(f"  Public WS: {public_url.replace('http', 'ws')}/status/ws")
    else:
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
