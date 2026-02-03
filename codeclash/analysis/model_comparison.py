#!/usr/bin/env python3
"""
Model Comparison Matrix for Inverse Strategy

Compares multiple models' ability to recover the same target strategy.
Generates a summary table and comparison visualizations.

Usage:
    python -m inverse_strategy.analysis.model_comparison
    python -m inverse_strategy.analysis.model_comparison -d /path/to/logs
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from codeclash.constants import LOG_DIR


@dataclass
class ModelResult:
    """Results for a model on a specific target."""
    model: str
    target: str
    game: str
    runs: list[dict] = field(default_factory=list)
    
    @property
    def num_runs(self) -> int:
        return len(self.runs)
    
    @property
    def best_accuracy(self) -> float:
        if not self.runs:
            return 0.0
        return max(r["best_accuracy"] for r in self.runs)
    
    @property
    def mean_best_accuracy(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r["best_accuracy"] for r in self.runs) / len(self.runs)
    
    @property
    def baseline_accuracy(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r["baseline_accuracy"] for r in self.runs) / len(self.runs)
    
    @property
    def improvement(self) -> float:
        """Improvement from baseline to best."""
        return self.mean_best_accuracy - self.baseline_accuracy
    
    @property
    def total_cost(self) -> float:
        return sum(r["total_cost"] for r in self.runs)
    
    @property
    def mean_cost(self) -> float:
        if not self.runs:
            return 0.0
        return self.total_cost / len(self.runs)


def find_inverse_strategy_folders(log_dir: Path) -> list[Path]:
    """Find all inverse strategy log folders."""
    folders = []
    for item in log_dir.iterdir():
        if item.is_dir() and item.name.startswith("InverseStrategy"):
            metadata_path = item / "metadata.json"
            if metadata_path.exists():
                folders.append(item)
    return folders


def extract_model_name(metadata: dict) -> str:
    """Extract learner model name from metadata."""
    players = metadata.get("config", {}).get("players", [])
    for player in players:
        if player.get("agent") == "inverse":
            model_name = player.get("config", {}).get("model", {}).get("model_name", "")
            return model_name.split("/")[-1] if model_name else "unknown"
    return "unknown"


def extract_target_name(metadata: dict) -> str:
    """Extract target strategy name from metadata."""
    players = metadata.get("config", {}).get("players", [])
    for player in players:
        if player.get("agent") == "static":
            source_path = player.get("args", {}).get("source_path", "")
            if source_path:
                parts = Path(source_path).parts
                return parts[-1] if parts[-1] else (parts[-2] if len(parts) > 1 else "target")
    return "target"


def extract_total_cost(metadata: dict) -> float:
    """Extract total cost from metadata."""
    agents = metadata.get("agents", [])
    for agent in agents:
        if agent.get("config", {}).get("agent") == "inverse":
            stats = agent.get("agent_stats", {})
            return sum(s.get("cost", 0) for s in stats.values())
    return 0.0


def main(log_dir: Path, output_path: Path | None = None):
    """Generate model comparison report."""
    print(f"Analyzing inverse strategy experiments in {log_dir}...")
    
    folders = find_inverse_strategy_folders(log_dir)
    print(f"Found {len(folders)} experiments")
    
    # Collect data by model + target
    results: dict[str, ModelResult] = {}
    
    for folder in tqdm(folders, desc="Processing"):
        try:
            metadata = json.loads((folder / "metadata.json").read_text())
        except Exception as e:
            print(f"Skipping {folder.name}: {e}")
            continue
        
        model = extract_model_name(metadata)
        target = extract_target_name(metadata)
        game = metadata.get("config", {}).get("game", {}).get("name", "Unknown")
        accuracy_history = metadata.get("accuracy_history", {})
        
        if not accuracy_history:
            continue
        
        # Key by model + target
        key = f"{model}@{target}"
        
        if key not in results:
            results[key] = ModelResult(model=model, target=target, game=game)
        
        # Extract run info
        accuracies = list(accuracy_history.values())
        run_info = {
            "folder": folder.name,
            "baseline_accuracy": accuracies[0] if accuracies else 0.0,
            "best_accuracy": max(accuracies) if accuracies else 0.0,
            "final_accuracy": accuracies[-1] if accuracies else 0.0,
            "rounds": len(accuracy_history),
            "total_cost": extract_total_cost(metadata),
        }
        results[key].runs.append(run_info)
    
    if not results:
        print("No data found!")
        return
    
    # Print comparison table
    print("\n" + "=" * 100)
    print("MODEL COMPARISON: Strategy Recovery Performance")
    print("=" * 100)
    
    # Group by target
    targets = set(r.target for r in results.values())
    
    for target in sorted(targets):
        print(f"\n📎 Target: {target}")
        print("-" * 80)
        
        target_results = [r for r in results.values() if r.target == target]
        target_results.sort(key=lambda r: -r.mean_best_accuracy)
        
        print(f"{'Model':<25} {'Runs':>5} {'Baseline':>10} {'Best':>10} {'Mean Best':>12} {'Improve':>10} {'Cost':>10}")
        print("-" * 80)
        
        for r in target_results:
            print(
                f"{r.model:<25} "
                f"{r.num_runs:>5} "
                f"{r.baseline_accuracy*100:>9.1f}% "
                f"{r.best_accuracy*100:>9.1f}% "
                f"{r.mean_best_accuracy*100:>11.1f}% "
                f"{r.improvement*100:>+9.1f}% "
                f"${r.mean_cost:>8.2f}"
            )
    
    # Overall leaderboard
    print("\n" + "=" * 100)
    print("🏆 OVERALL LEADERBOARD (by Mean Best Accuracy)")
    print("=" * 100)
    
    all_results = sorted(results.values(), key=lambda r: -r.mean_best_accuracy)
    
    print(f"{'Rank':<6} {'Model':<25} {'Target':<20} {'Mean Best':>12} {'Runs':>6}")
    print("-" * 75)
    
    for i, r in enumerate(all_results[:20], 1):
        print(f"{i:<6} {r.model:<25} {r.target:<20} {r.mean_best_accuracy*100:>11.1f}% {r.num_runs:>6}")
    
    # Save JSON report
    if output_path is None:
        output_path = log_dir / "model_comparison.json"
    
    report = {
        "summary": {
            "total_experiments": len(folders),
            "unique_models": len(set(r.model for r in results.values())),
            "unique_targets": len(targets),
        },
        "results": [
            {
                "model": r.model,
                "target": r.target,
                "game": r.game,
                "num_runs": r.num_runs,
                "baseline_accuracy": r.baseline_accuracy,
                "best_accuracy": r.best_accuracy,
                "mean_best_accuracy": r.mean_best_accuracy,
                "improvement": r.improvement,
                "mean_cost": r.mean_cost,
            }
            for r in all_results
        ],
    }
    
    output_path.write_text(json.dumps(report, indent=2))
    print(f"\n✅ Saved report to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate model comparison report")
    parser.add_argument(
        "-d", "--directory",
        type=str,
        default=None,
        help="Logs directory (defaults to LOG_DIR)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output JSON file path",
    )
    
    args = parser.parse_args()
    
    log_dir = Path(args.directory) if args.directory else LOG_DIR
    output_path = Path(args.output) if args.output else None
    
    main(log_dir, output_path)
