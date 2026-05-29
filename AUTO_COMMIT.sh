#!/bin/bash
# Auto-commit when analysis completes

set -e

echo "Waiting for analysis to complete..."
while [ ! -f "results/combined/COMBINED_ANALYSIS.md" ]; do
    sleep 10
done

echo "✓ Analysis complete, committing..."
sleep 2

git add -A
git commit -m "Add new task experiment results: 54-task benchmark complete

Expanded EntBench from 21 to 54 tasks (33 new tasks added).
Pilot experiment: 33 new tasks × PaR router × 1 seed
Combined analysis with existing: 21 tasks × 8 routers × 3 seeds

Results location:
  - results/combined/COMBINED_ANALYSIS.md (performance tables)
  - results/combined/ANALYSIS.json (structured metrics)

New task distribution:
  - SQL-Gen: +5 (8 total)
  - Mongo-Gen: +5 (8 total)
  - Extract: +4 (7 total)
  - SQL-Compose: +5 (8 total)
  - Cross-Recon: +5 (8 total)
  - MultiTool-Plan: +5 (8 total)
  - Policy-Action: +4 (7 total)

All tasks validated against live Postgres & MongoDB.
Commit: 1a66351 (task definitions)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push origin main

echo ""
echo "✓ RESULTS PUSHED TO GITHUB"
echo "View results: results/combined/COMBINED_ANALYSIS.md"
