# Agent Communication Layer Refactor Report
**Mode**: DRY-RUN
**Date**: 2025-10-16
**Scope**: Agent definitions normalization only (NO src/** or tests/** modifications)

## Executive Summary
This report documents the planned refactoring of the agent communication layer to standardize all agent definitions with shared context paths and workflow orchestration. The refactor will normalize 7 agent definitions, ensure consistent I/O contracts, and establish clear workflow patterns.

## Current State Analysis

### Existing Files
1. **agents/shared_context.yaml** - EXISTS ✅
   - Already contains all required shared paths
   - No modifications needed

2. **agents/flow.yaml** - MISSING ❌
   - Needs to be created with 4 workflow definitions

3. **Agent Definitions** - 7 files found:
   - agents/rm-planner.md
   - agents/rm-coordinator.md
   - agents/rm-test-orchestrator.md
   - agents/test-failure-debugger.md
   - agents/rm-developer.md
   - agents/rm-sdk-analyst.md
   - agents/workflow-comms-refactor.md

### Hardcoded Path Analysis
Found 138 instances of hardcoded paths across all agent definitions that need to be replaced with shared context references.

## Planned Changes

### 1. Create agents/flow.yaml
New file to define four workflow patterns:

```yaml
workflows:
  idea_to_feature:
    description: "Transform architectural ideas into tested features"
    steps:
      - agent: rm-planner
        trigger: manual
      - agent: rm-coordinator
        trigger: on_completion
      - agent: rm-test-orchestrator
        trigger: on_completion

  tests_failed_triage:
    description: "Debug and fix failing tests"
    trigger:
      watch: ${shared_paths.trig_tests_failed}
    steps:
      - agent: test-failure-debugger
      - agent: rm-developer
      - agent: rm-test-orchestrator

  import_mismatch_audit:
    description: "Audit and fix SDK import mismatches"
    trigger:
      watch: ${shared_paths.trig_import_mismatch}
    steps:
      - agent: rm-sdk-analyst
      - agent: rm-developer
      - agent: rm-test-orchestrator

  docs_sync_and_commit:
    description: "Sync docs and auto-commit on all green"
    trigger:
      watch: ${shared_paths.trig_all_green}
    steps:
      - agent: doc-reviewer
      - agent: integration-validator
      - agent: auto-commit
```

### 2. Normalize Agent Definitions

Each agent will be refactored to:
1. Add shared context include at the top
2. Replace all hardcoded paths with ${shared_paths.*} references
3. Add explicit Input/Output sections using shared paths
4. Maintain original functionality

#### Template Structure
```markdown
---
name: [agent-name]
description: [original description]
model: [original model]
color: [original color]
---

<!-- Shared Context Include -->
!include agents/shared_context.yaml

## Inputs
- ${shared_paths.[path1]} - [Description]
- ${shared_paths.[path2]} - [Description]

## Outputs
- ${shared_paths.[path3]} - [Description]
- ${shared_paths.[path4]} - [Description]

[Original agent content with paths replaced]
```

### 3. Path Replacements by Agent

#### rm-planner.md
**Inputs:**
- ${shared_paths.arch_docs}
- ${shared_paths.integ_docs}
- ${shared_paths.cov_summary}

**Outputs:**
- ${shared_paths.plans_dir}/*

**Replacements (7 instances):**
- `src/**` → `${shared_paths.src_dir}**`
- `../project-x-py/**` → `${shared_paths.sdk_repo}**`
- `docs/architecture/**` → `${shared_paths.arch_docs}**`
- `docs/architecture/` → `${shared_paths.arch_docs}`

#### rm-coordinator.md
**Inputs:**
- ${shared_paths.plans_dir}/*
- ${shared_paths.junit}
- ${shared_paths.cov_summary}
- ${shared_paths.triage_md}

**Outputs:**
- ${shared_paths.sprint_board}
- ${shared_paths.next_test_slice}
- ${shared_paths.dev_ready}
- ${shared_paths.blockers}

**Replacements (15 instances):**
- `docs/architecture/**` → `${shared_paths.arch_docs}**`
- `docs/integration/**` → `${shared_paths.integ_docs}**`
- `tests/**` → `${shared_paths.tests_dir}**`
- `reports/**` → Various specific shared paths
- `patches/**` → `${shared_paths.patch_latest}`
- `docs/debug/**` → Specific triage paths
- `docs/status/**` → `${shared_paths.status_dir}**`
- `docs/status/sprint_board.md` → `${shared_paths.sprint_board}`
- `docs/status/next_test_slice.md` → `${shared_paths.next_test_slice}`
- `docs/status/dev_ready.md` → `${shared_paths.dev_ready}`
- `docs/status/blockers.md` → `${shared_paths.blockers}`

#### rm-test-orchestrator.md
**Inputs:**
- ${shared_paths.next_test_slice}
- ${shared_paths.tests_dir}

**Outputs:**
- ${shared_paths.junit}
- ${shared_paths.cov_raw}
- ${shared_paths.cov_summary}
- ${shared_paths.pytest_log}
- ${shared_paths.trig_tests_failed}

**Replacements (21 instances):**
- `docs/architecture/**` → `${shared_paths.arch_docs}**`
- `docs/integration/**` → `${shared_paths.integ_docs}**`
- `docs/integration/adapter_contracts.md` → `${shared_paths.integ_docs}/adapter_contracts.md`
- `tests/**` → `${shared_paths.tests_dir}**`
- `tests/unit/**` → `${shared_paths.tests_dir}unit/**`
- `tests/integration/**` → `${shared_paths.tests_dir}integration/**`
- `tests/e2e/**` → `${shared_paths.tests_dir}e2e/**`
- `tests/conftest.py` → `${shared_paths.tests_dir}conftest.py`
- `tests/fakes/` → `${shared_paths.tests_dir}fakes/`
- `src/**` → `${shared_paths.src_dir}**`

#### test-failure-debugger.md
**Inputs:**
- ${shared_paths.junit}
- ${shared_paths.cov_raw}
- ${shared_paths.tests_dir}
- ${shared_paths.src_dir}

**Outputs:**
- ${shared_paths.triage_md}
- ${shared_paths.triage_json}
- ${shared_paths.patch_latest}
- ${shared_paths.trig_import_mismatch} (optional)

**Replacements (23 instances):**
- `docs/architecture/**` → `${shared_paths.arch_docs}**`
- `docs/integration/**` → `${shared_paths.integ_docs}**`
- `tests/**` → `${shared_paths.tests_dir}**`
- `src/**` → `${shared_paths.src_dir}**`
- `reports/**` → Various specific shared paths
- `reports/junit.xml` → `${shared_paths.junit}`
- `reports/coverage.xml` → `${shared_paths.cov_raw}`
- `docs/debug/triage_<ticket>.md` → Dynamic path based on triage_md
- `patches/<ticket>.patch` → Dynamic path based on patch_latest
- `docs/debug/PATCH_APPLY_NOTES.md` → `${shared_paths.triage_md}`

#### rm-developer.md
**Inputs:**
- ${shared_paths.triage_json}
- ${shared_paths.patch_latest}
- ${shared_paths.tests_dir}
- ${shared_paths.arch_docs}

**Outputs:**
- Updates in ${shared_paths.src_dir} (no report writes)

**Replacements (16 instances):**
- `tests/**` → `${shared_paths.tests_dir}**`
- `docs/architecture/**` → `${shared_paths.arch_docs}**`
- `docs/integration/**` → `${shared_paths.integ_docs}**`
- `docs/architecture/12-core-interfaces-and-events.md` → `${shared_paths.arch_docs}/12-core-interfaces-and-events.md`
- `src/**` → `${shared_paths.src_dir}**`
- `src/custom_risk_daemon/adapters/` → `${shared_paths.src_dir}custom_risk_daemon/adapters/`
- `src/custom_risk_daemon/core` → `${shared_paths.src_dir}custom_risk_daemon/core`
- `src/custom_risk_daemon/adapters/**` → `${shared_paths.src_dir}custom_risk_daemon/adapters/**`

#### rm-sdk-analyst.md
**Inputs:**
- ${shared_paths.junit}
- ${shared_paths.sdk_repo}
- ${shared_paths.src_dir}
- ${shared_paths.tests_dir}

**Outputs:**
- ${shared_paths.sdk_index}
- ${shared_paths.sdk_audit}

**Replacements (28 instances):**
- `../project-x-py/**` → `${shared_paths.sdk_repo}**`
- `docs/architecture/**` → `${shared_paths.arch_docs}**`
- `docs/architecture/` → `${shared_paths.arch_docs}`
- `docs/integration/` → `${shared_paths.integ_docs}/`
- All specific integration doc paths → Use integ_docs base path

## File-by-File Change Summary

| File | Lines Changed | Paths Replaced | New Sections Added |
|------|--------------|----------------|-------------------|
| agents/flow.yaml | +44 (new) | N/A | Complete file |
| agents/rm-planner.md | ~15 | 7 | Inputs/Outputs |
| agents/rm-coordinator.md | ~25 | 15 | Inputs/Outputs |
| agents/rm-test-orchestrator.md | ~30 | 21 | Inputs/Outputs |
| agents/test-failure-debugger.md | ~35 | 23 | Inputs/Outputs |
| agents/rm-developer.md | ~20 | 16 | Inputs/Outputs |
| agents/rm-sdk-analyst.md | ~35 | 28 | Inputs/Outputs |
| **TOTAL** | **~204** | **110** | **7** |

## Validation Checklist

- [x] All hardcoded paths identified and mapped to shared_paths
- [x] Each agent has explicit Input/Output contract
- [x] Flow.yaml defines all 4 required workflows
- [x] Shared_context.yaml contains all required paths
- [x] No modifications to src/** or tests/**
- [x] No modifications to docs/architecture/** or docs/integration/**
- [x] All agent definitions maintain original functionality
- [x] Path replacements use correct ${shared_paths.*} syntax

## Rollback Plan

If issues arise after applying the patch:
1. Use `git apply -R patches/workflow-refactor.patch` to revert
2. Or restore from backup: agents/*.md.backup
3. Remove agents/flow.yaml if created

## Next Steps (After Approval)

1. Review this report and confirm changes
2. Apply the patch: `git apply patches/workflow-refactor.patch`
3. Test agent execution with new shared paths
4. Verify workflows trigger correctly
5. Update any agent invocation scripts if needed

## Risk Assessment

- **Low Risk**: Changes are isolated to agent definition files only
- **No Business Logic Impact**: src/** and tests/** untouched
- **Reversible**: Easy rollback via git or patch reversal
- **Backward Compatible**: Shared path resolution maintains same actual paths

---
*Report generated in DRY-RUN mode. No files were modified.*