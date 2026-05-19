import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildLinkedImportEntityGroups,
  buildLinkedPrimaryEntityOptions,
  buildLinkedSecondaryEntityOptions,
  isLinkedImportEntityType,
  resolveLinkedStrategyEntityType,
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

test('builds dependent linked relation selector options and resolves them to explicit strategy ids', () => {
  assert.deepEqual(buildLinkedPrimaryEntityOptions(), [
    { value: 'company', label: 'Компания' },
    { value: 'contact', label: 'Контакт' },
    { value: 'deal', label: 'Сделка' },
  ])

  assert.deepEqual(buildLinkedSecondaryEntityOptions('company'), [
    { value: 'contact', label: 'Контакт' },
    { value: 'deal', label: 'Сделка' },
  ])
  assert.deepEqual(buildLinkedSecondaryEntityOptions('contact'), [
    { value: 'company', label: 'Компания' },
    { value: 'deal', label: 'Сделка' },
  ])
  assert.deepEqual(buildLinkedSecondaryEntityOptions('deal'), [
    { value: 'company', label: 'Компания' },
    { value: 'contact', label: 'Контакт' },
  ])

  assert.equal(resolveLinkedStrategyEntityType('company', 'contact'), 'linked_company_contact')
  assert.equal(resolveLinkedStrategyEntityType('company', 'deal'), 'linked_company_deal')
  assert.equal(resolveLinkedStrategyEntityType('contact', 'company'), 'linked_contact_company')
  assert.equal(resolveLinkedStrategyEntityType('contact', 'deal'), 'linked_contact_deal')
  assert.equal(resolveLinkedStrategyEntityType('deal', 'company'), 'linked_deal_company')
  assert.equal(resolveLinkedStrategyEntityType('deal', 'contact'), 'linked_deal_contact')
  assert.equal(resolveLinkedStrategyEntityType('deal', 'deal'), '')
})

test('detects linked import entity types without hardcoding a single flow in the component', () => {
  assert.equal(isLinkedImportEntityType('linked_company_contact'), true)
  assert.equal(isLinkedImportEntityType('linked_deal_contact'), true)
  assert.equal(isLinkedImportEntityType('deal'), false)

  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const isLinkedEntityImport = computed(() => isLinkedImportEntityType(entityType.value))'), true)
  assert.equal(importerWorkbenchSource.includes('const selectedLinkedPrimaryEntityType = ref(\'\')'), true)
  assert.equal(importerWorkbenchSource.includes('const selectedLinkedSecondaryEntityType = ref(\'\')'), true)
  assert.equal(importerWorkbenchSource.includes('resolveLinkedStrategyEntityType'), true)
})
