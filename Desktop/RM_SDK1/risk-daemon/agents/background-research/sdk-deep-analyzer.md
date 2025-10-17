---
name: sdk-deep-analyzer
description: BACKGROUND AGENT - Deep analysis of project-x-py SDK for Phase 2 preparation. Runs in parallel with Phase 1 implementation. Creates detailed SDK capability map, identifies integration challenges, prepares for live connection.

<example>
Context: Phase 1 in progress, prepare for Phase 2.
user: "While we're implementing Phase 1, can you deeply analyze the SDK for Phase 2?"
assistant: "I'll use the sdk-deep-analyzer agent to prepare SDK integration details."
<task>sdk-deep-analyzer</task>
</example>
model: opus
color: yellow
---

## Mission
Deep dive into project-x-py SDK to prepare for Phase 2 live integration. Work in PARALLEL with Phase 1 implementation.

## Inputs
- ../project-x-py/src/** (SDK source code)
- ../project-x-py/docs/api/** (SDK documentation)
- docs/audits/04_SDK_Integration_Analysis.md (previous analysis)

## Outputs
- docs/research/sdk_capability_deep_dive.md
  - Every SDK method with signature, behavior, edge cases
  - Event types and data structures (exact field names)
  - Authentication flow (step-by-step with code examples)
  - Error handling patterns (what exceptions to expect)
  - Rate limits and throttling (exact numbers)
  - WebSocket vs REST endpoints
  - Reconnection behavior (what happens on disconnect)

- docs/research/sdk_integration_challenges.md
  - Known SDK bugs or quirks
  - Workarounds for limitations
  - Performance characteristics
  - Breaking changes between versions

- docs/research/live_testing_requirements.md
  - What test account credentials needed
  - How to set up test environment
  - Test data requirements
  - Cleanup procedures

## Key Focus Areas
1. **Event System**: Exact event type strings, field structures
2. **Position Data**: Exact field names (size vs quantity, etc.)
3. **P&L Tracking**: Does SDK track realized P&L? How to calculate unrealized?
4. **Authentication**: Step-by-step flow with error handling
5. **Reconnection**: What state is lost? Must we resubscribe?

## Deliverable
Production-ready SDK integration guide for Phase 2 implementation.
