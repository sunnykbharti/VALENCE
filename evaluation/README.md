# Evaluation Suite (Member A)

This directory contains evaluation benchmarks, test questions, and ground-truth validation criteria for VALENCE.

## Structure
- `benchmark_queries.json`: Test questions covering:
  - Equipment-specific SOP lookups
  - Cross-manual troubleshooting
  - Negative tests (unsupported equipment, absent information)
  - Image-assisted defect/inspection queries
- `metrics.py`: Evaluator checking:
  - Factual grounding
  - Source citation validity
  - Appropriate declaration of `insufficient_evidence`
