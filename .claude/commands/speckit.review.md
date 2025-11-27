---
description: Perform a user-context-scoped review and, when valid, APPLY the requested changes across all relevant FEATURE_DIR files, then report a concise, easy-to-scan summary of edits and outcomes.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).  
Treat `$ARGUMENTS` as **the latest user prompt (context)** you must review against artifacts.

## Goal

Evaluate **only the issues, change requests, or questions explicitly or implicitly contained in the latest user prompt** and:

1. **Apply changes as-is** when each user point is valid and consistent with the current design and constitution.
2. When a user point is not valid, explain **why**, and propose a **safe alternative** aligned to the design and constitution.
3. Ensure **complete impact discovery** by scanning all related locations under `FEATURE_DIR/` before applying any edits.
4. Output a **concise report** that is easy to scan, focusing on decisions and deltas.

This command runs after `/speckit.tasks` has produced a complete `tasks.md`.

## Operating Constraints

**CHANGE-ALLOWED, CONTEXT-SCOPED**:
- You MAY modify files under `FEATURE_DIR/` **only to implement changes that are authorized by this command**.
- You MUST NOT edit anything unrelated to the latest user prompt’s User Point List (UPL).
- If no user points are valid, do not modify files.

**Mandatory References**:  
You MUST always reference:
- `spec.md`
- `plan.md`
- `tasks.md`
- `.specify/memory/constitution.md`

You MAY reference other files under `FEATURE_DIR/` only when relevant to evaluating or applying a UP.

**Constitution Authority**:  
The constitution is **non-negotiable**.  
Any user request conflicting with a MUST principle is **automatically rejected (CRITICAL)** and must NOT be applied.

## Execution Steps

### 1. Initialize Context

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` once from repo root and parse JSON for FEATURE_DIR and AVAILABLE_DOCS. Derive paths:

- SPEC = FEATURE_DIR/spec.md
- PLAN = FEATURE_DIR/plan.md
- TASKS = FEATURE_DIR/tasks.md
- CONSTITUTION = .specify/memory/constitution.md

Abort with an error if any required file is missing (instruct the user to run missing prerequisite command).

### 2. Extract “User Points” From Latest Prompt

From `$ARGUMENTS`, construct a **User Point List (UPL)**.  
Each point must be atomic and testable.

Rules:
- Preserve user intent; do not broaden scope.
- If the latest prompt is empty, output “No user points to review.” and stop.

### 3. Load Required Artifacts + Optional Supporting Files

Load minimal necessary context from the mandatory four artifacts.  
Additionally, load **other FEATURE_DIR files** only if they define, constrain, or reference concepts implicated by a UP.

### 4. Discover All Related Locations Under FEATURE_DIR/ (Pre-Edit Scan)

Before judging or editing a UP, you MUST perform a **targeted scan over `FEATURE_DIR/`**:

- Search for key terms, entities, IDs, filenames, components, and synonyms implied by the UP.
- Include spec/plan/tasks and any other FEATURE_DIR files referencing the same concept.
- Produce a **Related Locations List (RLL)** per UP.

No edit may occur unless its target location appears in that UP’s RLL.

### 5. Evaluate Each User Point

For every UP:

#### A. Evidence Check
Using RLL, locate supporting or conflicting text.

#### B. Judgment
Classify into:

- **AUTHORIZE_AND_APPLY**:  
  - Consistent with constitution and current design  
  - Improves clarity/correctness/coverage  
  - No conflicts introduced  
  - **Result:** apply user request as-is across all RLL locations.

- **REJECT**:  
  - Constitution MUST conflict  
  - Breaks established architecture/constraints without rationale  
  - Introduces ambiguity/regression/untestable requirement  
  - **Result:** do NOT edit; propose alternative.

- **AUTHORIZE_WITH_MODS_AND_APPLY**:  
  - Intent valid but concrete change suboptimal  
  - **Result:** apply corrected edit across all RLL locations.

#### C. Edit Plan (for AUTHORIZE*_AND_APPLY)
For each RLL location, specify the exact change to apply, ensuring:
- Terminology stays consistent across files
- Requirements ↔ plan ↔ tasks references remain aligned
- No new scope beyond the UP is introduced

### 6. Apply Edits

Apply the Edit Plan **only to RLL locations**.  
Edits must be minimal, mechanical, and consistent with the authorized intent.

### 7. Produce Concise Review + Change Report

Output Markdown:

## User-Context Review & Change Report

### Decisions per User Point
For each UP, output a short bullet:

- **UP1 — AUTHORIZE_AND_APPLY**  
  - Why (1–2 lines)  
  - Edited locations: `spec.md`, `plan.md`, `tasks.md`, `FEATURE_DIR/…`  
  - Delta summary: “X → Y”, “Add criterion C”, etc.

- **UP2 — REJECT**  
  - Why (1–2 lines)  
  - Alternative (1–2 lines)

Rules:
- Keep each UP block within ~8 lines.
- Do not include raw text dumps.
- Prefer concrete deltas over narrative.

### Applied Changes Summary
- List only AUTHORIZE*_AND_APPLY outcomes.
- Group by concept if multiple files changed.
- Each bullet should fit on 1–3 lines.

### Post-Change Sanity Check (Context-Only)
- 3–6 bullets max confirming: constitution alignment, cross-artifact consistency, no scope creep.

### Next Actions
- 2–5 bullets max depending on presence of rejections.

## Operating Principles

- **Scope fidelity**: Only latest prompt’s UPL can trigger edits.
- **Full-impact discovery**: Always scan FEATURE_DIR and build RLL before edits.
- **Constitution-first**: MUST conflicts are never applied.
- **High precision over recall**: Do not expand beyond user intent.
- **Deterministic edits**: Same prompt + same files → same UP IDs, RLLs, and edits.
- **Conciseness as a feature**: Prefer crisp deltas to exhaustive enumeration.

## Context

$ARGUMENTS
