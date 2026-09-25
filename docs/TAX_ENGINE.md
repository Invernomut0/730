# Tax Engine

Tax rules are independent from insurance rules and versioned by tax year.

## Inputs
Taxpayer/dependent relationship, gross expense, expense type, reimbursement allocation, payment traceability, provider/accreditation where relevant, official annual rule set and pre-filled data.

## Outputs
Eligibility state, gross/reimbursed/residual amounts, tax-eligible amount, deductible/franchise handling, theoretical deduction, missing evidence and provenance.

## Constraints
Do not blindly use `gross - reimbursement`. Tax treatment of reimbursements can depend on premiums/contributions and annual law.

## Sources
Production rules must cite official Agenzia delle Entrate material for the exact tax year, with source URL/document, retrieval date, hash and reviewer status.

## Pre-filled reconciliation
MVP imports downloaded/exported documents. No authenticated scraping and no SPID/CIE credentials.

Statuses: MATCHED, LOCAL_ONLY, PRECOMPILED_ONLY, AMOUNT_MISMATCH, REIMBURSEMENT_MISMATCH, REVIEW_REQUIRED.
