import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const importerWorkbenchSource = readFileSync(
  new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
  'utf8',
)

test('importer workbench rejects oversized files before upload starts', () => {
  assert.equal(importerWorkbenchSource.includes("const MAX_IMPORT_FILE_SIZE_BYTES = 50 * 1024 * 1024"), true)
  assert.equal(importerWorkbenchSource.includes("const MAX_IMPORT_FILE_SIZE_LABEL = '50 МБ'"), true)
  assert.equal(importerWorkbenchSource.includes("nextFile && nextFile.size > MAX_IMPORT_FILE_SIZE_BYTES"), true)
  assert.equal(importerWorkbenchSource.includes("selectedFile.value.size > MAX_IMPORT_FILE_SIZE_BYTES"), true)
  assert.equal(importerWorkbenchSource.includes("buildImportFileSizeErrorMessage(nextFile)"), true)
  assert.equal(importerWorkbenchSource.includes("buildImportFileSizeErrorMessage(selectedFile.value)"), true)
})

test('importer workbench shows the 50 MB limit in the file picker card', () => {
  assert.equal(importerWorkbenchSource.includes('Поддерживаются форматы Excel и CSV, размер файла до 50 МБ'), true)
})
