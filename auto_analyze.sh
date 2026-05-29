#!/bin/bash
# Auto-run once pilot completes: analyze + commit

set -e

echo "======================================"
echo "AUTO-ANALYSIS: Pilot Complete"
echo "======================================"
echo ""

# Wait for 33 tasks
echo "Waiting for 33/33 tasks..."
while [ $(ls results/new_tasks/*.json 2>/dev/null | wc -l) -lt 33 ]; do
    sleep 30
done

echo "✓ Pilot complete (33/33)"
sleep 5

source .venv/bin/activate
source .env

# Extract cost from logs
echo ""
echo "Extracting cost metrics..."
if [ -f "logs/new_tasks.log" ]; then
    LAST_COST=$(tail -200 logs/new_tasks.log | grep -oP '\$[0-9.]+' | tail -1)
    echo "Pilot cost: $LAST_COST"
fi

# Run analysis
echo ""
echo "Generating combined analysis..."
python3 final_analysis.py results/final_sweep results/new_tasks results/combined

# Display results
echo ""
echo "======================================"
echo "RESULTS READY"
echo "======================================"
cat results/combined/COMBINED_ANALYSIS.md | head -30

# Commit
echo ""
echo "Committing to GitHub..."
git add -A
git commit -m "Add new task experiment results: 54-task benchmark complete

Pilot experiment: 33 new tasks × PaR router × 1 seed
Combined analysis with existing: 21 tasks × 8 routers × 3 seeds

Per-router accuracy and cost metrics computed.
Results in results/combined/:
  - COMBINED_ANALYSIS.md (performance tables)
  - ANALYSIS.json (structured metrics)

EntBench now includes:
  - 54 total tasks (21 original + 33 new)
  - 7 task classes fully represented
  - Expanded coverage: SQL, Mongo, Extract, Compose, XR, MTP, Policy

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push origin main

echo ""
echo "✓ COMPLETE"
echo "  - Analysis: results/combined/COMBINED_ANALYSIS.md"
echo "  - Metrics: results/combined/ANALYSIS.json"
echo "  - Commit: $(git rev-parse --short HEAD)"
