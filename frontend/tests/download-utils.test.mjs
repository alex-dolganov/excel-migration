import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildValidatedBinaryDownload,
  XLSX_MAGIC_BYTES,
  XLSX_MIME_TYPE,
} from '../app/utils/downloads.js'

test('builds xlsx download payload from binary response with filename header', async () => {
  const binaryPayload = new Uint8Array([...XLSX_MAGIC_BYTES, 1, 2, 3, 4])
  const response = new Response(binaryPayload, {
    status: 200,
    headers: {
      'Content-Type': XLSX_MIME_TYPE,
      'Content-Disposition': 'attachment; filename="deal-import-example.xlsx"',
    },
  })

  const { filename, blob } = await buildValidatedBinaryDownload(response, {
    fallbackFilename: 'fallback.xlsx',
    fallbackMimeType: XLSX_MIME_TYPE,
    expectedMagicBytes: XLSX_MAGIC_BYTES,
    invalidFormatMessage: 'broken',
  })

  assert.equal(filename, 'deal-import-example.xlsx')
  assert.equal(blob.type, XLSX_MIME_TYPE)
  assert.deepEqual(new Uint8Array(await blob.arrayBuffer()), binaryPayload)
})

test('rejects non-xlsx payloads before browser saves corrupted file', async () => {
  const response = new Response('{"error":"not xlsx"}', {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Content-Disposition': 'attachment; filename="deal-import-example.xlsx"',
    },
  })

  await assert.rejects(
    () => buildValidatedBinaryDownload(response, {
      fallbackFilename: 'fallback.xlsx',
      fallbackMimeType: XLSX_MIME_TYPE,
      expectedMagicBytes: XLSX_MAGIC_BYTES,
      invalidFormatMessage: 'Скачанный Excel-шаблон поврежден или пришел в неверном формате.',
    }),
    /Скачанный Excel-шаблон поврежден или пришел в неверном формате\./,
  )
})
