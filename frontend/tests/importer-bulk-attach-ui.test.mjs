import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const apiStoreSource = readFileSync(
  new URL('../app/stores/api.ts', import.meta.url),
  'utf8',
)

test('importer workbench exposes bulk attach as a dedicated internal view alongside history', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const currentView = ref<'wizard' | 'history' | 'bulkAttach'>('wizard')"), true)
  assert.equal(importerWorkbenchSource.includes("v-else-if=\"currentView === 'bulkAttach'\""), true)
  assert.equal(importerWorkbenchSource.includes("currentView.value = 'bulkAttach'"), true)
  assert.equal(importerWorkbenchSource.includes('<BulkAttachWizard'), true)
})

test('bulk attach opens a separate page from the advanced CRM scenario section', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Массовый импорт файлов'), true)
  assert.equal(importerWorkbenchSource.includes('Откроется отдельный экран сценария S17'), false)
  assert.equal(importerWorkbenchSource.includes('Массовое добавление файлов по фильтру CRM'), true)
  assert.equal(importerWorkbenchSource.includes("@click=\"goBackFromBulkAttach\""), true)
  assert.equal(importerWorkbenchSource.includes("v-if=\"showsAdvancedImportTools && selectedFileAttachEntityType\""), false)
})

test('bulk attach wizard can start from a preselected CRM entity inside the importer', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('initialEntityType'), true)
  assert.equal(bulkAttachWizardSource.includes('lockEntityType'), true)
  assert.equal(bulkAttachWizardSource.includes("v-if=\"!lockEntityType\""), true)
})

test('bulk attach wizard uses full-width layouts instead of a narrow centered column', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('mx-auto max-w-2xl'), false)
  assert.equal(bulkAttachWizardSource.includes('w-full space-y-6'), true)
  assert.equal(bulkAttachWizardSource.includes('lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]'), true)
})

test('bulk attach wizard builds dynamic CRM filters from Bitrix field catalog instead of two hardcoded fields', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes("const filterStatusId = ref('')"), false)
  assert.equal(bulkAttachWizardSource.includes("const filterAssignedById = ref('')"), false)
  assert.equal(bulkAttachWizardSource.includes('filterFieldRows'), true)
  assert.equal(bulkAttachWizardSource.includes('Добавить поле'), true)
  assert.equal(bulkAttachWizardSource.includes('Если поля не добавлены, будут выбраны все'), true)
  assert.equal(bulkAttachWizardSource.includes(":filter-fields=\"['label']\""), true)
  assert.equal(bulkAttachWizardSource.includes("placeholder: 'Поиск поля Bitrix24'"), true)
})

test('bulk attach wizard renders Bitrix24 enum filter values as selectable lists', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('items: Array<{ id: string, title: string }>'), true)
  assert.equal(bulkAttachWizardSource.includes('const hasSelectableItems = Array.isArray(row.items) && row.items.length > 0'), true)
  assert.equal(bulkAttachWizardSource.includes("placeholder=\"Выберите значение Bitrix24\""), true)
  assert.equal(bulkAttachWizardSource.includes("placeholder: 'Поиск значения Bitrix24'"), true)
})

test('bulk attach preview mentions only first 5 sample records', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('показаны первые 10'), false)
  assert.equal(bulkAttachWizardSource.includes('показаны первые 5'), true)
})

test('api store exposes import field catalog loader for bulk attach filters', () => {
  assert.equal(apiStoreSource.includes('const getImportFields = async ('), true)
  assert.equal(apiStoreSource.includes("/api/import-fields?${searchParams.toString()}"), true)
  assert.equal(apiStoreSource.includes('getImportFields,'), true)
})
