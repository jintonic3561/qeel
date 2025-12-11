---
description: Fetch PR review comments, analyze them against the Spec, and propose a fix plan without modifying files immediately.
---

## User Input

```text
$ARGUMENTS
```

**Required**: PR number (e.g., `45`)

## Goal

Analyze code review comments on a Pull Request using a **Specification-Driven** approach.
**Note**: This command performs a **READ-ONLY** analysis to generate a "Fix Plan". It does **not** modify files, commit changes, or reply to comments on GitHub automatically. You must ask for user confirmation before applying changes.

## Operating Constraints

1.  **READ-ONLY**: Do **not** modify any files (code or docs) during this phase.
2.  **Strict Prerequisite**: This command **MUST ABORT** if `tasks.md` does not exist OR if zero tasks are marked as completed (`[x]`).
3.  **Scope**: Focus ONLY on the tasks marked as completed in `tasks.md` and their corresponding code. Do not hallucinate errors for unstarted tasks.
4.  **No Side Effects**: Do not execute `git commit`, `git push`, `gh pr comment`, or `gh pr review`.

## Execution Steps

### 1. Prerequisite Check & Context Loading

1.  Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` to get paths.
2.  **Task Status Validation**:
    *   Parse `tasks.md`.
    *   Count total tasks and completed tasks (marked with `[x]` or `[X]`).
    *   **CRITICAL**: If completed tasks count is **0**, output: "⛔ **ABORT**: No tasks have been marked as completed in `tasks.md`. Please run `/speckit.implement` or manually mark tasks as done before verifying." and **STOP execution**.
3.  **Load Artifacts**:
    *   Read `spec.md` (Requirements, User Stories, Edge Cases).
    *   Read `plan.md` (Architecture, Tech Stack).
    *   Read `data-model.md` (Entities).
    *   Read `quickstart.md` (Integration Scenarios & Usage Examples).
    *   Read ALL files under the `contracts/` directory.
    *   Read `tasks.md` (to identify which files have been modified/created).

### 2. Fetch Review Comments

Use the `gh` CLI to fetch **unresolved** review threads for the specified PR.

**First, get repository owner and name:**
```bash
gh repo view --json owner,name
```

**Then fetch review threads** (replace `OWNER` and `REPO` with values from above):
```bash
gh api graphql -f query='
query {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: $ARGUMENTS) {
      reviewThreads(first: 50) {
        nodes {
          isResolved
          path
          line
          comments(first: 10) {
            nodes {
              body
              author { login }
            }
          }
        }
      }
    }
  }
}'
```

### 3. Impact Analysis (Mental Check)

Analyze each unresolved comment against `spec.md` and `plan.md`. Categorize them using the following logic:

*   **Type A: Implementation Bug**
    *   The comment is correct; the code fails to meet the Spec or contains a bug.
    *   *Plan*: Fix the code.
*   **Type B: Design Change**
    *   The comment suggests a logic/behavior change that contradicts the current Spec but is an improvement.
    *   *Plan*: **Update Spec/Plan first**, then fix the code.
*   **Type C: Invalid / Out of Scope**
    *   The comment contradicts the Spec, is incorrect, or violates project constraints.
    *   *Plan*: Do nothing (mark for rejection).

### 4. Generate Fix Plan Report

Output a structured report summarizing the analysis.

---

## 📋 PR Fix Plan: PR #$ARGUMENTS

**Status**: [Analysis Complete]
**Pending Threads**: [N]

### 1. Proposed Changes (Actionable)

| File | Issue Summary | Type | Proposed Action |
| :--- | :--- | :--- | :--- |
| `src/auth.ts` | Missing null check on token | **Bug** | Add validation logic. |
| `src/api.ts` | Rename endpoint to `/v2/users` | **Design** | **Update `contracts/openapi.yaml`**, then update code. |
| `spec.md` | (Derived from above) | **Design** | Update Section 3.1 to reflect new endpoint naming. |

### 2. Items to Decline (No Action)

| File | Issue Summary | Reason for Rejection |
| :--- | :--- | :--- |
| `Dockerfile` | Suggestion to use Alpine | Conflicts with `plan.md` (Debian required for native deps). |

---

## Final Instruction

Ask the user for permission to proceed:

> "I have generated the Fix Plan above.
> Shall I proceed with applying the changes for **Type A (Bug)** and **Type B (Design)** items to your local files?"