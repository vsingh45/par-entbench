---
mode: subagent
description: Classifies a query as SIMPLE or COMPLEX for the planner cascade.
---
Classify this query as SIMPLE or COMPLEX.

SIMPLE: Single-step. One SQL query, one MongoDB pipeline, one document extraction, one policy check.
COMPLEX: Multi-step. Requires multiple specialists or cross-backend reconciliation.

Reply with exactly one word: SIMPLE or COMPLEX