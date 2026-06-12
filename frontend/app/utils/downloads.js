import { translateImporterUi } from './importer-ui.js'

export const XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
export const XLSX_MAGIC_BYTES = [0x50, 0x4b, 0x03, 0x04]

function parseContentDispositionFilename(contentDisposition, fallbackFilename) {
  const normalizedHeader = String(contentDisposition || '')
  const filenameMatch = normalizedHeader.match(/filename="?([^";]+)"?/i)
  return String(filenameMatch?.[1] || fallbackFilename || 'download.bin')
}

function hasExpectedMagicBytes(bytes, expectedMagicBytes) {
  if (!Array.isArray(expectedMagicBytes) || expectedMagicBytes.length === 0) {
    return true
  }

  if (!(bytes instanceof Uint8Array) || bytes.length < expectedMagicBytes.length) {
    return false
  }

  return expectedMagicBytes.every((value, index) => bytes[index] === value)
}

export async function buildValidatedBinaryDownload(response, {
  fallbackFilename = 'download.bin',
  fallbackMimeType = 'application/octet-stream',
  expectedMagicBytes = [],
  invalidFormatMessage = translateImporterUi('importer.error.download_invalid_format', null, 'Скачанный файл поврежден или пришел в неверном формате.'),
} = {}) {
  const arrayBuffer = await response.arrayBuffer()
  const bytes = new Uint8Array(arrayBuffer)

  if (!hasExpectedMagicBytes(bytes, expectedMagicBytes)) {
    throw new Error(String(invalidFormatMessage || 'Invalid binary payload'))
  }

  const filename = parseContentDispositionFilename(
    response.headers.get('Content-Disposition'),
    fallbackFilename,
  )
  const mimeType = String(response.headers.get('Content-Type') || fallbackMimeType || 'application/octet-stream')

  return {
    filename,
    blob: new Blob([arrayBuffer], { type: mimeType }),
  }
}
