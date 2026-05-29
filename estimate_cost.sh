#!/bin/bash
# Estimate remaining budget and recommend next steps

PILOT_COST=$(grep -oP 'cost so far.*\$\K[0-9.]+' logs/new_tasks.log 2>/dev/null | tail -1)
BUDGET=30
REMAINING=$(echo "$BUDGET - ${PILOT_COST:-0}" | bc)

echo "========================================="
echo "BUDGET & COST ANALYSIS"
echo "========================================="
echo "Initial budget: \$$BUDGET"
echo "Pilot cost (33 × PaR × 1): \$${PILOT_COST:-?.??}"
echo "Remaining: \$$REMAINING"
echo ""

if (( $(echo "$REMAINING < 0" | bc -l) )); then
    echo "⚠️  OVER BUDGET - Pilot consumed more than expected"
    echo "Recommendation: STOP - Skip additional experiments"
    exit 1
fi

if (( $(echo "$REMAINING < 5" | bc -l) )); then
    echo "⚠️  TIGHT BUDGET (\$$REMAINING remaining)"
    echo "Recommendation: Skip full sweep, proceed to analysis"
    echo "  - Combine pilot results with existing final_sweep/"
    echo "  - Generate unified analysis tables"
    echo "  - Commit to GitHub"
    exit 0
fi

if (( $(echo "$REMAINING >= 15" | bc -l) )); then
    echo "✓ HEALTHY BUDGET (\$$REMAINING remaining)"
    echo "Recommendation: Run moderate expansion"
    echo "  - Run new tasks × 4 key routers (par, frugal, frontier, small) × 1 seed"
    echo "  - Est. cost: ~\$4-5, leaves \$$((REMAINING - 5)) buffer"
    exit 0
fi

echo "✓ ADEQUATE BUDGET (\$$REMAINING remaining)"
echo "Recommendation: Limited expansion"
echo "  - Run new tasks × 2-3 routers × 1 seed"
echo "  - Combine with existing results"
echo "  - Generate analysis"
exit 0
