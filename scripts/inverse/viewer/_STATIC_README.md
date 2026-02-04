# Static Hosting of Inverse Strategy Experiments

How this works:

1. Run `freeze_viewer.py` to generate the static site in the `build` directory.
2. Push to a GitHub repo or deploy to any static hosting service.
3. View the results without needing a Python backend.

## Commands

### Generate Static Site

```bash
cd /path/to/inverse_strategy

# Generate static site from logs
python scripts/freeze_viewer.py -d ./logs -o ./build

# Preview locally
cd build && python -m http.server 8080
# Then open http://localhost:8080
```

### Run Interactive Viewer

For live development/debugging:

```bash
python scripts/run_viewer.py -d ./logs
# Opens at http://localhost:5002
```

## File Structure

```
build/
├── index.html                          # Main listing page
├── error.html                          # Error page
└── experiment/
    └── InverseStrategy.BattleSnake.*/  # One folder per experiment
        ├── index.html                  # Experiment summary + accuracy chart
        └── trajectory/
            └── {round}/
                └── index.html          # Trajectory viewer for that round
```

## Deployment Options

1. **GitHub Pages**: Push `build/` to a `gh-pages` branch
2. **Netlify**: Connect repo and set build directory to `build/`
3. **S3 + CloudFront**: Upload to S3 bucket with static website hosting
4. **Any web server**: Just serve the `build/` directory

## Related Scripts

- `scripts/run_viewer.py` - Interactive Flask viewer
- `scripts/freeze_viewer.py` - Generate static site
- `inverse_strategy.analysis.model_comparison` - Generate comparison reports
- `inverse_strategy.analysis.viz.line_chart_accuracy_per_round` - Accuracy plots
