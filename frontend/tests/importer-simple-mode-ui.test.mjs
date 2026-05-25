import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildImportModeOptions,
  getImportModeMeta,
  buildSimpleDedupPreset,
} from '../app/utils/importer-ui.js'

const importerWorkbenchSource = readFileSync(
  new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
  'utf8',
)
const apiStoreSource = readFileSync(
  new URL('../app/stores/api.ts', import.meta.url),
  'utf8',
)

test('builds simple and advanced import mode options', () => {
  assert.deepEqual(buildImportModeOptions(), [
    {
      value: 'simple',
      label: 'Простой импорт',
      description: 'Только файл, сущность, простое сопоставление полей и запуск импорта.',
    },
    {
      value: 'advanced',
      label: 'Расширенный импорт',
      description: 'Шаблоны сопоставления, расширенная настройка дублей и детальный отчёт по каждой строке.',
    },
  ])
})

test('returns advanced mode metadata for simple and advanced flows', () => {
  assert.deepEqual(getImportModeMeta('simple'), {
    value: 'simple',
    label: 'Простой импорт',
    description: 'Только файл, сущность, простое сопоставление полей и запуск импорта.',
    hidesAdvancedTools: true,
    allowsPerRowDedupDecisions: false,
  })

  assert.deepEqual(getImportModeMeta('advanced'), {
    value: 'advanced',
    label: 'Расширенный импорт',
    description: 'Шаблоны сопоставления, расширенная настройка дублей и детальный отчёт по каждой строке.',
    hidesAdvancedTools: false,
    allowsPerRowDedupDecisions: true,
  })
})

test('builds simple dedup preset from mapped fields without unsupported ask strategy', () => {
  assert.deepEqual(buildSimpleDedupPreset({
    entityType: 'deal',
    mappingRows: [
      { targetFieldId: 'TITLE' },
      { targetFieldId: 'EMAIL' },
      { targetFieldId: 'PHONE' },
      { targetFieldId: '' },
    ],
  }), {
    strategy: 'update',
    condition: 'any',
    fields: ['EMAIL', 'PHONE', 'TITLE'],
    available: true,
  })

  assert.deepEqual(buildSimpleDedupPreset({
    entityType: 'task',
    mappingRows: [{ targetFieldId: 'TITLE' }],
  }), {
    strategy: 'create',
    condition: 'any',
    fields: [],
    available: false,
  })

  assert.deepEqual(buildSimpleDedupPreset({
    entityType: 'linked_deal_contact',
    mappingRows: [
      { targetFieldId: 'CONTACT__EMAIL' },
      { targetFieldId: 'CONTACT__PHONE' },
      { targetFieldId: 'DEAL__TITLE' },
    ],
  }), {
    strategy: 'update',
    condition: 'any',
    fields: ['EMAIL', 'PHONE', 'TITLE'],
    available: true,
  })
})

test('importer workbench starts with simple versus advanced mode choice', () => {
  assert.equal(importerWorkbenchSource.includes('Выберите тип импорта'), true)
  assert.equal(importerWorkbenchSource.includes('Выбрать режим'), true)
  assert.equal(importerWorkbenchSource.includes('buildImportModeOptions'), true)
})

test('importer workbench keeps simple mode isolated from advanced alias rules while preserving session mapping', () => {
  assert.equal(importerWorkbenchSource.includes('const sessionSavedMapping = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('const effectiveSavedMapping = computed(() => sessionSavedMapping.value)'), true)
  assert.equal(importerWorkbenchSource.includes('preferSavedMapping: Object.keys(sessionSavedMapping.value).length > 0'), true)
  assert.equal(importerWorkbenchSource.includes('savedMapping: sessionSavedMapping.value'), true)
})

test('importer workbench requests mapping data without advanced alias rules in simple mode', () => {
  assert.equal(importerWorkbenchSource.includes('apiStore.getImportMapping(String(session.value.id), importModeMeta.value.value)'), true)
  assert.match(
    importerWorkbenchSource,
    /apiStore\.getImportAliasRules\(\s*entityType\.value,\s*selectedSmartProcessConfig\.value,\s*importModeMeta\.value\.value,\s*\)/,
  )
  assert.equal(apiStoreSource.includes("searchParams.set('import_mode', importMode)"), true)
})

test('importer workbench saves mapping in the active import mode scope', () => {
  assert.match(
    importerWorkbenchSource,
    /apiStore\.saveImportMapping\(\s*String\(session\.value\.id\),[\s\S]{0,220}currentDedupSettingsPayload\.value,[\s\S]{0,80}importModeMeta\.value\.value,/,
  )
  assert.equal(apiStoreSource.includes("body: JSON.stringify({ mapping, dedup, import_mode: importMode, ...options })"), true)
  assert.equal(apiStoreSource.includes('import_mode?: string'), true)
  assert.equal(importerWorkbenchSource.includes('import_mode: importModeMeta.value.value'), true)
})

test('importer workbench uses primary blue style for all back navigation buttons', () => {
  assert.equal(importerWorkbenchSource.includes('← Назад'), true)
  assert.equal(importerWorkbenchSource.includes('Выбрать режим'), true)
  const primaryBlueButtons = importerWorkbenchSource.match(/color="air-primary"/g) || []
  assert.ok(primaryBlueButtons.length >= 6)
})
