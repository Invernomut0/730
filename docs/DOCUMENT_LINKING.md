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

## Relations

The current automatic relation types are `LLM_PROPOSED` and `USER_CONFIRMED`.
Other graph edges remain available for downstream insurance, reimbursement, and
tax workflows.
