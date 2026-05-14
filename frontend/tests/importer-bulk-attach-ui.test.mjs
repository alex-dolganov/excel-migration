import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('importer workbench no longer keeps a separate bulk attach view alongside history', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const currentView = ref<'wizard' | 'history'>('wizard')"), true)
  assert.equal(importerWorkbenchSource.includes("v-else-if=\"currentView === 'bulkAttach'\""), false)
  assert.equal(importerWorkbenchSource.includes("@click=\"currentView = 'bulkAttach'\""), false)
  assert.equal(importerWorkbenchSource.includes('<BulkAttachWizard'), false)
})

test('bulk attach remains available only through the CRM scenario section', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Массовый импорт файлов'), true)
  assert.equal(importerWorkbenchSource.includes('Выберите CRM-сущность'), true)
  assert.equal(importerWorkbenchSource.includes('Сценарий S17'), false)
})
