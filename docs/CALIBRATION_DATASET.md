# Calibration dataset

`apps/api/app/calibration/document-classifier-v1.jsonl` is a versioned,
privacy-safe baseline for document-classifier evaluation. It contains only
synthetic Italian-language document text and no people, fiscal codes, addresses,
or real clinical records.

Each JSONL line has a stable `CAL-CLF-###` identifier, prompt and dataset
versions, a task, input text, expected `DocumentType`, source, and descriptive
tags. The loader rejects malformed or duplicate rows and requires coverage of
every supported `DocumentType`.

Run `evaluate-rizzo --minimum-accuracy 0.95 --output build/rizzo-report.json`
inside the API container when a local Rizzo Flow instance is enabled. It uses no
LM Studio fallback, reports exact classification accuracy by prompt/model/provider,
and exits with code `1` when the threshold is missed. The JSON report contains
only synthetic sample identifiers and categories, never input text. Candidate
retrieval, patient attribution, and link confirmation are deliberately outside
this dataset; precision for identity and event association remains the product's
primary safety metric.