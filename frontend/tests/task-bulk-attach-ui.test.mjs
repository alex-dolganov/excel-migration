import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('task attachment mode is treated as an inline bulk attach flow inside the main importer', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const isTaskBulkAttachFlow = computed(() => ("), true)
  assert.equal(importerWorkbenchSource.includes("selectedFamily.value === 'task'"), true)
  assert.equal(importerWorkbenchSource.includes("entityType.value === 'task_attachment'"), true)
  assert.equal(importerWorkbenchSource.includes("|| isTaskBulkAttachFlow.value"), true)
})

test('task attachment bulk flow loads task filter fields and does not require a crm file field', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("if (normalizedValue === 'task_attachment')"), true)
  assert.equal(importerWorkbenchSource.includes("apiStore.getImportFields('task')"), true)
  assert.equal(importerWorkbenchSource.includes("if (!isTaskBulkAttachFlow.value && !normalizedFieldId)"), true)
  assert.equal(importerWorkbenchSource.includes("...(isTaskBulkAttachFlow.value ? {} : { field_id: normalizedFieldId })"), true)
})

test('task attachment bulk flow accepts a regular attachment file instead of only excel formats', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const isSpreadsheetUploadRequired = computed(() => !isBulkAttachFlow.value)"), true)
  assert.equal(importerWorkbenchSource.includes("if (nextFile && isSpreadsheetUploadRequired.value && !detectSourceFormat(nextFile.name))"), true)
  assert.equal(importerWorkbenchSource.includes("if (isSpreadsheetUploadRequired.value && !detectSourceFormat(file.name))"), true)
  assert.equal(importerWorkbenchSource.includes(":accept=\"isSpreadsheetUploadRequired ? '.xlsx,.xls,.csv' : undefined\""), true)
})

test('task attachment section renders task-oriented bulk copy instead of excel-template copy', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Фильтр задач:'), true)
  assert.equal(importerWorkbenchSource.includes('Один файл будет прикреплён ко всем найденным задачам'), true)
  assert.equal(importerWorkbenchSource.includes('Excel-шаблон здесь не нужен'), true)
  assert.equal(importerWorkbenchSource.includes("selectedTaskEntityType === 'task_attachment' && !bulkFilterPreview"), true)
})

test('resuming task bulk attach from history restores the inline task flow instead of crm bulk mode', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const resumeStart = importerWorkbenchSource.indexOf('async function resumeHistorySession(sessionId: string) {')
  const resumeEnd = importerWorkbenchSource.indexOf('function getStepStatus(step: number): StepState {', resumeStart)
  const resumeSource = importerWorkbenchSource.slice(resumeStart, resumeEnd)

  assert.equal(resumeSource.includes("const bulkAttachMode = String(bulkAttachSummary.mode || '').trim().toLowerCase()"), true)
  assert.equal(resumeSource.includes("bulkAttachMode === 'task'"), true)
  assert.equal(resumeSource.includes("selectedFamily.value = 'task'"), true)
  assert.equal(resumeSource.includes("selectedTaskEntityType.value = 'task_attachment'"), true)
  assert.equal(resumeSource.includes("await loadBulkAttachEntityFields('task_attachment')"), true)
  assert.equal(resumeSource.includes("selectedFamily.value = 'crm'"), true)
})
