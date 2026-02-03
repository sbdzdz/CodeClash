#!/usr/bin/env python3
"""
Freeze the Inverse Strategy Viewer into a static site.

This generates static HTML files that can be hosted on any web server
without requiring a Python backend.

Usage:
    python scripts/freeze_viewer.py -d /path/to/logs -o ./build
"""

import argparse
import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from codeclash import REPO_DIR


def main(log_dir: Path, output_dir: Path):
    """Generate static site from log data."""
    print(f"📁 Reading logs from: {log_dir}")
    print(f"📦 Output directory: {output_dir}")
    
    # Clean output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    
    # Set up Jinja2 environment
    template_dir = REPO_DIR / "src" / "inverse_strategy" / "viewer" / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Add filters
    env.filters["format_percent"] = lambda v: f"{v * 100:.1f}%" if isinstance(v, (int, float)) else v
    env.filters["format_cost"] = lambda v: f"${v:.2f}" if isinstance(v, (int, float)) else v
    
    # Find all experiments
    folders = []
    for item in sorted(log_dir.iterdir(), reverse=True):
        if item.is_dir() and item.name.startswith("InverseStrategy"):
            metadata_path = item / "metadata.json"
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text())
                    accuracy_history = metadata.get("accuracy_history", {})
                    
                    # Extract model name
                    model = "unknown"
                    target = "target"
                    for player in metadata.get("config", {}).get("players", []):
                        if player.get("agent") == "inverse":
                            model_name = player.get("config", {}).get("model", {}).get("model_name", "")
                            model = model_name.split("/")[-1] if model_name else "unknown"
                        if player.get("agent") == "static":
                            source_path = player.get("args", {}).get("source_path", "")
                            if source_path:
                                parts = Path(source_path).parts
                                target = parts[-1] if parts[-1] else (parts[-2] if len(parts) > 1 else "target")
                    
                    folders.append({
                        "path": item.name,
                        "name": item.name,
                        "game": metadata.get("config", {}).get("game", {}).get("name", "Unknown"),
                        "learner": model,
                        "target": target,
                        "rounds": len(accuracy_history),
                        "total_rounds": metadata.get("config", {}).get("tournament", {}).get("rounds"),
                        "accuracy": accuracy_history,
                        "best_accuracy": max(accuracy_history.values()) if accuracy_history else 0,
                        "metadata": metadata,
                    })
                except Exception as e:
                    print(f"  ⚠️ Skipping {item.name}: {e}")
    
    print(f"📊 Found {len(folders)} experiments")
    
    # Generate index page
    index_template = env.get_template("index.html")
    index_html = index_template.render(folders=folders, log_dir=str(log_dir))
    (output_dir / "index.html").write_text(index_html)
    print("  ✅ Generated index.html")
    
    # Generate experiment pages
    experiment_template = env.get_template("experiment.html")
    trajectory_template = env.get_template("trajectory.html")
    
    for folder in folders:
        exp_dir = output_dir / "experiment" / folder["name"]
        exp_dir.mkdir(parents=True, exist_ok=True)
        
        metadata = folder["metadata"]
        accuracy_data = folder["accuracy"]
        
        # Get agent stats
        agent_stats = {}
        for agent in metadata.get("agents", []):
            if agent.get("config", {}).get("agent") == "inverse":
                agent_stats = agent.get("agent_stats", {})
        
        # Create a simple metadata wrapper
        class MetadataWrapper:
            def __init__(self, data, model, target):
                self._data = data
                self._model = model
                self._target = target
            
            @property
            def game_name(self):
                return self._data.get("config", {}).get("game", {}).get("name", "Unknown")
            
            @property
            def learner_model(self):
                return self._model
            
            @property
            def target_name(self):
                return self._target
        
        metadata_wrapper = MetadataWrapper(metadata, folder["learner"], folder["target"])
        
        # Generate experiment page
        exp_html = experiment_template.render(
            metadata=metadata_wrapper,
            folder_path=folder["name"],
            folder_name=folder["name"],
            accuracy_data=accuracy_data,
            agent_stats=agent_stats,
        )
        (exp_dir / "index.html").write_text(exp_html)
        
        # Generate trajectory pages for each round
        for round_key in accuracy_data.keys():
            if round_key == "0":
                continue
            
            round_dir = exp_dir / "trajectory" / round_key
            round_dir.mkdir(parents=True, exist_ok=True)
            
            # Load trajectory if available
            traj_path = log_dir / folder["name"] / "players" / "learner" / f"learner_r{round_key}.traj.json"
            trajectory = None
            if traj_path.exists():
                try:
                    trajectory = json.loads(traj_path.read_text())
                except:
                    pass
            
            # Load traces if available
            traces_path = log_dir / folder["name"] / "rounds" / round_key / "traces.json"
            traces = None
            if traces_path.exists():
                try:
                    traces = json.loads(traces_path.read_text())
                except:
                    pass
            
            traj_html = trajectory_template.render(
                metadata=metadata_wrapper,
                folder_path=folder["name"],
                folder_name=folder["name"],
                round_num=round_key,
                trajectory=trajectory,
                traces=traces,
            )
            (round_dir / "index.html").write_text(traj_html)
        
        print(f"  ✅ Generated {folder['name']}/")
    
    # Generate error page
    error_template = env.get_template("error.html")
    error_html = error_template.render(message="Page not found")
    (output_dir / "error.html").write_text(error_html)
    
    print(f"\n🎉 Static site generated at {output_dir}")
    print(f"   To preview: cd {output_dir} && python -m http.server 8080")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Freeze viewer into static site")
    parser.add_argument(
        "-d", "--directory",
        type=str,
        required=True,
        help="Logs directory to include",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./build",
        help="Output directory for static site (default: ./build)",
    )
    
    args = parser.parse_args()
    
    main(Path(args.directory), Path(args.output))
