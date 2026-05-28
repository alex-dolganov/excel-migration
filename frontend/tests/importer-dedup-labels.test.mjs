import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildDedupFieldOptions,
  buildDedupPayload,
  buildImportRunRows,
  buildDedupWeakeningNotice,
  formatImporterFieldLabel,
} from '../app/utils/importer-ui.js'

test('formats dedup field labels in Russian for common Bitrix fields across imports', () => {
  assert.equal(formatImporterFieldLabel('OPPORTUNITY'), 'Сумма')
  assert.equal(formatImporterFieldLabel('CURRENCY_ID'), 'Валюта')
  assert.equal(formatImporterFieldLabel('STAGE_ID'), 'Стадия')
  assert.equal(formatImporterFieldLabel('PHONE'), 'Телефон')
  assert.equal(formatImporterFieldLabel('DATE_CREATE'), 'Дата создания')
  assert.equal(formatImporterFieldLabel('CREATED_TIME'), 'Дата создания')
  assert.equal(formatImporterFieldLabel('UNKNOWN_FIELD', 'Date create'), 'Дата создания')
})

test('builds dedup field options with Russian labels for mapped fields beyond legacy title phone email keys', () => {
  const options = buildDedupFieldOptions(
    [
      { targetFieldId: 'OPPORTUNITY' },
      { targetFieldId: 'CURRENCY_ID' },
      { targetFieldId: 'STAGE_ID' },
    ],
    [
      { id: 'OPPORTUNITY', title: 'Opportunity' },
      { id: 'CURRENCY_ID', title: 'Currency' },
      { id: 'STAGE_ID', title: 'Stage' },
    ],
  )

  assert.deepEqual(options, [
    { id: 'OPPORTUNITY', label: 'Сумма', hint: undefined },
    { id: 'CURRENCY_ID', label: 'Валюта', hint: undefined },
    { id: 'STAGE_ID', label: 'Стадия', hint: undefined },
  ])
})

test('keeps dedup payload fields for any valid mapped importer fields', () => {
  assert.deepEqual(buildDedupPayload({
    strategy: 'update',
    fields: ['OPPORTUNITY', 'currency_id', 'STAGE_ID'],
    condition: 'all',
  }), {
    strategy: 'update',
    fields: ['OPPORTUNITY', 'currency_id', 'STAGE_ID'],
    condition: 'all',
  })
})

test('formats duplicate match and missing dedup details with Russian field labels', () => {
  assert.deepEqual(buildImportRunRows({
    results: [
      {
        row_number: 2,
        status: 'updated',
        record_id: 912,
        duplicate_match_fields: ['OPPORTUNITY', 'DATE_CREATE'],
        dedup_missing_fields: ['CURRENCY_ID', 'CREATED_TIME'],
      },
    ],
  }), [
    {
      key: '2:updated',
      rowNumber: 2,
      status: 'updated',
      statusLabel: 'Обновлено',
      recordId: '912',
      title: '—',
      entityLabel: '—',
      createdAt: '—',
      details: 'Совпадение: Сумма, Дата создания · Неполный поиск дублей: Валюта, Дата создания',
    },
  ])

  assert.deepEqual(buildDedupWeakeningNotice({
    results: [
      { row_number: 2, dedup_missing_fields: ['STAGE_ID', 'CURRENCY_ID'] },
    ],
  }), {
    hasWarnings: true,
    count: 1,
    title: 'Неполный поиск дублей в 1 строке',
    description: 'Поиск дублей выполнен не по всем выбранным полям.',
    fieldsLabel: 'Валюта, Стадия',
    rowsLabel: '2',
    rowNumbers: [2],
  })
})

test('excludes custom fields (is_custom) from dedup options for smart processes', () => {
  const options = buildDedupFieldOptions(
    [
      { targetFieldId: 'title' },
      { targetFieldId: 'stageId' },
      { targetFieldId: 'ufCrm128_someField' },
    ],
    [
      { id: 'title', title: 'Название', is_custom: false },
      { id: 'stageId', title: 'Стадия', is_custom: false },
      { id: 'ufCrm128_someField', title: 'Доп. поле', is_custom: true },
    ],
  )

  const ids = options.map((o) => o.id)
  assert.ok(ids.includes('TITLE'), 'title should be included')
  assert.ok(ids.includes('STAGEID'), 'stageId should be included')
  assert.ok(!ids.includes('UFCRM128_SOMEFIELD'), 'custom field should be excluded')
})

test('importer workbench describes dedup keys as current import fields instead of legacy fixed ids', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Используются сопоставленные поля текущего импорта.'), true)
  assert.equal(importerWorkbenchSource.includes('Используются сопоставленные поля EMAIL, PHONE и TITLE.'), false)
})
