# Document Linking and Medical Event Clustering

## Goal

The configured primary local LLM decides whether each prescription–invoice pair
belongs to the same concrete clinical episode. It sees the complete structured
extractions, including services, tests, drugs, providers, dates, and patient
evidence. Patient identity is used only to keep retrieval private and bounded;
it is not a relationship decision rule.

## Model decisions

The relation model returns exactly one of:

- `RELATED`: create a `PROPOSED` event for operator review;
- `NOT_RELATED`: do not create a relationship;
- `UNCERTAIN`: do not create a relationship until richer evidence is available.

There are no lexical weights, date windows, thresholds, or deterministic
clinical-match scores. The model is specifically instructed that shared dates,
generic labels, a provider, or a patient alone never justify a link.

## Operator learning

An approval stores `APPROVED` feedback and is recreated as `USER_CONFIRMED` on
later rebuilds. A rejection stores `REJECTED` feedback and suppresses that exact
pair permanently. Recent same-patient decisions and rejection reasons are fed
back to the local relation model as private few-shot context for later pairs.
Bulk rejections imported from the retired rule engine are marked as legacy: they
remain contextual evidence but are reassessed by the model rather than acting as
permanent vetoes. Eligible pairs are evaluated in one structured LLM batch per
source document.

## Two-stage local routing

The configured small local model first receives each patient's complete
prescription and invoice JSON inventory once and returns only `RELATED` or
`UNCERTAIN` pairs. Clear positive decisions become reviewable
`SMALL_LLM_PROPOSED` events; they never auto-confirm. Only `UNCERTAIN` pairs are
escalated to the primary large model, which receives concise clinical fields
rather than repeated raw extraction JSON.

## Relations

The current automatic relation types are `LLM_PROPOSED` and `USER_CONFIRMED`.
Other graph edges remain available for downstream insurance, reimbursement, and
tax workflows.
