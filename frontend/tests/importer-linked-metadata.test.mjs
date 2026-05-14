import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildLinkedImportEntityGroups,
  isLinkedImportEntityType,
} from '../app/utils/importer-ui.js'

test('builds linked entity groups from linked import schema metadata', () => {
  assert.deepEqual(buildLinkedImportEntityGroups('linked_company_contact'), [
    {
      id: 'company',
      label: 'Компания',
      sourceEntityType: 'company',
      prefix: 'COMPANY__',
    },
    {
      id: 'contact',
      label: 'Контакт',
      sourceEntityType: 'contact',
      prefix: 'CONTACT__',
    },
  ])
  assert.deepEqual(buildLinkedImportEntityGroups('deal'), [])
})

test('detects linked import entity types without hardcoding a single flow in the component', () => {
  assert.equal(isLinkedImportEntityType('linked_company_contact'), true)
  assert.equal(isLinkedImportEntityType('deal'), false)

  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const isLinkedEntityImport = computed(() => isLinkedImportEntityType(entityType.value))'), true)
})
