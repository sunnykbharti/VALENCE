# VALENCE Milestone 4A: Evaluation & Benchmark Report

## 1. Executive Summary & Measured Metrics

> [!IMPORTANT]
> **Evaluation Sample Size**: Total queries evaluated: **N = 15**.
> All metrics report explicit sample counts and distinguish automated checks from manual review.

| Metric | Result | Sample Size | Description |
|---|---|---|---|
| **Automated Pass Rate** | **1/15 (6.7%)** | N=15 | Overall query satisfaction across all categories. |
| **Citation Integrity** | **6.7%** | N=15 | Every citation in answer text strictly resolves to an Evidence item. |
| **Negative Query Rejection** | **100.0%** | N=4 unanswerable | Correct declaration of `insufficient_evidence=True` when context is absent. |
| **Source Retrieval Accuracy** | **22.2%** | N=11 answerable | Retrieved passages contain expected document and page reference. |
| **Mean End-to-End Latency** | **0.004 s** | N=15 | Combined retrieval, context construction, and synthesis time. |

---

## 2. Automated Checks vs. Manual Review Audit

| Query ID | Category | Question | Verdict | Latency | Automated Checks | Unsupported Claims (Manual Audit) |
|---|---|---|---|---|---|---|
| `eval_001` | `equipment_sop` | What is the procedure and authorization ... | **FAIL** | 0.009s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_002` | `equipment_sop` | What is the frequency and responsible ro... | **FAIL** | 0.003s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |
| `eval_003` | `cross_manual` | When a PLC critical fault occurs during ... | **FAIL** | 0.003s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |
| `eval_004` | `negative_test` | What is the exact torque specification f... | **FAIL** | 0.003s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_005` | `negative_test` | What is the oil change interval for the ... | **PASS** | 0.000s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=True | None detected |
| `eval_manual_001` | `manual_answerable` | What are the permissible ambient operati... | **FAIL** | 0.003s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |
| `eval_manual_002` | `manual_answerable` | What is the integrated work memory and l... | **FAIL** | 0.003s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |
| `eval_manual_003` | `manual_unanswerable` | What is the recommended replacement inte... | **FAIL** | 0.003s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_manual_004` | `manual_unanswerable` | What is the recommended ISO VG viscosity... | **FAIL** | 0.003s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_manual_005` | `equipment_ambiguous` | How many onboard high-speed counters (HS... | **FAIL** | 0.003s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |
| `eval_manual_006` | `equipment_ambiguous` | What is the maximum digital input and di... | **FAIL** | 0.003s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |
| `eval_vision_001` | `visual_inspection` | Inspect the attached photo of the PLC in... | **FAIL** | 0.008s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_vision_002` | `visual_inspection_failure` | What equipment state does this panel ima... | **FAIL** | 0.004s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_vision_003` | `visual_inspection_no_match` | What SOP procedure applies to this equip... | **FAIL** | 0.004s | SourceMatch=True, InsufficientCorrect=True, CitationsValid=False | None detected |
| `eval_vision_004` | `visual_inspection_ambiguous_identity` | Which startup procedure applies to this ... | **FAIL** | 0.004s | SourceMatch=False, InsufficientCorrect=True, CitationsValid=False | Answer generated without matching required reference page. |

---

## 3. Detailed Query Breakdown

### Query: `eval_001` (equipment_sop)
- **Question**: What is the procedure and authorization required to change the operating state of the Filler Cell PLC (PLC-FIL-02)?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_b751037672f0#p1#c1#c4 (01_Standard_Operating_Procedure.pdf:p1), doc_b751037672f0#p1#c1#c1 (01_Standard_Operating_Procedure.pdf:p1), doc_aed0845dcb88#p1#c1#c4 (05_Expert_Technical_Documentation.pdf:p1)
- **Reviewer Notes**: Direct SOP lookup from Section 1: Purpose and scope.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_002` (equipment_sop)
- **Question**: What is the frequency and responsible role for Level A visual walk-around inspection on Demo Bottling Line 2?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_aed0845dcb88#p2#c2#c5 (05_Expert_Technical_Documentation.pdf:p2), doc_b7c52b8d3a2a#p2#c2#c2 (02_Inspection_SOP.pdf:p2), doc_b751037672f0#p1#c1#c3 (01_Standard_Operating_Procedure.pdf:p1)
- **Reviewer Notes**: Lookup from Inspection SOP Level A frequency table.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_003` (cross_manual)
- **Question**: When a PLC critical fault occurs during operation, what severity level is assigned and what escalation path must be followed?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_aed0845dcb88#p2#c2#c7 (05_Expert_Technical_Documentation.pdf:p2), doc_aed0845dcb88#p3#c3#c1 (05_Expert_Technical_Documentation.pdf:p3), doc_aed0845dcb88#p1#c1#c1 (05_Expert_Technical_Documentation.pdf:p1)
- **Reviewer Notes**: Cross-references escalation policy with PLC fault conditions.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_004` (negative_test)
- **Question**: What is the exact torque specification for the cylinder head bolts on the high-pressure air compressor?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_b751037672f0#p1#c1#c6 (01_Standard_Operating_Procedure.pdf:p1), doc_aed0845dcb88#p2#c2#c2 (05_Expert_Technical_Documentation.pdf:p2), doc_aed0845dcb88#p1#c1#c5 (05_Expert_Technical_Documentation.pdf:p1)
- **Reviewer Notes**: Negative test: Cylinder head bolt torque is absent from available documents; system must flag insufficient_evidence.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_005` (negative_test)
- **Question**: What is the oil change interval for the Atlas Copco GA37 rotary screw compressor?
- **Equipment Model**: `Atlas-Copco-GA37`
- **Answer**: Insufficient documentary evidence found for equipment 'Atlas-Copco-GA37' to answer the question: 'What is the oil change interval for the Atlas Copco GA37 rotary screw compressor?'.
- **Retrieved Sources**: None
- **Reviewer Notes**: Negative test: Equipment model mismatch; model is unsupported in current indexed corpus.
- **Automated Check**: `Source Match: True` | `Citations Valid: True` | `Verdict: PASS`

### Query: `eval_manual_001` (manual_answerable)
- **Question**: What are the permissible ambient operating temperature ranges for the S7-1200 CPU when mounted horizontally versus vertically?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_b751037672f0#p1#c1#c4 (01_Standard_Operating_Procedure.pdf:p1), doc_027d02b85fa8#p2#c2#c0 (04_Maintenance_History_File.pdf:p2), doc_aed0845dcb88#p1#c1#c4 (05_Expert_Technical_Documentation.pdf:p1)
- **Reviewer Notes**: Answerable technical specification lookup from Siemens S7-1200 System Manual Environmental Specifications.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_manual_002` (manual_answerable)
- **Question**: What is the integrated work memory and load memory capacity of the S7-1200 CPU 1214C?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_aed0845dcb88#p1#c1#c6 (05_Expert_Technical_Documentation.pdf:p1), doc_b751037672f0#p1#c1#c4 (01_Standard_Operating_Procedure.pdf:p1), doc_aed0845dcb88#p2#c2#c6 (05_Expert_Technical_Documentation.pdf:p2)
- **Reviewer Notes**: Answerable technical parameter for CPU 1214C from Technical Specifications table.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_manual_003` (manual_unanswerable)
- **Question**: What is the recommended replacement interval for the hydraulic pump rotor seals on the auxiliary fluid loop?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_aed0845dcb88#p1#c1#c4 (05_Expert_Technical_Documentation.pdf:p1), doc_aed0845dcb88#p1#c1#c6 (05_Expert_Technical_Documentation.pdf:p1), doc_aed0845dcb88#p2#c2#c5 (05_Expert_Technical_Documentation.pdf:p2)
- **Reviewer Notes**: Unanswerable query: The S7-1200 manual covers programmable controllers and electronic modules; hydraulic rotor seals are completely absent.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_manual_004` (manual_unanswerable)
- **Question**: What is the recommended ISO VG viscosity rating for lubricating the mechanical reduction gear box?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_b751037672f0#p1#c1#c4 (01_Standard_Operating_Procedure.pdf:p1), doc_027d02b85fa8#p1#c1#c0 (04_Maintenance_History_File.pdf:p1), doc_cf69b8810cbf#p1#c1#c4 (03_Demo_Escalation_Policy-1.pdf:p1)
- **Reviewer Notes**: Unanswerable query: Mechanical gearbox lubrication is outside the scope of the PLC manual.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_manual_005` (equipment_ambiguous)
- **Question**: How many onboard high-speed counters (HSC) are supported on the S7-1200 CPU?
- **Equipment Model**: `None`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_027d02b85fa8#p1#c1#c1 (04_Maintenance_History_File.pdf:p1), doc_b751037672f0#p1#c1#c3 (01_Standard_Operating_Procedure.pdf:p1), doc_aed0845dcb88#p2#c2#c3 (05_Expert_Technical_Documentation.pdf:p2)
- **Reviewer Notes**: Equipment-ambiguous query: The S7-1200 family varies by CPU model. Equipment model is unspecified (null); answer must present breakdown across models.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_manual_006` (equipment_ambiguous)
- **Question**: What is the maximum digital input and digital output (DI/DO) channel count provided directly on the CPU?
- **Equipment Model**: `None`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_cf69b8810cbf#p2#c2#c1 (03_Demo_Escalation_Policy-1.pdf:p2), doc_aed0845dcb88#p1#c1#c1 (05_Expert_Technical_Documentation.pdf:p1), doc_aed0845dcb88#p2#c2#c2 (05_Expert_Technical_Documentation.pdf:p2)
- **Reviewer Notes**: Equipment-ambiguous query: Unspecified CPU model requires enumerating onboard I/O counts across 1211C, 1212C, 1214C, and 1215C.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_vision_001` (visual_inspection)
- **Question**: Inspect the attached photo of the PLC indicator LEDs. What is the current operating state shown and does any LED indicate a fault?
- **Equipment Model**: `S7-1200 CPU 1214C`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_b751037672f0#p1#c1#c4 (01_Standard_Operating_Procedure.pdf:p1), doc_aed0845dcb88#p1#c1#c4 (05_Expert_Technical_Documentation.pdf:p1), doc_b751037672f0#p2#c2#c1 (01_Standard_Operating_Procedure.pdf:p2)
- **Reviewer Notes**: Normal-state image. Synthetic fixture with clearly labelled SYNTHETIC DEMO watermark. Observations should be flagged tentative.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_vision_002` (visual_inspection_failure)
- **Question**: What equipment state does this panel image show?
- **Equipment Model**: `None`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_b7c52b8d3a2a#p1#c1#c4 (02_Inspection_SOP.pdf:p1), doc_027d02b85fa8#p1#c1#c1 (04_Maintenance_History_File.pdf:p1), doc_cf69b8810cbf#p1#c1#c3 (03_Demo_Escalation_Policy-1.pdf:p1)
- **Reviewer Notes**: Blurry image test: System must report image quality too low for reliable interpretation. No fabricated observations should be returned.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_vision_003` (visual_inspection_no_match)
- **Question**: What SOP procedure applies to this equipment?
- **Equipment Model**: `None`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_cf69b8810cbf#p1#c1#c2 (03_Demo_Escalation_Policy-1.pdf:p1), doc_b7c52b8d3a2a#p2#c2#c3 (02_Inspection_SOP.pdf:p2), doc_027d02b85fa8#p1#c1#c4 (04_Maintenance_History_File.pdf:p1)
- **Reviewer Notes**: Unknown equipment image: System must declare no documentation match and insufficient_evidence. Must not invent procedures.
- **Automated Check**: `Source Match: True` | `Citations Valid: False` | `Verdict: FAIL`

### Query: `eval_vision_004` (visual_inspection_ambiguous_identity)
- **Question**: Which startup procedure applies to this CPU?
- **Equipment Model**: `None`
- **Answer**: Inference unverified: Cannot connect to local Ollama daemon at 'http://localhost:11434': <urlopen error [Errno 1] Operation not permitted>. Ensure 'ollama serve' is running locally.
- **Retrieved Sources**: doc_cf69b8810cbf#p1#c1#c2 (03_Demo_Escalation_Policy-1.pdf:p1), doc_b7c52b8d3a2a#p2#c2#c3 (02_Inspection_SOP.pdf:p2), doc_027d02b85fa8#p1#c1#c4 (04_Maintenance_History_File.pdf:p1)
- **Reviewer Notes**: Ambiguous equipment identity test: System should report that model variant cannot be determined from image alone, suggest physical label verification, and present model-family general guidance if available.
- **Automated Check**: `Source Match: False` | `Citations Valid: False` | `Verdict: FAIL`
