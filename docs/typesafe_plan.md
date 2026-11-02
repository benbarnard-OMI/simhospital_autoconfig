# TypeSafe AI Integration Plan for simhospital_autoconfig

## Objective
Use TypeSafe's Jev model as a structured uncertainty classifier, not as a replacement for deterministic rules. Follow the Jev Evaluation SOP:
1. Run deterministic checks first.
2. Only escalate to Jev when the deterministic system cannot confidently answer.
3. Ask narrow, typed questions with clear success criteria.
4. Log every Jev interaction for dataset collection.
5. Continuously replace Jev questions with deterministic rules or local classifiers.

## Strategy

### Layer 1: Deterministic Rules (local, no Jev)
Expressed as lightweight Python functions in `simhospital_autoconfig/deterministic_checks.py`. These catch the obvious issues:
- No `${ORGANIZATION_NAME}` or `${ORGANIZATION_ID}` placeholders remain
- `locations.yml` contains an `ED` location
- All `floor` values are numeric
- `ethnicity.csv` contains exactly one `nil,nil` sentinel
- All doctor entries have non-empty required fields
- `hl7.yml` contains required top-level sections
- `hl7.yml` placeholders are resolved
- Country code is a valid 3-letter ISO code
- Doctor specialties are in the allowed set

### Layer 2: Local Classifiers (historical data, no Jev)
Simple heuristics derived from deterministic check results:
- `get_deterministic_confidence()` returns 0.0-1.0 based on pass rate
- If confidence >= 0.9, most config issues are already caught

### Layer 3: Jev (narrow, typed questions)
Only ask Jev when deterministic confidence is high but we want uncertainty classification:
- Narrow Noul questions: "Does this specific field match the expected pattern?"
- Narrow Score questions: "How complete is this specific section on a 0-2 rubric?"
- Narrow Choice questions: "What is the most likely issue type: none, schema, missing, data?"

### Layer 4: Routing & Policy (deterministic)
Security policy and routing decisions are never delegated to Jev.

## Execution Criteria
- Deterministic checks must pass before any Jev call
- Jev Noul threshold: < 0.3 probability of issue (narrow questions only)
- Jev Score threshold: >= 1.5 (specific sections only)
- Every Jev interaction is logged with request metadata, policy decision, latency, and outcome

## Replacement Strategy
For every question currently answered by Jev, periodically ask:
1. Can this be expressed as a deterministic rule?
2. Can it be predicted from historical data?
3. Can a small local classifier replace it?

Desired trajectory: Deterministic rule → Historical lookup → Lightweight local model → Jev (only for novel or ambiguous cases).

## Success Criteria
- Jev usage decreases over time while overall routing quality improves.
- Security policy remains deterministic.
- Deterministic confidence score >= 0.9 for all generated configs.
- Jev is reserved for genuinely new or ambiguous situations.

## Deliverables
- `simhospital_autoconfig/deterministic_checks.py` — local validation rules
- `tests/test_typesafe_validation.py` — automated audit with deterministic pre-check + narrow Jev questions
- `docs/typesafe_plan.md` — this document
