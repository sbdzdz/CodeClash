"""Visualization utilities for Inverse Strategy analysis."""

from pathlib import Path

from codeclash import REPO_DIR

# Model display names
MODEL_TO_DISPLAY_NAME = {
    "openai/gpt-5": "GPT-5",
    "openai/gpt-4o": "GPT-4o",
    "openai/gpt-5-mini": "GPT-5 Mini",
    "openai/o3": "o3",
    "anthropic/claude-sonnet-4-20250514": "Claude Sonnet 4",
    "anthropic/claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "google/gemini-2.5-pro": "Gemini 2.5 Pro",
    "x-ai/grok-code-fast-1": "Grok Code Fast",
    "gpt-5": "GPT-5",
    "gpt-4o": "GPT-4o",
    "gpt-5-mini": "GPT-5 Mini",
    "o3": "o3",
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "grok-code-fast-1": "Grok Code Fast",
}

# Model colors for consistent plotting
MODEL_TO_COLOR = {
    "openai/gpt-5": "#04A777",
    "openai/gpt-4o": "#1E88E5",
    "openai/gpt-5-mini": "#69DDFF",
    "openai/o3": "#5E7CE2",
    "anthropic/claude-sonnet-4-20250514": "#FFD449",
    "anthropic/claude-sonnet-4-5-20250929": "#F75C03",
    "google/gemini-2.5-pro": "#d62728",
    "x-ai/grok-code-fast-1": "#031926",
    "gpt-5": "#04A777",
    "gpt-4o": "#1E88E5",
    "gpt-5-mini": "#69DDFF",
    "o3": "#5E7CE2",
    "claude-sonnet-4-20250514": "#FFD449",
    "claude-sonnet-4-5-20250929": "#F75C03",
    "gemini-2.5-pro": "#d62728",
    "grok-code-fast-1": "#031926",
}

# Output directory for visualizations
ASSETS_DIR = REPO_DIR / "docs" / "visualization"

# Line markers for multiple series
MARKERS = ["o", "s", "^", "v", "D", "p", "*", "h", "H", "+", "x", "<", ">", "d"]


def get_display_name(model: str) -> str:
    """Get display name for a model."""
    return MODEL_TO_DISPLAY_NAME.get(model, model)


def get_color(model: str) -> str:
    """Get color for a model."""
    return MODEL_TO_COLOR.get(model, "#808080")
