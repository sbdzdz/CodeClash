#!/usr/bin/env python3
"""
Line chart showing accuracy progression over rounds for different models.

Usage:
    python -m inverse_strategy.analysis.viz.line_chart_accuracy_per_round
    python -m inverse_strategy.analysis.viz.line_chart_accuracy_per_round -d /path/to/logs
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from matplotlib import pyplot as plt
from tqdm import tqdm

from codeclash.analysis.viz.utils import (
    ASSETS_DIR,
    MARKERS,
    get_color,
    get_display_name,
)
from codeclash.constants import LOCAL_LOG_DIR as LOG_DIR


@dataclass
class ModelAccuracyProfile:
    """Accuracy profile for a model on a specific target."""
    model: str
    target: str
    game: str
    round_accuracies: dict[int, list[float]]  # round -> list of accuracies from different runs
    
    def mean_accuracy(self, round_idx: int) -> float:
        """Get mean accuracy for a round."""
        accs = self.round_accuracies.get(round_idx, [])
        return sum(accs) / len(accs) if accs else 0.0
    
    def std_accuracy(self, round_idx: int) -> float:
        """Get std dev of accuracy for a round."""
        accs = self.round_accuracies.get(round_idx, [])
        if len(accs) < 2:
            return 0.0
        mean = self.mean_accuracy(round_idx)
        return (sum((a - mean) ** 2 for a in accs) / len(accs)) ** 0.5


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


def main(log_dir: Path, output_path: Path | None = None):
    """Generate accuracy per round line chart."""
    print(f"Analyzing inverse strategy experiments in {log_dir}...")
    
    folders = find_inverse_strategy_folders(log_dir)
    print(f"Found {len(folders)} experiments")
    
    # Collect data by model
    profiles: dict[str, ModelAccuracyProfile] = {}
    
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
        
        # Create profile key (model + target for grouping)
        key = f"{model}@{target}"
        
        if key not in profiles:
            profiles[key] = ModelAccuracyProfile(
                model=model,
                target=target,
                game=game,
                round_accuracies={},
            )
        
        # Add accuracies from this run
        for round_str, acc in accuracy_history.items():
            round_idx = int(round_str)
            if round_idx not in profiles[key].round_accuracies:
                profiles[key].round_accuracies[round_idx] = []
            profiles[key].round_accuracies[round_idx].append(acc)
    
    if not profiles:
        print("No data found!")
        return
    
    # Print summary
    print("\n" + "=" * 60)
    print("Model Accuracy Progression")
    print("=" * 60)
    
    for key, profile in sorted(profiles.items()):
        rounds = sorted(profile.round_accuracies.keys())
        print(f"\n{get_display_name(profile.model)} → {profile.target}:")
        for r in rounds:
            mean = profile.mean_accuracy(r) * 100
            std = profile.std_accuracy(r) * 100
            n = len(profile.round_accuracies[r])
            print(f"  Round {r}: {mean:.1f}% ± {std:.1f}% (n={n})")
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for i, (key, profile) in enumerate(sorted(profiles.items())):
        rounds = sorted(profile.round_accuracies.keys())
        means = [profile.mean_accuracy(r) * 100 for r in rounds]
        stds = [profile.std_accuracy(r) * 100 for r in rounds]
        
        color = get_color(profile.model)
        marker = MARKERS[i % len(MARKERS)]
        label = f"{get_display_name(profile.model)}"
        
        ax.errorbar(
            rounds, means,
            yerr=stds,
            label=label,
            color=color,
            marker=marker,
            markersize=8,
            linewidth=2,
            capsize=4,
        )
    
    ax.set_xlabel("Round", fontsize=12)
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_title("Strategy Recovery Accuracy Over Rounds", fontsize=14, fontweight="bold")
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    # Set x-axis to integers
    max_round = max(max(p.round_accuracies.keys()) for p in profiles.values())
    ax.set_xticks(range(0, max_round + 1))
    
    plt.tight_layout()
    
    # Save
    if output_path is None:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = ASSETS_DIR / "accuracy_per_round.png"
    
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    print(f"\n✅ Saved to {output_path}")
    print(f"✅ Saved to {output_path.with_suffix('.pdf')}")
    
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate accuracy per round line chart")
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
        help="Output file path",
    )
    
    args = parser.parse_args()
    
    log_dir = Path(args.directory) if args.directory else LOG_DIR
    output_path = Path(args.output) if args.output else None
    
    main(log_dir, output_path)
