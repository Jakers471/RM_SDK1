# Autonomous Agent Workflow Guide

## Overview

This document describes how to use the fully autonomous agent pipeline to go from feature idea to deployed PR without manual intervention. The system supports parallel execution, automatic branching, testing, and PR creation.

## Quick Start

### 1. Start with the Planner

```bash
# Initialize a new feature
RUN_ID="$(date +%Y%m%d-%H%M%S)-$(uuidgen | cut -c1-8)"
FEATURE_NAME="risk-monitoring"

# Launch the planner agent
echo "Starting autonomous pipeline for feature: ${FEATURE_NAME}"
echo "Run ID: ${RUN_ID}"

# Trigger rm-planner with the feature request
agent_prompt="
I need to implement a risk monitoring feature that:
- Tracks position limits in real-time
- Enforces max contract limits
- Sends notifications on breaches
- Resets counters at 17:00 CT daily
"
```

### 2. Pipeline Automatically Executes

Once the planner completes, the pipeline automatically:

1. **Coordinator** orchestrates the work
2. **SDK-Analyst** and **Doc-Reviewer** run in parallel
3. **Test-Orchestrator** creates failing tests
4. **Developer** implements the code
5. **Test-Orchestrator** verifies tests pass
6. **Doc-Reviewer** and **Integration-Validator** validate in parallel
7. **Auto-Commit** creates branch, commits, pushes, and creates PR

## Parallel Execution Model

### Safe Parallel Combinations

```yaml
# These agents can run simultaneously
parallel_groups:
  analysis:
    - rm-sdk-analyst      # Writes to docs/analysis/
    - doc-reviewer        # Read-only validation
    - integration-validator # Read-only validation

  debugging:
    - test-failure-debugger # Writes to docs/debug/
    - rm-sdk-analyst       # Different output directory
```

### Single Writer Enforcement

```yaml
# These agents must run sequentially
single_writers:
  - rm-developer         # Only writer to src/**
  - rm-test-orchestrator # Only writer to tests/**
  - auto-commit         # Only agent that commits
```

## Run Isolation

### Directory Structure

```
docs/
├── status/
│   ├── runs/
│   │   ├── 20251016-150000-abc123/
│   │   │   ├── planner/
│   │   │   ├── coordinator/
│   │   │   ├── sdk_analyst/
│   │   │   ├── test_results/
│   │   │   ├── commit_log.json
│   │   │   ├── branch_info.json
│   │   │   └── pr_body.md
│   │   └── 20251016-160000-def456/
│   └── latest/  # Atomic copy of most recent successful run
```

### Advisory Locks

```bash
# Acquire lock before writing shared files
acquire_lock() {
  local resource="$1"
  local lock_file=".locks/${resource}.lock"
  local timeout=60

  # Wait for lock to be available
  while [ -f "$lock_file" ] && [ $timeout -gt 0 ]; do
    sleep 1
    ((timeout--))
  done

  # Create lock with metadata
  echo "{
    \"run_id\": \"${RUN_ID}\",
    \"agent\": \"${AGENT_NAME}\",
    \"timestamp\": \"$(date -Iseconds)\",
    \"pid\": $$
  }" > "$lock_file"
}

# Release lock
release_lock() {
  rm -f ".locks/$1.lock"
}
```

## Triggering Workflows

### Manual Trigger

```bash
# Start the idea_to_feature workflow
./agents/trigger_workflow.sh idea_to_feature "${RUN_ID}" "${FEATURE_NAME}"
```

### Automatic Triggers

```bash
# Tests failed - triggers automatic triage
echo "${RUN_ID}" > .triggers/runs/${RUN_ID}/tests_failed

# Import mismatch detected
echo "${RUN_ID}" > .triggers/runs/${RUN_ID}/import_mismatch

# All tests green - triggers commit workflow
echo "${RUN_ID}" > .triggers/runs/${RUN_ID}/all_green
```

## Complete Example

### Feature Implementation Pipeline

