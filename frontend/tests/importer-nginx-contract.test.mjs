import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  deriveNginxClientMaxBodySize,
  renderPythonAppConfig,
} from '../../infrastructure/nginx/render-python-app-conf.mjs'

const templateSource = readFileSync(
  new URL('../../infrastructure/nginx/python-app.conf.template', import.meta.url),
  'utf8',
)

test('derives nginx client_max_body_size from IMPORT_MAX_FILE_SIZE_BYTES when it is the largest limit', () => {
  assert.equal(
    deriveNginxClientMaxBodySize({
      importMaxFileSizeBytes: '52428800',
      bulkAttachMaxFileSizeBytes: '52428800',
      nginxClientMaxBodySize: '',
    }),
    '50m',
  )
})

test('uses the larger bulk-attach limit so big bulk uploads are not rejected at nginx', () => {
  assert.equal(
    deriveNginxClientMaxBodySize({
      importMaxFileSizeBytes: '52428800',
      bulkAttachMaxFileSizeBytes: '157286400',
      nginxClientMaxBodySize: '',
    }),
    '150m',
  )
})

test('defaults bulk-attach limit to 150m when only the import size is provided', () => {
  assert.equal(
    deriveNginxClientMaxBodySize({
      importMaxFileSizeBytes: '52428800',
      nginxClientMaxBodySize: '',
    }),
    '150m',
  )
})

test('prefers explicit nginx client_max_body_size override when it is provided', () => {
  assert.equal(
    deriveNginxClientMaxBodySize({
      importMaxFileSizeBytes: '52428800',
      bulkAttachMaxFileSizeBytes: '157286400',
      nginxClientMaxBodySize: '64m',
    }),
    '64m',
  )
})

test('renders python nginx config from the shared importer env contract', () => {
  const rendered = renderPythonAppConfig({
    templateSource,
    env: {
      IMPORT_MAX_FILE_SIZE_BYTES: '52428800',
      NGINX_CLIENT_MAX_BODY_SIZE: '',
      NGINX_PROXY_SEND_TIMEOUT: '600s',
      NGINX_PROXY_READ_TIMEOUT: '600s',
    },
  })

  assert.equal(rendered.includes('client_max_body_size 150m;'), true)
  assert.equal(rendered.includes('proxy_send_timeout 600s;'), true)
  assert.equal(rendered.includes('proxy_read_timeout 600s;'), true)
  assert.equal(rendered.includes('__NGINX_CLIENT_MAX_BODY_SIZE__'), false)
})

test('checked-in python nginx config matches renderer defaults', () => {
  const rendered = renderPythonAppConfig({
    templateSource,
    env: {
      IMPORT_MAX_FILE_SIZE_BYTES: '52428800',
      NGINX_CLIENT_MAX_BODY_SIZE: '',
      NGINX_PROXY_SEND_TIMEOUT: '600s',
      NGINX_PROXY_READ_TIMEOUT: '600s',
    },
  }).trim()

  const committed = readFileSync(
    new URL('../../infrastructure/nginx/python-app.conf', import.meta.url),
    'utf8',
  ).trim()

  assert.equal(committed, rendered)
})
