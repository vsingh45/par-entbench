# Final EntBench Results (54 Tasks, All Routers)

This document contains the comprehensive evaluation of all routers across all 54 EntBench tasks.

**Overall: 252/1157 correct (21.8%)**

Total API Cost: $13.82

## Per-Router Performance

| Router | Tasks | Correct | Accuracy | Total Cost | Avg Cost/Task | Avg Latency (ms) |
|--------|-------|---------|----------|------------|---------------|------------------|
| all_frontier                   | 162     | 40        |    24.7% | $     3.06 | $      0.0189 |             6480 |
| all_small                      | 162     | 34        |    21.0% | $     0.68 | $      0.0042 |             4977 |
| frugal_cascade                 | 162     | 34        |    21.0% | $     0.63 | $      0.0039 |             4723 |
| par                            | 162     | 36        |    22.2% | $     1.85 | $      0.0114 |             9254 |
| par_lite                       | 162     | 34        |    21.0% | $     1.86 | $      0.0115 |             8443 |
| par_no_rationale               | 24      | 0         |     0.0% | $     1.31 | $      0.0544 |            37842 |
| sink_frontier                  | 162     | 35        |    21.6% | $     2.02 | $      0.0125 |             9152 |
| source_frontier                | 161     | 39        |    24.2% | $     2.42 | $      0.0150 |             6679 |
| **OVERALL** | **1157** | **252** | **21.8%** | **$13.82** | **$0.0119** | **7739** |

## Performance by Task Class


### CROSS_RECON (n=192, acc=10.4%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 24      | 3         |    12.5% |
| all_small                      | 24      | 3         |    12.5% |
| frugal_cascade                 | 24      | 3         |    12.5% |
| par                            | 24      | 3         |    12.5% |
| par_lite                       | 24      | 3         |    12.5% |
| par_no_rationale               | 24      | 0         |     0.0% |
| sink_frontier                  | 24      | 2         |     8.3% |
| source_frontier                | 24      | 3         |    12.5% |

### EXTRACT (n=147, acc=26.5%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 21      | 6         |    28.6% |
| all_small                      | 21      | 5         |    23.8% |
| frugal_cascade                 | 21      | 4         |    19.0% |
| par                            | 21      | 6         |    28.6% |
| par_lite                       | 21      | 6         |    28.6% |
| sink_frontier                  | 21      | 6         |    28.6% |
| source_frontier                | 21      | 6         |    28.6% |

### MONGO_GEN (n=167, acc=31.1%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 24      | 9         |    37.5% |
| all_small                      | 24      | 7         |    29.2% |
| frugal_cascade                 | 24      | 6         |    25.0% |
| par                            | 24      | 6         |    25.0% |
| par_lite                       | 24      | 6         |    25.0% |
| sink_frontier                  | 24      | 9         |    37.5% |
| source_frontier                | 23      | 9         |    39.1% |

### MULTITOOL_PLAN (n=168, acc=8.3%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 24      | 4         |    16.7% |
| all_small                      | 24      | 1         |     4.2% |
| frugal_cascade                 | 24      | 3         |    12.5% |
| par                            | 24      | 3         |    12.5% |
| par_lite                       | 24      | 1         |     4.2% |
| sink_frontier                  | 24      | 1         |     4.2% |
| source_frontier                | 24      | 1         |     4.2% |

### POLICY_ACTION (n=147, acc=27.9%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 21      | 6         |    28.6% |
| all_small                      | 21      | 6         |    28.6% |
| frugal_cascade                 | 21      | 6         |    28.6% |
| par                            | 21      | 6         |    28.6% |
| par_lite                       | 21      | 6         |    28.6% |
| sink_frontier                  | 21      | 5         |    23.8% |
| source_frontier                | 21      | 6         |    28.6% |

### SQL_COMPOSE (n=168, acc=0.0%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 24      | 0         |     0.0% |
| all_small                      | 24      | 0         |     0.0% |
| frugal_cascade                 | 24      | 0         |     0.0% |
| par                            | 24      | 0         |     0.0% |
| par_lite                       | 24      | 0         |     0.0% |
| sink_frontier                  | 24      | 0         |     0.0% |
| source_frontier                | 24      | 0         |     0.0% |

### SQL_GEN (n=168, acc=51.2%)

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier                   | 24      | 12        |    50.0% |
| all_small                      | 24      | 12        |    50.0% |
| frugal_cascade                 | 24      | 12        |    50.0% |
| par                            | 24      | 12        |    50.0% |
| par_lite                       | 24      | 12        |    50.0% |
| sink_frontier                  | 24      | 12        |    50.0% |
| source_frontier                | 24      | 14        |    58.3% |
