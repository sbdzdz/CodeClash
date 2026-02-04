#!/usr/bin/env python3
"""
Trajectory Viewer for Inverse Strategy Recovery

A Flask-based web application to visualize agent learning trajectories
and strategy recovery progress.
"""

import functools
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_from_directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Global configuration
_log_base_directory: Path = Path.cwd() / "logs"
_static_mode: bool = False


def set_log_base_directory(directory: str | Path):
    """Set the base directory for log files."""
    global _log_base_directory
    _log_base_directory = Path(directory)


def set_static_mode(enabled: bool = True):
    """Enable/disable static mode (for frozen sites)."""
    global _static_mode
    _static_mode = enabled


@dataclass
class CacheEntry:
    """Cache entry with data and timestamp"""
    data: Any
    timestamp: datetime


class SimpleCache:
    """Simple in-memory cache with timeout."""

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str, timeout_seconds: int | None = None) -> Any | None:
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if timeout_seconds is not None:
                age = (datetime.now() - entry.timestamp).total_seconds()
                if age > timeout_seconds:
                    del self._cache[key]
                    return None
            return entry.data

    def set(self, key: str, value: Any):
        with self._lock:
            self._cache[key] = CacheEntry(data=value, timestamp=datetime.now())

    def clear(self):
        with self._lock:
            self._cache.clear()


_cache = SimpleCache()


class Metadata:
    """Wrapper around metadata dictionary with convenient access methods."""

    def __init__(self, data: dict[str, Any] | None = None):
        self._data = data or {}

    def get_path(self, path: str, default: Any = None) -> Any:
        """Get value from nested dictionary using dot notation path."""
        current = self._data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @property
    def is_valid(self) -> bool:
        return bool(self._data)

    @property
    def total_rounds(self) -> int | None:
        return self.get_path("config.tournament.rounds")

    @property
    def completed_rounds(self) -> int:
        round_stats = self.get_path("round_stats", {})
        return len(round_stats)

    @property
    def accuracy_history(self) -> dict[str, float]:
        return self.get_path("accuracy_history", {})

    @property
    def learner_model(self) -> str:
        """Get learner's model name."""
        players = self.get_path("config.players", [])
        for player in players:
            if player.get("agent") == "inverse":
                model_name = player.get("config", {}).get("model", {}).get("model_name", "")
                return model_name.split("/")[-1] if model_name else "unknown"
        return "unknown"

    @property
    def target_name(self) -> str:
        """Get target strategy name."""
        players = self.get_path("config.players", [])
        for player in players:
            if player.get("agent") == "static":
                source_path = player.get("args", {}).get("source_path", "")
                if source_path:
                    parts = Path(source_path).parts
                    return parts[-1] if parts[-1] else (parts[-2] if len(parts) > 1 else "target")
        return "target"

    @property
    def game_name(self) -> str:
        return self.get_path("config.game.name", "Unknown")

    @property
    def agent_stats(self) -> dict[str, Any]:
        """Get agent statistics per round."""
        agents = self.get_path("agents", [])
        for agent in agents:
            if agent.get("config", {}).get("agent") == "inverse":
                return agent.get("agent_stats", {})
        return {}

    @property
    def raw_data(self) -> dict[str, Any]:
        return self._data


def load_metadata(log_dir: Path) -> Metadata:
    """Load metadata from a log directory."""
    metadata_path = log_dir / "metadata.json"
    if metadata_path.exists():
        try:
            data = json.loads(metadata_path.read_text())
            return Metadata(data)
        except Exception as e:
            logger.error(f"Failed to load metadata from {metadata_path}: {e}")
    return Metadata()


def is_inverse_strategy_folder(log_dir: Path) -> bool:
    """Check if a directory is an inverse strategy log folder."""
    if not log_dir.is_dir():
        return False
    metadata_path = log_dir / "metadata.json"
    if not metadata_path.exists():
        return False
    # Check if it starts with InverseStrategy
    return log_dir.name.startswith("InverseStrategy")


def find_all_log_folders(base_dir: Path) -> list[dict[str, Any]]:
    """Find all inverse strategy log folders (recursively)."""
    folders = []
    
    def scan_dir(directory: Path):
        """Recursively scan for InverseStrategy folders."""
        try:
            for item in sorted(directory.iterdir(), reverse=True):
                if item.is_dir():
                    if is_inverse_strategy_folder(item):
                        metadata = load_metadata(item)
                        if metadata.is_valid:
                            folders.append({
                                "path": str(item),
                                "name": item.name,
                                "game": metadata.game_name,
                                "learner": metadata.learner_model,
                                "target": metadata.target_name,
                                "rounds": metadata.completed_rounds,
                                "total_rounds": metadata.total_rounds,
                                "accuracy": metadata.accuracy_history,
                                "best_accuracy": max(metadata.accuracy_history.values()) if metadata.accuracy_history else 0,
                            })
                    else:
                        # Recurse into subdirectories
                        scan_dir(item)
        except PermissionError:
            pass
    
    scan_dir(base_dir)
    return folders


