#!/bin/bash
# Runs after pilot completes: decide and run next experiment phase

set -e

source .venv/bin/activate
source .env

BUDGET=30
PILOT_RESULTS=$(ls results/new_tasks/*.json 2>/dev/null | wc -l)

echo "========================================="
echo "PILOT COMPLETE: $PILOT_RESULTS/33 tasks"
echo "========================================="

# Extract cost from final summary
if [ -f "logs/new_tasks.log" ]; then
    LAST_LINE=$(tail -20 logs/new_tasks.log | grep -i "cost\|spent\|total" | tail -1)
    echo "Log summary: $LAST_LINE"
fi

# For now, estimate cost: ~33 tasks * ~$0.08-0.15 per task = $2.60-4.95
PILOT_EST=3.50
REMAINING=$(echo "$BUDGET - $PILOT_EST" | bc)

echo ""
echo "Budget estimate:"
echo "  Pilot cost: ~\$$PILOT_EST"
echo "  Remaining: ~\$$REMAINING"
echo ""

if (( $(echo "$REMAINING < 5" | bc -l) )); then
    echo "⚠️  TIGHT BUDGET - Skipping additional experiments"
    echo ""
    echo "Running final analysis with:"
    echo "  - Pilot: 33 tasks × PaR × 1 seed"
    echo "  - Existing: 21 tasks × 8 routers × 3 seeds"
    echo ""
    python3 final_analysis.py results/final_sweep results/new_tasks results/combined
    exit 0
fi

# Run moderate expansion
echo "✓ RUNNING NEXT PHASE"
echo "  Tasks: 33 new tasks"
echo "  Routers: frugal_cascade, all_frontier, all_small"
echo "  Seeds: 1"
echo "  Est. cost: ~\$2-3"
echo ""

mkdir -p results/new_tasks_extended logs
par-entbench --tasks new --routers frugal_cascade,all_frontier,all_small --seeds 1 \
    --output results/new_tasks_extended/ --kill-switch-usd 70 \
    > logs/new_tasks_extended.log 2>&1 &

PID=$!
echo "Started (PID: $PID)"
echo "Track progress: tail -f logs/new_tasks_extended.log"
echo ""
echo "Once complete, run:"
echo "  python3 final_analysis.py results/final_sweep results/new_tasks_extended results/combined"
