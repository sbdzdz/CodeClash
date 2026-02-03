# CodeClash Downloader

Download and extract strategies from [viewer.codeclash.ai](https://viewer.codeclash.ai).

## Usage

```bash
# Run from CodeClash repo root

# 1. Download artifacts from an index page
python scripts/inverse/codeclash/download.py --index path/to/index.html
# Downloads to: data/inverse/codeclash_html/

# 2. Extract strategies from downloaded artifacts
python scripts/inverse/codeclash/extract.py
# Reads from: data/inverse/codeclash_html/
# Writes to:  data/inverse/extracted_strategies/

# Custom paths (optional)
python scripts/inverse/codeclash/download.py --index index.html --output data/inverse/my_html/
python scripts/inverse/codeclash/extract.py --input data/inverse/my_html/ --output data/inverse/my_strategies/
```

## Output Structure

```
data/inverse/
├── codeclash_html/          # Downloaded HTML files
└── extracted_strategies/     # Extracted code (git-ignored)
```

## Source

These scripts are adapted from [codeclash_viewer](https://github.com/your-org/codeclash_viewer).