def load_trajectory(log_dir: Path, round_num: int) -> dict[str, Any] | None:
    """Load trajectory for a specific round."""
    players_dir = log_dir / "players" / "learner"
    traj_file = players_dir / f"learner_r{round_num}.traj.json"
    
    if traj_file.exists():
        try:
            return json.loads(traj_file.read_text())
        except Exception as e:
            logger.error(f"Failed to load trajectory: {e}")
    return None


def load_traces(log_dir: Path, round_num: int) -> dict[str, Any] | None:
    """Load traces for a specific round."""
    traces_file = log_dir / "rounds" / str(round_num) / "traces.json"
    
    if traces_file.exists():
        try:
            return json.loads(traces_file.read_text())
        except Exception as e:
            logger.error(f"Failed to load traces: {e}")
    return None


@app.route("/")
def index():
    """Main page - list all experiments."""
    folders = find_all_log_folders(_log_base_directory)
    return render_template("index.html", folders=folders, log_dir=str(_log_base_directory))


@app.route("/experiment")
def experiment_view():
    """View a specific experiment."""
    folder_path = request.args.get("path", "")
    if not folder_path:
        return render_template("error.html", message="No experiment path provided")
    
    full_path = Path(folder_path)
    if not full_path.is_absolute():
        # Try relative to current directory first
        cwd_path = Path.cwd() / folder_path
        if cwd_path.exists():
            full_path = cwd_path
        else:
            # Then try relative to log base directory
            full_path = _log_base_directory / folder_path
    
    logger.info(f"Experiment view: folder_path={folder_path}, full_path={full_path}, exists={full_path.exists()}")
    
    metadata = load_metadata(full_path)
    if not metadata.is_valid:
        return render_template("error.html", message=f"Invalid experiment: {folder_path} (resolved to {full_path})")
    
    # Get accuracy history for chart
    accuracy_data = metadata.accuracy_history
    
    # Get agent stats
    agent_stats = metadata.agent_stats
    
    return render_template(
        "experiment.html",
        metadata=metadata,
        folder_path=str(full_path),
        folder_name=full_path.name,
        accuracy_data=accuracy_data,
        agent_stats=agent_stats,
    )


@app.route("/trajectory")
def trajectory_view():
    """View trajectory for a specific round."""
    folder_path = request.args.get("path", "")
    round_num = request.args.get("round", type=int, default=1)
    
    if not folder_path:
        return render_template("error.html", message="No experiment path provided")
    
    full_path = Path(folder_path)
    if not full_path.is_absolute():
        full_path = _log_base_directory / folder_path
    
    metadata = load_metadata(full_path)
    trajectory = load_trajectory(full_path, round_num)
    traces = load_traces(full_path, round_num)
    
    return render_template(
        "trajectory.html",
        metadata=metadata,
        folder_path=str(full_path),
        folder_name=full_path.name,
        round_num=round_num,
        trajectory=trajectory,
        traces=traces,
    )


@app.route("/api/accuracy")
def api_accuracy():
    """API endpoint for accuracy data."""
    folder_path = request.args.get("path", "")
    if not folder_path:
        return jsonify({"error": "No path provided"}), 400
    
    full_path = Path(folder_path)
    if not full_path.is_absolute():
        full_path = _log_base_directory / folder_path
    
    metadata = load_metadata(full_path)
    return jsonify({
        "accuracy": metadata.accuracy_history,
        "learner": metadata.learner_model,
        "target": metadata.target_name,
    })


@app.route("/api/trajectory/<path:folder_path>/<int:round_num>")
def api_trajectory(folder_path, round_num):
    """API endpoint for trajectory data."""
    full_path = Path(folder_path)
    if not full_path.is_absolute():
        full_path = _log_base_directory / folder_path
    
    trajectory = load_trajectory(full_path, round_num)
    return jsonify(trajectory or {})


@app.route("/api/traces/<path:folder_path>/<int:round_num>")
def api_traces(folder_path, round_num):
    """API endpoint for traces data."""
    full_path = Path(folder_path)
    if not full_path.is_absolute():
        full_path = _log_base_directory / folder_path
    
    traces = load_traces(full_path, round_num)
    return jsonify(traces or {})


@app.template_filter("nl2br")
def nl2br(value):
    """Convert newlines to <br> tags."""
    if value:
        return value.replace("\n", "<br>")
    return value


@app.template_filter("format_percent")
def format_percent(value):
    """Format a float as percentage."""
    if isinstance(value, (int, float)):
        return f"{value * 100:.1f}%"
    return value


@app.template_filter("format_cost")
def format_cost(value):
    """Format cost as dollars."""
    if isinstance(value, (int, float)):
        return f"${value:.2f}"
    return value


def run(debug: bool = True, host: str = "0.0.0.0", port: int = 5002):
    """Run the Flask app."""
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Inverse Strategy Trajectory Viewer")
    parser.add_argument("--log-dir", "-d", type=str, default="logs",
                        help="Base directory for log files")
    parser.add_argument("--port", "-p", type=int, default=5002,
                        help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Host to bind to")
    parser.add_argument("--no-debug", action="store_true",
                        help="Disable debug mode")
    args = parser.parse_args()
    
    set_log_base_directory(args.log_dir)
    run(debug=not args.no_debug, host=args.host, port=args.port)
