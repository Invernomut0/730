# Test Strategy

## Unit
Hashing, MIME validation, filename normalization, fiscal-code normalization, date/amount/AIC parsing, rule engine, link scoring and tax/reimbursement arithmetic.

## Integration scenarios
1. prescription + invoice -> one MedicalEvent;
2. prescription + report + multiple invoices -> one event;
3. one pharmacy receipt with drugs for two people -> two line allocations;
4. receipt CF differs from clinical patient -> clinical match plus fiscal review;
5. physiotherapy prescription + ten invoices -> one event;
6. private visit without traceable payment evidence -> tax warning;
7. explicit different patient -> no auto-link.

## E2E
Upload -> process -> graph -> insurance evaluation -> user correction -> export.

## AI metrics
Document classification accuracy, field extraction, patient attribution precision, AIC accuracy, medicine/prescription matching precision, event clustering precision, coverage classification and review rate.

Precision is primary for patient/event association.
