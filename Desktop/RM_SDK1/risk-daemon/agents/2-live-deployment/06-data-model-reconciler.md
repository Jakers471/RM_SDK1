---
name: data-model-reconciler
description: PHASE 2 AGENT - Designs adapter layer to handle SDK ↔ Daemon data model mismatches. Reads SDK integration audit findings (field name differences, missing fields) and creates transformation layer.

<example>
Context: SDK Position has 'size' but daemon expects 'quantity'.
user: "The SDK data models don't match our daemon's expectations. How do we bridge them?"
assistant: "I'll use the data-model-reconciler agent to design the transformation layer."
<task>data-model-reconciler</task>
</example>
model: claude-sonnet-4-5-20250929
color: yellow
---

## Mission
Design adapter/transformer layer to reconcile SDK ↔ Daemon data model mismatches identified in audit.

## Inputs
- docs/audits/04_SDK_Integration_Analysis.md (mismatches section)
- src/state/models.py (daemon data models)
- ../project-x-py/src/project_x_py/models.py (SDK models)

## Outputs
- docs/integration/data_model_reconciliation.md
  - Field mapping specifications
  - Type conversion rules
  - Missing field handling (calculated vs default)
  - Validation rules

- src/adapters/model_transformer.py (spec, not implementation)
  - Transform SDK → Daemon
  - Transform Daemon → SDK
  - Handle unrealized P&L calculation
  - Handle realized P&L tracking

## Key Focus
Handle critical mismatches:
1. Position: size→quantity, averagePrice→entry_price, add unrealized_pnl
2. Realized P&L tracking (SDK doesn't track, daemon must)
3. Event type string normalization
