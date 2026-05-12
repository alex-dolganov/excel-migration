# Task Scenario Entry Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the first step of the wizard clearly answer “what exactly are we importing into tasks?” before the user gets to file preview and field mapping.

**Architecture:** Keep the existing backend entity types as-is and improve the entry UX around them. The first slice is frontend-focused: group task-related import types into one understandable scenario block, show explicit scenario cards and minimum requirements, and make the user’s choice obvious before upload/mapping starts.

**Tech Stack:** Nuxt, Vue, importer UI helpers, existing task entity types (`task`, `task_comment`, `task_checklist_item`, `task_attachment`)

---

## Chunk 1: Task Scenario Entry UX

### Task 1: Reshape the first step around task scenarios

**Files:**
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [x] **Step 1: Write the failing helper tests**

Cover:
- task-related import types are grouped as one “import into tasks” family
- helper returns clear scenario cards for:
  - tasks
  - task comments
  - task checklist items
  - task attachments
- each card exposes:
  - title
  - short description
  - minimum required fields
  - explanation of where the row goes

- [x] **Step 2: Run RED**

Run:
`node --test frontend/tests/importer-ui.test.mjs`

Expected:
- FAIL because current step 1 only exposes flat entity choices and generic guide text

- [x] **Step 3: Implement minimal helper layer**

Rules:
- do not invent new backend entity types
- reuse existing supported entity values
- keep CRM entities flat
- make task entities explicit and scenario-first

- [x] **Step 4: Update first-step UI**

Implement:
- visible grouped entry for task scenarios
- clearer card copy before file upload
- selected scenario summary in step 1

- [x] **Step 5: Run GREEN**

Run:
`node --test frontend/tests/importer-ui.test.mjs`

Expected:
- PASS

---

## Chunk 2: Scenario Continuity Through The Wizard

### Task 2: Keep the chosen task scenario obvious after step 1

**Files:**
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/tests/index-page-init.test.mjs`

- [x] **Step 1: Add a small continuity indicator**

Show:
- selected scenario label in the wizard header or context panel
- minimum import reminder for task scenarios

- [x] **Step 2: Verify it does not interfere with CRM flows**

Rules:
- leads/contacts/companies/deals must keep their current path
- task-specific reminders only appear for task-family scenarios

---

## Chunk 3: Verification And Context

### Task 3: Run regression and update project files

**Files:**
- Test: `frontend/tests/importer-ui.test.mjs`
- Test: `frontend/tests/index-page-init.test.mjs`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [x] **Step 1: Run frontend regression**

Run:
`node --test frontend/tests/importer-ui.test.mjs frontend/tests/index-page-init.test.mjs`

- [x] **Step 2: Try frontend build**

Run:
`node .\\node_modules\\nuxt\\bin\\nuxt.mjs build`

Expected:
- either PASS
- or same known local `lightningcss` environment failure, which must be recorded honestly

- [x] **Step 3: Update context**

Record:
- that task import is now scenario-first at step 1
- what still remains for deeper task-centric flows

---

## Definition Of Done

1. On the first step, user clearly chooses what exactly is being imported for task-family scenarios.
2. The choice is understandable before file mapping starts.
3. Task-related scenarios stop feeling like four disconnected technical entity codes.
4. Frontend regression passes.
