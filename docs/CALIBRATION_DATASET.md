# Calibration dataset

`apps/api/app/calibration/document-classifier-v1.jsonl` is a versioned,
privacy-safe baseline for document-classifier evaluation. It contains only
synthetic Italian-language document text and no people, fiscal codes, addresses,
or real clinical records.

Each JSONL line has a stable `CAL-CLF-###` identifier, prompt and dataset
versions, a task, input text, expected `DocumentType`, source, and descriptive
tags. The loader rejects malformed or duplicate rows and requires coverage of
every supported `DocumentType`.

The future `evaluate-rizzo` command must evaluate this dataset offline, report
classification accuracy by prompt/model/provider, and never include input text
in output artifacts or logs. Candidate retrieval, patient attribution, and link
confirmation are deliberately outside this dataset; precision for identity and
event association remains the product's primary safety metric.