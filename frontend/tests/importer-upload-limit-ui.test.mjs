import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const importerWorkbenchSource = readFileSync(
  new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
  'utf8',
)

test('importer workbench rejects oversized files before upload starts', () => {
  assert.equal(importerWorkbenchSource.includes('const runtimeConfig = useRuntimeConfig()'), true)
  assert.equal(importerWorkbenchSource.includes('runtimeConfig.public.importMaxFileSizeBytes'), true)
  assert.equal(importerWorkbenchSource.includes("nextFile && nextFile.size > MAX_IMPORT_FILE_SIZE_BYTES"), true)
  assert.equal(importerWorkbenchSource.includes("selectedFile.value.size > MAX_IMPORT_FILE_SIZE_BYTES"), true)
  assert.equal(importerWorkbenchSource.includes("buildImportFileSizeErrorMessage(nextFile)"), true)
  assert.equal(importerWorkbenchSource.includes("buildImportFileSizeErrorMessage(selectedFile.value)"), true)
})

test('importer workbench shows the runtime file size limit label in the file picker card', () => {
  assert.equal(importerWorkbenchSource.includes('Поддерживаются форматы Excel и CSV, размер файла до ${MAX_IMPORT_FILE_SIZE_LABEL}'), true)
  assert.equal(importerWorkbenchSource.includes('XLSX, XLS, CSV · до ${MAX_IMPORT_FILE_SIZE_LABEL}'), true)
})
