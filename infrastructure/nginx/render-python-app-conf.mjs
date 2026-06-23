import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const DEFAULT_IMPORT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
const DEFAULT_PROXY_SEND_TIMEOUT = '600s'
const DEFAULT_PROXY_READ_TIMEOUT = '600s'

function normalizePositiveInteger(value, fallback) {
  const normalized = Number(value)
  if (!Number.isFinite(normalized) || normalized <= 0) {
    return fallback
  }

  return Math.floor(normalized)
}

export function deriveNginxClientMaxBodySize(options = {}) {
  const explicitValue = String(options.nginxClientMaxBodySize ?? '').trim()
  if (explicitValue) {
    return explicitValue
  }

  const importMaxFileSizeBytes = normalizePositiveInteger(
    options.importMaxFileSizeBytes,
    DEFAULT_IMPORT_MAX_FILE_SIZE_BYTES,
  )

  return `${Math.max(1, Math.ceil(importMaxFileSizeBytes / (1024 * 1024)))}m`
}

export function renderPythonAppConfig(options = {}) {
  const templateSource = String(options.templateSource || '').trim()
  if (!templateSource) {
    throw new Error('templateSource is required')
  }

  const env = options.env && typeof options.env === 'object' ? options.env : process.env
  const replacements = {
    '__NGINX_CLIENT_MAX_BODY_SIZE__': deriveNginxClientMaxBodySize({
      importMaxFileSizeBytes: env.IMPORT_MAX_FILE_SIZE_BYTES,
      nginxClientMaxBodySize: env.NGINX_CLIENT_MAX_BODY_SIZE,
    }),
    '__NGINX_PROXY_SEND_TIMEOUT__': String(env.NGINX_PROXY_SEND_TIMEOUT || DEFAULT_PROXY_SEND_TIMEOUT).trim() || DEFAULT_PROXY_SEND_TIMEOUT,
    '__NGINX_PROXY_READ_TIMEOUT__': String(env.NGINX_PROXY_READ_TIMEOUT || DEFAULT_PROXY_READ_TIMEOUT).trim() || DEFAULT_PROXY_READ_TIMEOUT,
  }

  return Object.entries(replacements).reduce(
    (result, [placeholder, value]) => result.replaceAll(placeholder, value),
    templateSource,
  )
}

const modulePath = fileURLToPath(import.meta.url)
const moduleDir = path.dirname(modulePath)

if (process.argv[1] && path.resolve(process.argv[1]) === modulePath) {
  const templatePath = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.join(moduleDir, 'python-app.conf.template')
  const outputPath = process.argv[3]
    ? path.resolve(process.argv[3])
    : ''

  const templateSource = readFileSync(templatePath, 'utf8')
  const rendered = renderPythonAppConfig({ templateSource, env: process.env })

  if (outputPath) {
    writeFileSync(outputPath, rendered)
  } else {
    process.stdout.write(rendered)
  }
}
