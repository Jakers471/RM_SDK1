#!/bin/bash

# invoke_planner.sh - Start the autonomous pipeline with the rm-planner agent

# Configuration
FEATURE_NAME="${1:-unnamed-feature}"
FEATURE_DESC="${2:-No description provided}"
BASE_BRANCH="${3:-main}"

# Generate run ID
RUN_ID="$(date +%Y%m%d-%H%M%S)-$(openssl rand -hex 4 2>/dev/null || echo "$(date +%s)")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create run directory
RUN_DIR="risk-daemon/docs/status/runs/${RUN_ID}"
mkdir -p "${RUN_DIR}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🚀 Starting Autonomous Pipeline${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Feature:${NC} ${FEATURE_NAME}"
echo -e "${YELLOW}Run ID:${NC} ${RUN_ID}"
echo -e "${YELLOW}Base Branch:${NC} ${BASE_BRANCH}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Create feature request file for planner
cat > "${RUN_DIR}/feature_request.md" << EOF
# Feature Request

**Feature Name**: ${FEATURE_NAME}
**Run ID**: ${RUN_ID}
**Base Branch**: ${BASE_BRANCH}
**Timestamp**: $(date -Iseconds)

## Description
${FEATURE_DESC}

## Pipeline Configuration
- Mode: Autonomous
- Parallel Execution: Enabled
- Auto-Commit: Enabled
- PR Creation: Enabled

## Agent Chain
1. rm-planner (this agent)
2. rm-coordinator
3. [rm-sdk-analyst || doc-reviewer] (parallel)
4. rm-test-orchestrator
5. rm-developer
6. rm-test-orchestrator (verify)
7. [doc-reviewer || integration-validator] (parallel)
8. auto-commit (branch, push, PR)
EOF

# Create the planner prompt
cat > "${RUN_DIR}/planner_prompt.md" << EOF
You are being invoked as part of an autonomous pipeline.

Run ID: ${RUN_ID}
Feature: ${FEATURE_NAME}

Please design and document the following feature:
${FEATURE_DESC}

Requirements:
1. Create comprehensive architecture documentation in docs/architecture/runs/${RUN_ID}/
2. Define clear module boundaries and interfaces
3. Specify all integration points
4. Document the data flow
5. Create a handoff document for the SDK analyst

After you complete the planning, the pipeline will automatically:
- Coordinate implementation tasks
- Analyze SDK capabilities
- Create tests
- Implement the feature
- Verify everything works
- Create a PR

Please ensure your documentation is detailed enough for the downstream agents to work autonomously.

Output all documentation to: docs/architecture/runs/${RUN_ID}/
EOF

echo -e "\n${GREEN}📝 Step 1: Planning Phase${NC}"
echo "----------------------------------------"
echo "The rm-planner agent will now:"
echo "  • Design the architecture"
echo "  • Document module structure"
echo "  • Define interfaces"
echo "  • Create implementation roadmap"
echo ""
echo -e "${YELLOW}Planner Input:${NC}"
cat "${RUN_DIR}/planner_prompt.md"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Here you would invoke the actual agent
# For now, we'll show how it would be called
echo -e "\n${YELLOW}To invoke the planner in Claude:${NC}"
echo "----------------------------------------"
echo "Use the Task tool with:"
echo "  subagent_type: 'rm-planner'"
echo "  prompt: <contents of ${RUN_DIR}/planner_prompt.md>"
echo ""

echo -e "${GREEN}Alternative: Direct Claude Message:${NC}"
echo "----------------------------------------"
echo "Copy and paste this message to Claude:"
echo ""
echo "\"Please use the rm-planner agent to design the '${FEATURE_NAME}' feature."
echo "Run ID: ${RUN_ID}"
echo "Description: ${FEATURE_DESC}\""
echo ""

# Create status file
cat > "${RUN_DIR}/pipeline_status.json" << EOF
{
  "run_id": "${RUN_ID}",
  "feature": "${FEATURE_NAME}",
  "status": "planning",
  "current_agent": "rm-planner",
  "started": "$(date -Iseconds)",
  "steps": [
    {
      "agent": "rm-planner",
      "status": "in_progress",
      "started": "$(date -Iseconds)"
    }
  ]
}
EOF

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Pipeline initialized successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Run artifacts will be saved to:"
echo "  ${RUN_DIR}/"
echo ""
echo "Monitor progress with:"
echo "  cat ${RUN_DIR}/pipeline_status.json | python -m json.tool"
echo ""
echo "Once the planner completes, the next agent (rm-coordinator) will"
echo "automatically be triggered to continue the pipeline."
echo ""