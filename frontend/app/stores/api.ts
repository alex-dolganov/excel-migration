import type { B24Frame } from '@bitrix24/b24jssdk'
import { withoutTrailingSlash } from 'ufo'
import { buildValidatedBinaryDownload, XLSX_MAGIC_BYTES, XLSX_MIME_TYPE } from '~/utils/downloads'

export const useApiStore = defineStore(
  'api',
  () => {
    let $b24: null | B24Frame = null
    const config = useRuntimeConfig()
    const apiUrl = withoutTrailingSlash(config.public.apiUrl)

    const tokenJWT = ref('')

    const isInitTokenJWT = computed(() => {
      return tokenJWT.value.length > 2
    })

    const $api = $fetch.create({
      baseURL: apiUrl,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Health check
    const checkHealth = async (): Promise<{
      status: string
      backend: string
      timestamp: number
    }> => {
      try {
        return await $api('/api/health', {
          headers: {
            Authorization: `Bearer ${tokenJWT.value}`
          }
        })
      } catch {
        throw new Error('Backend health check failed')
      }
    }

    // API
    const getEnum = async (): Promise<string[]> => {
      return await $api('/api/enum', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getList = async (): Promise<string[]> => {
      return await $api('/api/list', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const postInstall = async (data: Record<string, any>): Promise<Record<string, any>> => {
      return await $api('/api/install', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    }

    const telemetryTest = async (): Promise<{
      status: string
      fired_events: string[]
      fired_count: number
      session_id: string
      portal_domain: string
    }> => {
      return await $api('/api/telemetry/test', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getToken = async (data: Record<string, any>): Promise<{ token: string }> => {
      return await $api('/api/getToken', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    }

    const createImportSession = async (data: {
      entity_type: string
      source_format: string
      original_filename: string
      entity_config?: Record<string, any>
    }): Promise<{ item: Record<string, any> }> => {
      return await $api('/api/import-sessions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify(data),
      })
    }

    const getImportSmartProcesses = async (): Promise<{ items: Record<string, any>[] }> => {
      return await $api('/api/import-smart-processes', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const listImportSessions = async (): Promise<{ items: Record<string, any>[] }> => {
      return await $api('/api/import-sessions', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getImportSession = async (sessionId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}`, {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const uploadImportFile = async (sessionId: string, file: File): Promise<{ item: Record<string, any> }> => {
      const formData = new FormData()
      formData.append('file', file)

      return await $fetch(`/api/import-sessions/${sessionId}/upload`, {
        baseURL: apiUrl,
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: formData,
      })
    }

    const getImportPreview = async (sessionId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/preview`, {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const updateImportPreview = async (sessionId: string, data: {
      header_row: number
      data_start_row: number
    }): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/preview`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify(data),
      })
    }

    const getImportMapping = async (sessionId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/mapping`, {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getImportFields = async (
      entityType: string,
      entityConfig?: Record<string, any> | null,
    ): Promise<{ items: Record<string, any>[] }> => {
      const searchParams = new URLSearchParams()
      if (entityType) {
        searchParams.set('entity_type', entityType)
      }
      if (entityType === 'smart_process' && entityConfig?.entityTypeId) {
        searchParams.set('entity_type_id', String(entityConfig.entityTypeId))
      }

      return await $api(`/api/import-fields?${searchParams.toString()}`, {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getImportTemplates = async (
      entityType: string,
      entityConfig?: Record<string, any> | null,
    ): Promise<{ items: Record<string, any>[] }> => {
      const searchParams = new URLSearchParams()
      if (entityType) {
        searchParams.set('entity_type', entityType)
      }
      if (entityType === 'smart_process' && entityConfig?.entityTypeId) {
        searchParams.set('entity_type_id', String(entityConfig.entityTypeId))
      }

      return await $api(`/api/import-templates?${searchParams.toString()}`, {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getImportAliasRules = async (
      entityType: string,
      entityConfig?: Record<string, any> | null,
    ): Promise<{ items: Record<string, any>[] }> => {
      const searchParams = new URLSearchParams()
      if (entityType) {
        searchParams.set('entity_type', entityType)
      }
      if (entityType === 'smart_process' && entityConfig?.entityTypeId) {
        searchParams.set('entity_type_id', String(entityConfig.entityTypeId))
      }

      return await $api(`/api/import-alias-rules?${searchParams.toString()}`, {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getImportPermissions = async (): Promise<{ item: Record<string, any> }> => {
      return await $api('/api/import-permissions/me', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const getImportRoles = async (): Promise<{ items: Record<string, any>[] }> => {
      return await $api('/api/import-roles', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const saveImportRole = async (data: {
      b24_user_id: number
      role: string
    }): Promise<{ item: Record<string, any> }> => {
      return await $api('/api/import-roles', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify(data),
      })
    }

    const saveImportMapping = async (
      sessionId: string,
      mapping: Record<string, any>,
      dedup: Record<string, any>,
      options: {
        default_responsible_id?: string
        default_creator_id?: string
        default_comment_author_id?: string
      } = {},
    ): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/mapping`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({ mapping, dedup, ...options }),
      })
    }

    const saveImportTemplate = async (
      sessionId: string,
      name: string,
      mapping?: Record<string, any>,
      dedup?: Record<string, any>,
    ): Promise<{ item: Record<string, any> }> => {
      return await $api('/api/import-templates', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({ session_id: sessionId, name, mapping, dedup }),
      })
    }

    const saveImportAliasRule = async (
      sessionId: string,
      sourceLabel: string,
      targetFieldId: string,
    ): Promise<{ item: Record<string, any> }> => {
      return await $api('/api/import-alias-rules', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({
          session_id: sessionId,
          source_label: sourceLabel,
          target_field_id: targetFieldId,
        }),
      })
    }

    const applyImportTemplate = async (sessionId: string, templateId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/apply-template`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({ template_id: templateId }),
      })
    }

    const validateImportSession = async (sessionId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/validate`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({}),
      })
    }

    const dryRunImportSession = async (
      sessionId: string,
      options: { mode?: string } = {},
    ): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/dry-run`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({
          mode: String(options.mode || '').trim(),
        }),
      })
    }

    const runImportSession = async (sessionId: string, perRowDecisions: Record<string, string> = {}): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/run`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({ per_row_decisions: perRowDecisions }),
      })
    }

    const cancelImportSession = async (sessionId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/cancel`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({}),
      })
    }

    const retryFailedImportSession = async (sessionId: string): Promise<{ item: Record<string, any> }> => {
      return await $api(`/api/import-sessions/${sessionId}/retry-failed`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
        body: JSON.stringify({}),
      })
    }

    const downloadImportSessionReportCsv = async (sessionId: string): Promise<{ blob: Blob, filename: string }> => {
      const response = await fetch(`${apiUrl}/api/import-sessions/${sessionId}/report.csv`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
      })

      if (!response.ok) {
        try {
          const payload = await response.json()
          throw new Error(String(payload?.error || 'Не удалось скачать CSV-отчет'))
        } catch (error) {
          if (error instanceof Error) {
            throw error
          }
          throw new Error('Не удалось скачать CSV-отчет')
        }
      }

      const contentDisposition = String(response.headers.get('Content-Disposition') || '')
      const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i)

      return {
        blob: await response.blob(),
        filename: String(filenameMatch?.[1] || 'import-report.csv'),
      }
    }

    const fetchCrmEntityFields = async (entityType: string): Promise<{ fields: { id: string, title: string, type: string, items: { value: string, label: string }[] }[] }> => {
      return await $api('/api/crm-entity-fields', {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenJWT.value}` },
        body: JSON.stringify({ entity_type: entityType }),
      })
    }

    const fetchCrmFileFields = async (entityType: string): Promise<{ fields: { id: string, title: string }[] }> => {
      return await $api('/api/crm-file-fields', {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenJWT.value}` },
        body: JSON.stringify({ entity_type: entityType }),
      })
    }

    const crmFilterPreview = async (data: {
      entity_type: string
      filter: Record<string, any>
    }): Promise<{ total: number, has_more: boolean, sample: { id: number, title: string }[] }> => {
      return await $api('/api/crm-filter-preview', {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenJWT.value}` },
        body: JSON.stringify(data),
      })
    }

    const uploadBulkAttachFile = async (file: File): Promise<{ file_id: string, file_name: string }> => {
      const formData = new FormData()
      formData.append('file', file)
      return await $fetch(`${apiUrl}/api/bulk-attach-upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenJWT.value}` },
        body: formData,
      })
    }

    const createBulkAttachSession = async (data: {
      entity_type: string
      filter: Record<string, any>
      file_url?: string
      file_id?: string
      field_id: string
      file_name?: string
    }): Promise<{ item: Record<string, any> }> => {
      return await $api('/api/bulk-attach-sessions', {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenJWT.value}` },
        body: JSON.stringify(data),
      })
    }

    const runBulkAttachSession = async (sessionId: string): Promise<{ item: Record<string, any>, result: Record<string, any> }> => {
      return await $api(`/api/bulk-attach-sessions/${sessionId}/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenJWT.value}` },
        body: JSON.stringify({}),
      })
    }

    const getImportDepartments = async (): Promise<{ items: { id: string, name: string, parent_id: string | null }[] }> => {
      return await $api('/api/import-departments', {
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        }
      })
    }

    const downloadImportExampleTemplateXlsx = async (
      entityType: string,
      entityConfig?: Record<string, any> | null,
    ): Promise<{ blob: Blob, filename: string }> => {
      const searchParams = new URLSearchParams()
      if (entityType) {
        searchParams.set('entity_type', entityType)
      }
      if (entityType === 'smart_process' && entityConfig?.entityTypeId) {
        searchParams.set('entity_type_id', String(entityConfig.entityTypeId))
      }
      if (entityType === 'smart_process' && entityConfig?.title) {
        searchParams.set('entity_title', String(entityConfig.title))
      }

      const response = await fetch(`${apiUrl}/api/import-example-template.xlsx?${searchParams.toString()}`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${tokenJWT.value}`
        },
      })

      if (!response.ok) {
        try {
          const payload = await response.json()
          throw new Error(String(payload?.error || 'Не удалось скачать Excel-шаблон'))
        } catch (error) {
          if (error instanceof Error) {
            throw error
          }
          throw new Error('Не удалось скачать Excel-шаблон')
        }
      }

      return await buildValidatedBinaryDownload(response, {
        fallbackFilename: `${entityType || 'import'}-import-example.xlsx`,
        fallbackMimeType: XLSX_MIME_TYPE,
        expectedMagicBytes: XLSX_MAGIC_BYTES,
        invalidFormatMessage: 'Скачанный Excel-шаблон поврежден или пришел в неверном формате.',
      })
    }

    const init = async (b24: B24Frame) => {
      $b24 = b24
      await reinitToken()
    }

    const reinitToken = async () => {
      if ($b24 === null) {
        console.error('B24 non init. Use api.init()')
        return
      }

      const authData = $b24.auth.getAuthData()

      if(authData === false) {
        throw new Error('Some problem with auth. See App logic')
      }

      const user = useUserStore()
      const appSettings = useAppSettingsStore()

      const response = await getToken({
        DOMAIN: withoutTrailingSlash(authData.domain).replace('https://', '').replace('http://', ''),
        PROTOCOL: authData.domain.includes('https://') ? 1 : 0,
        LANG: $b24.getLang(),
        APP_SID: $b24.getAppSid(),
        AUTH_ID: authData.access_token,
        AUTH_EXPIRES: authData.expires_in,
        REFRESH_ID: authData.refresh_token,
        REFRESH_TOKEN: authData.refresh_token,
        member_id: authData.member_id,
        user_id: user.id,
        IS_ADMIN: Boolean(user.isAdmin),
        status: appSettings.status
      })

      tokenJWT.value = response.token
    }

    return {
      tokenJWT,
      isInitTokenJWT,
      checkHealth,
      init,
      getEnum,
      getList,
      postInstall,
      telemetryTest,
      createImportSession,
      getImportSmartProcesses,
      listImportSessions,
      getImportSession,
      uploadImportFile,
      getImportPreview,
      updateImportPreview,
      getImportMapping,
      getImportFields,
      getImportTemplates,
      getImportAliasRules,
      getImportPermissions,
      getImportRoles,
      saveImportMapping,
      saveImportRole,
      saveImportTemplate,
      saveImportAliasRule,
      applyImportTemplate,
      validateImportSession,
      dryRunImportSession,
      runImportSession,
      cancelImportSession,
      retryFailedImportSession,
      downloadImportSessionReportCsv,
      downloadImportExampleTemplateXlsx,
      getImportDepartments,
      fetchCrmEntityFields,
      fetchCrmFileFields,
      crmFilterPreview,
      uploadBulkAttachFile,
      createBulkAttachSession,
      runBulkAttachSession,
    }
  }
)
