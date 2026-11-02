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

## Evaluation Question Schema (`benchmark_queries.json`)

Each test item conforms to the following template:

| Field | Type | Description |
|---|---|---|
| `query_id` | `string` | Unique identifier for the test query (e.g. `eval_001`). |
| `category` | `string` | Category (`equipment_sop`, `cross_manual`, `negative_test`, `visual_inspection`). |
| `equipment_model` | `string` or `null` | Target equipment model identifier, or `null` if unspecified. |
| `question` | `string` | User query submitted to the system. |
| `expected_document` | `string` or `null` | Expected source manual filename, or `null` if unanswerable. |
| `expected_page` | `integer` or `null` | 1-based original source page position, or `null` if unanswerable. |
| `expected_answer_elements`| `list[string]` | Essential factual terms, numbers, or phrasing required in the answer. |
| `is_unanswerable` | `boolean` | `true` if documentary support is lacking and `insufficient_evidence` must be asserted. |
| `notes` | `string` | Evaluation notes and verification rationale. |


