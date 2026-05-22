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
      description: 'Полный сценарий с шаблонами, правилами сопоставления и расширенной настройкой дублей.',
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
    description: 'Полный сценарий с шаблонами, правилами сопоставления и расширенной настройкой дублей.',
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
  assert.equal(importerWorkbenchSource.includes('Простой импорт'), true)
  assert.equal(importerWorkbenchSource.includes('Расширенный импорт'), true)
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

test('importer workbench uses primary blue style for all back navigation buttons', () => {
  assert.match(
    importerWorkbenchSource,
    /label="← Режим"[\s\S]{0,120}color="air-primary"/,
  )
  assert.match(
    importerWorkbenchSource,
    /label="← Назад"[\s\S]{0,120}color="air-primary"/,
  )

  const backButtons = importerWorkbenchSource.match(/label="Назад"[\s\S]{0,120}color="air-primary"/g) || []
  assert.equal(backButtons.length, 6)
})
