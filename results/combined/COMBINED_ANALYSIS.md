# Combined Results Analysis

## Overall Performance (All Tasks × All Routers)

| Router | Tasks | Correct | Accuracy | Total Cost | Avg Cost/Task |
|--------|-------|---------|----------|------------|--------------|
| all_frontier         | 63      | 19        |    30.2% | $      1.24 | $      0.0196 |
| all_small            | 63      | 19        |    30.2% | $      0.24 | $      0.0039 |
| frugal_cascade       | 63      | 21        |    33.3% | $      0.26 | $      0.0041 |
| par                  | 96      | 26        |    27.1% | $      1.05 | $      0.0109 |
| par_lite             | 63      | 19        |    30.2% | $      0.65 | $      0.0102 |
| par_no_rationale     | 9       | 0         |     0.0% | $      0.46 | $      0.0514 |
| sink_frontier        | 63      | 15        |    23.8% | $      0.72 | $      0.0114 |
| source_frontier      | 62      | 18        |    29.0% | $      0.92 | $      0.0149 |
| **TOTAL** | **482** | **137** | **28.4%** | **$5.53** | **$0.0115** |

## Performance by Task Class


### CROSS_RECON

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 3         |    33.3% |
| all_small            | 9       | 3         |    33.3% |
| frugal_cascade       | 9       | 3         |    33.3% |
| par                  | 14      | 3         |    21.4% |
| par_lite             | 9       | 3         |    33.3% |
| par_no_rationale     | 9       | 0         |     0.0% |
| sink_frontier        | 9       | 2         |    22.2% |
| source_frontier      | 9       | 3         |    33.3% |

### EXTRACT

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 3         |    33.3% |
| all_small            | 9       | 3         |    33.3% |
| frugal_cascade       | 9       | 3         |    33.3% |
| par                  | 13      | 4         |    30.8% |
| par_lite             | 9       | 3         |    33.3% |
| sink_frontier        | 9       | 3         |    33.3% |
| source_frontier      | 9       | 3         |    33.3% |

### MONGO_GEN

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 3         |    33.3% |
| all_small            | 9       | 3         |    33.3% |
| frugal_cascade       | 9       | 3         |    33.3% |
| par                  | 14      | 4         |    28.6% |
| par_lite             | 9       | 3         |    33.3% |
| sink_frontier        | 9       | 3         |    33.3% |
| source_frontier      | 8       | 3         |    37.5% |

### MULTITOOL_PLAN

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 4         |    44.4% |
| all_small            | 9       | 1         |    11.1% |
| frugal_cascade       | 9       | 3         |    33.3% |
| par                  | 14      | 3         |    21.4% |
| par_lite             | 9       | 1         |    11.1% |
| sink_frontier        | 9       | 1         |    11.1% |
| source_frontier      | 9       | 1         |    11.1% |

### POLICY_ACTION

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 3         |    33.3% |
| all_small            | 9       | 3         |    33.3% |
| frugal_cascade       | 9       | 3         |    33.3% |
| par                  | 13      | 4         |    30.8% |
| par_lite             | 9       | 3         |    33.3% |
| sink_frontier        | 9       | 3         |    33.3% |
| source_frontier      | 9       | 3         |    33.3% |

### SQL_COMPOSE

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 0         |     0.0% |
| all_small            | 9       | 0         |     0.0% |
| frugal_cascade       | 9       | 0         |     0.0% |
| par                  | 14      | 0         |     0.0% |
| par_lite             | 9       | 0         |     0.0% |
| sink_frontier        | 9       | 0         |     0.0% |
| source_frontier      | 9       | 0         |     0.0% |

### SQL_GEN

| Router | Tasks | Correct | Accuracy |
|--------|-------|---------|----------|
| all_frontier         | 9       | 3         |    33.3% |
| all_small            | 9       | 6         |    66.7% |
| frugal_cascade       | 9       | 6         |    66.7% |
| par                  | 14      | 8         |    57.1% |
| par_lite             | 9       | 6         |    66.7% |
| sink_frontier        | 9       | 3         |    33.3% |
| source_frontier      | 9       | 5         |    55.6% |
