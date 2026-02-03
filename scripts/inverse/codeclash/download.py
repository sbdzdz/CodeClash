#!/usr/bin/env python3
"""
Download CodeClash artifacts from viewer.codeclash.ai

Usage:
    python -m inverse_strategy.codeclash.download --index path/to/index.html
"""

import argparse
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


def extract_data_paths(html_file: Path) -> list[str]:
    """Extract all unique data paths from the index HTML file."""
    with open(html_file, 'r') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    paths = set()
    for elem in soup.find_all(attrs={'data-path': True}):
        paths.add(elem['data-path'])
    
    return sorted(paths)


def download_trajectory(base_url: str, data_path: str, output_dir: Path) -> tuple[bool, str | None]:
    """Download trajectory HTML file for a given path."""
    path_segments = data_path.split("/")
    encoded_segments = [requests.utils.quote(seg, safe='') for seg in path_segments]
    url = f"{base_url}/game/{'/'.join(encoded_segments)}.html"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        output_path = output_dir / data_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(f"{output_path}.html", 'w') as f:
            f.write(response.text)
        
        return True, None
    
    except Exception as e:
        return False, str(e)


def download_codeclash(
    index_html: Path,
    output_dir: Path,
    base_url: str = "https://viewer.codeclash.ai",
    delay: float = 0.1,
) -> dict:
    """
    Download all CodeClash artifacts.
    
    Args:
        index_html: Path to downloaded index.html from viewer.codeclash.ai
        output_dir: Where to save downloaded HTML files
        base_url: CodeClash viewer URL
        delay: Delay between requests (be nice to server)
    
    Returns:
        dict with success_count, failed list
    """
    print(f"Extracting data paths from {index_html}...")
    data_paths = extract_data_paths(index_html)
    print(f"Found {len(data_paths)} unique trajectories")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    failed = []
    
    print("\nDownloading trajectories...")
    for path in tqdm(data_paths):
        success, error = download_trajectory(base_url, path, output_dir)
        
        if success:
            success_count += 1
        else:
            failed.append((path, error))
        
        time.sleep(delay)
    
    print(f"\n✓ Successfully downloaded: {success_count}/{len(data_paths)}")
    
    if failed:
        print(f"✗ Failed downloads: {len(failed)}")
        failed_file = output_dir / "failed_downloads.txt"
        with open(failed_file, 'w') as f:
            for path, error in failed:
                f.write(f"{path}: {error}\n")
        print(f"Failed paths saved to {failed_file}")
    
    return {"success_count": success_count, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="Download CodeClash artifacts")
    parser.add_argument("--index", type=Path, required=True,
                        help="Path to index.html from viewer.codeclash.ai")
    parser.add_argument("--output", type=Path, default=Path("data/inverse/codeclash_html"),
                        help="Output directory (default: data/inverse/codeclash_html)")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between requests in seconds")
    args = parser.parse_args()
    
    download_codeclash(args.index, args.output, delay=args.delay)


if __name__ == "__main__":
    main()
