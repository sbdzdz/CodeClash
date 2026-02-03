#!/usr/bin/env python3
"""
Launch script for the Inverse Strategy Trajectory Viewer
"""

import argparse
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inverse Strategy Trajectory Viewer")
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=None,
        help="Logs directory to search for experiments (defaults to ./logs)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=5002,
        help="Port to run the server on (default: 5002)",
    )

    args = parser.parse_args()

    from codeclash.viewer import app
    from codeclash.viewer.app import set_log_base_directory

    # Set the logs directory if provided
    if args.directory:
        set_log_base_directory(args.directory)
        print(f"📁 Using logs directory: {Path(args.directory).resolve()}")
    else:
        print(f"📁 Using logs directory: {Path.cwd() / 'logs'}")

    print("🎯 Starting Inverse Strategy Trajectory Viewer...")
    print(f"📊 Navigate to http://localhost:{args.port} to view experiments")
    print("🔧 Press Ctrl+C to stop the server")

    app.run(debug=True, host="0.0.0.0", port=args.port)
