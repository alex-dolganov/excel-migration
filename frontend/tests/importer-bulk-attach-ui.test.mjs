import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('importer workbench supports a dedicated bulk attach view inside the main entry flow', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const currentView = ref<'wizard' | 'history' | 'bulkAttach'>('wizard')"), true)
  assert.equal(importerWorkbenchSource.includes('<BulkAttachWizard'), true)
  assert.equal(importerWorkbenchSource.includes("v-else-if=\"currentView === 'bulkAttach'\""), true)
  assert.equal(importerWorkbenchSource.includes("currentView = 'bulkAttach'"), true)
})

test('importer workbench exposes bulk attach call-to-action without reintroducing a separate root page tab', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Массовый импорт файлов'), true)
  assert.equal(importerWorkbenchSource.includes('Сценарий S17'), true)
  assert.equal(importerWorkbenchSource.includes("currentView = 'wizard'"), true)
})
