import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  shouldRenderInitCard,
  getInitStageDescription,
} from '../app/utils/index-page-init.js'

test('renders init card while app initialization is still pending', () => {
  assert.equal(
    shouldRenderInitCard({
      isInit: false,
      initError: '',
      initStage: 'frame',
    }),
    true,
  )
})

test('describes current initialization stage for the user', () => {
  assert.equal(
    getInitStageDescription('app-init'),
    'Initializing application data inside Bitrix24.',
  )
})

test('deal placement page renders importer workbench instead of demo table', () => {
  const placementPageSource = readFileSync(
    new URL('../app/pages/handler/placement-crm-deal-detail-tab.client.vue', import.meta.url),
    'utf8',
  )

  assert.equal(placementPageSource.includes('<ImporterWorkbench'), true)
  assert.equal(placementPageSource.includes('placement.crm_deal_detail_tab.action'), false)
  assert.equal(placementPageSource.includes('dataList = ref(['), false)
})