```bash
#!/bin/bash
# autonomous_feature.sh

# Configuration
FEATURE_NAME="$1"
BASE_BRANCH="${2:-main}"
RUN_ID="$(date +%Y%m%d-%H%M%S)-$(uuidgen | cut -c1-8)"

# Initialize run directory
mkdir -p "docs/status/runs/${RUN_ID}"

# Step 1: Planning
echo "🎯 Starting planning phase..."
cat > "docs/status/runs/${RUN_ID}/feature_request.md" << EOF
Feature: ${FEATURE_NAME}
Base Branch: ${BASE_BRANCH}
Run ID: ${RUN_ID}
EOF

# Launch planner (this would be the actual agent invocation)
invoke_agent rm-planner \
  --run-id "${RUN_ID}" \
  --feature "${FEATURE_NAME}" \
  --output "docs/plans/runs/${RUN_ID}/"

# Step 2: Coordination
echo "📋 Coordinating implementation..."
invoke_agent rm-coordinator \
  --run-id "${RUN_ID}" \
  --input "docs/plans/runs/${RUN_ID}/"

# Step 3: Parallel Analysis
echo "🔍 Running parallel analysis..."
{
  invoke_agent rm-sdk-analyst \
    --run-id "${RUN_ID}" \
    --output "docs/status/runs/${RUN_ID}/sdk/" &

  invoke_agent doc-reviewer \
    --run-id "${RUN_ID}" \
    --output "docs/status/runs/${RUN_ID}/docs/" &

  wait
}

# Step 4: Test Creation
echo "🧪 Creating test suite..."
invoke_agent rm-test-orchestrator \
  --run-id "${RUN_ID}" \
  --mode create \
  --output "tests/runs/${RUN_ID}/"

# Step 5: Implementation (Single Writer)
echo "💻 Implementing feature..."
acquire_lock "src_writer"
invoke_agent rm-developer \
  --run-id "${RUN_ID}" \
  --input "tests/runs/${RUN_ID}/" \
  --patches "docs/status/runs/${RUN_ID}/patches/"
release_lock "src_writer"

# Step 6: Test Verification
echo "✅ Verifying tests..."
invoke_agent rm-test-orchestrator \
  --run-id "${RUN_ID}" \
  --mode verify \
  --output "docs/status/runs/${RUN_ID}/test_results/"

# Check if tests passed
if [ -f "docs/status/runs/${RUN_ID}/test_results/all_passing" ]; then
  echo "✨ All tests passing!"

  # Step 7: Final Validation (Parallel)
  echo "🔎 Final validation..."
  {
    invoke_agent doc-reviewer \
      --run-id "${RUN_ID}" \
      --mode final &

    invoke_agent integration-validator \
      --run-id "${RUN_ID}" &

    wait
  }

  # Step 8: Commit and Push
  echo "🚀 Creating PR..."
  invoke_agent auto-commit \
    --run-id "${RUN_ID}" \
    --feature "${FEATURE_NAME}" \
    --base-branch "${BASE_BRANCH}" \
    --create-pr true

  # Update latest pointer
  cp -r "docs/status/runs/${RUN_ID}/"* "docs/status/latest/"

  # Get PR URL
  PR_URL=$(cat "docs/status/runs/${RUN_ID}/pr_url.txt")
  echo "✅ PR created: ${PR_URL}"
else
  echo "❌ Tests failed - triggering debug workflow"
  echo "${RUN_ID}" > ".triggers/runs/${RUN_ID}/tests_failed"
fi
```

## Monitoring Progress

### Check Pipeline Status

```bash
# View current pipeline status
cat "docs/status/runs/${RUN_ID}/pipeline_status.json" | jq .

# Watch real-time progress
tail -f "docs/status/runs/${RUN_ID}/pipeline.log"

# Check which agents are running
ls -la .locks/
```

### View Agent Outputs

```bash
# See all artifacts for a run
tree "docs/status/runs/${RUN_ID}/"

# Check test results
cat "docs/status/runs/${RUN_ID}/test_results/summary.json"

# View PR details
cat "docs/status/runs/${RUN_ID}/branch_info.json"
```

## Error Recovery

### Retry Failed Step

```bash
# If an agent fails, retry with same run_id
invoke_agent ${FAILED_AGENT} \
  --run-id "${RUN_ID}" \
  --retry true
```

### Clean Up Stale Locks

```bash
# Remove locks older than 1 hour
find .locks -name "*.lock" -mmin +60 -delete
```

### Rollback Changes

```bash
# If pipeline needs to be aborted
git checkout "${BASE_BRANCH}"
git branch -D "feature/${FEATURE_NAME}-${RUN_ID}"
rm -rf "docs/status/runs/${RUN_ID}"
```

## Best Practices

1. **Always use run_id**: Every agent invocation should include a run_id for traceability
2. **Check locks**: Ensure advisory locks are acquired/released properly
3. **Atomic updates**: Only update `latest/` after successful completion
4. **Clean up**: Remove old run directories periodically
5. **Monitor**: Watch for stuck locks or failed agents

## Configuration

### Environment Variables

```bash
export AGENT_PARALLEL_MAX=4        # Max parallel agents
export AGENT_LOCK_TIMEOUT=60       # Lock timeout in seconds
export AGENT_RUN_RETENTION=7       # Days to keep run artifacts
export AGENT_AUTO_CLEANUP=true     # Auto-cleanup old runs
```

### Workflow Customization

Edit `agents/flow.yaml` to customize:
- Workflow steps
- Parallel groupings
- Trigger conditions
- Input/output paths

## Troubleshooting

### Common Issues

1. **Lock timeout**: Check for stuck agents holding locks
2. **Disk space**: Old run directories consuming space
3. **Git conflicts**: Multiple runs on same feature
4. **Test flakiness**: Retry with same run_id

### Debug Commands

```bash
# Show all active runs
ls -la docs/status/runs/

# Check lock status
for lock in .locks/*.lock; do
  echo "=== $lock ==="
  cat "$lock" | jq .
done

# Find stuck agents
ps aux | grep agent

# Clean up everything
./scripts/cleanup_runs.sh
```

## Summary

The autonomous workflow enables:
- 🚀 **Full automation** from idea to PR
- ⚡ **Parallel execution** where safe
- 🔒 **Single-writer enforcement** for src/
- 📦 **Run isolation** for parallel pipelines
- 🔄 **Automatic retry** on failures
- 📊 **Complete traceability** via run_id

Start with `invoke_agent rm-planner` and let the pipeline handle the rest!