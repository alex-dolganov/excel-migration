<script setup lang="ts">
import {
  buildExampleTemplateDownloadMeta,
  buildImporterPermissionState,
  buildImportScenarioSections,
  buildImportModeOptions,
  buildScenarioSelectionSummary,
  buildMigrationStatusBadge,
  buildDedupPayload,
  buildDedupFieldOptions,
  buildDedupWeakeningNotice,
  buildSimpleDedupPreset,
  EMPTY_MAPPING_SELECT_VALUE,
  buildDryRunRows,
  buildFieldGuidanceHints,
  buildFieldTypeLabel,
  getImportModeMeta,
  buildDryRunSummaryFromSessionSnapshot,
  buildImportRunProblemGroups,
  buildImportRunRows,
  buildImportRunCompletionNotice,
  buildImportRunSummaryFromSessionSnapshot,
  buildLinkedImportRunSummary,
  buildLinkedImportEntityGroups,
  buildImportRunStatusFilters,
  buildImportRunRetryState,
  buildLinkedPrimaryEntityOptions,
  buildLinkedSecondaryEntityOptions,
  buildResolvedDryRunSummary,
  isLinkedImportEntityType,
  resolveLinkedStrategyEntityType,
  resolveLinkedStrategyPair,
  shouldWaitForDryRunExecutionSnapshot,
  shouldWaitForImportExecutionSnapshot,
  buildMappingFieldItems,
  buildMappingPayload,
  buildMappingRows,
  buildRequiredFieldSummary,
  filterImportRunRows,
  resolveImportRunFilterId,
  buildUnmappedValueSummary,
  buildValueMappingRows,
  buildValueMappingStatus,
  buildValidationIssueRows,
  canAdvanceWizard,
  detectSourceFormat,
  formatImporterFieldLabel,
  getWizardAdvanceMode,
  getWizardNextLabel,
  normalizeMappingSelectValue,
  resolveMappingSelectValue,
  buildSessionHistoryRows,
  FILE_ATTACH_IMPORT_SCENARIOS,
} from '~/utils/importer-ui'
import { sleepAction } from '~/utils/sleep'

type MappingRow = {
  key: string
  column: string
  sourceHeader: string
  targetFieldId: string
  targetFieldTitle: string
  autoMatchType?: string
  autoMatchLabel?: string
  autoMatchReason?: string
  autoMatchReasonLabel?: string
  targetFieldType?: string
  targetFieldTypeLabel?: string
  targetFieldRequired?: boolean
  targetFieldIsCustom?: boolean
  targetFieldIsMultiple?: boolean
  targetFieldGuidanceHints?: string[]
  candidateSuggestions?: Array<{
    targetFieldId: string
    targetFieldTitle: string
    matchType: string
    matchLabel: string
    matchReason: string
    matchReasonLabel: string
  }>
  valueMapping?: Record<string, string>
  columnType?: string
}

type ValueMappingRow = {
  key: string
  targetFieldId: string
  targetFieldTitle: string
  sourceValue: string
  selectedTargetValue: string
  options: Array<{ value: string, label: string }>
}

type ValidationIssueRow = {
  key: string
  rowNumber: number
  column: string
  sourceHeader: string
  targetField: string
  message: string
  value: string
}

type ImportRunRow = {
  key: string
  rowNumber: number
  rowNumberLabel?: string
  status: string
  statusLabel: string
  createdAt: string
  entityLabel: string
  title: string
  recordId: string
  details: string
  hasProblem?: boolean
  hasDedupRisk?: boolean
  entityTree?: LinkedEntityTree
}

type LinkedEntityTreeItem = {
  key: string
  entityId: string
  entityLabel: string
  title: string
  recordId: string
  status: string
  statusLabel: string
  rowNumbers: number[]
  details: string
}

type LinkedEntityTree = {
  primary: LinkedEntityTreeItem
  linkedItems: LinkedEntityTreeItem[]
}

type LinkedImportSummaryItem = {
  key: string
  title: string
  recordId: string
  statusLabel: string
}

type LinkedImportSummarySection = {
  id: string
  title: string
  total: number
  pageSize: number
  pageCount: number
  hasOverflow: boolean
  items: LinkedImportSummaryItem[]
}

type ImportRunFilterItem = {
  id: string
  label: string
  count: number
}

type ImportRunProblemGroup = {
  key: string
  label: string
  reason: string
  count: number
  rowNumbers: number[]
  statuses: string[]
}

type DryRunRow = {
  key: string
  rowNumber: number
  rowNumberLabel?: string
  status: string
  statusLabel: string
  details: string
  entityTree?: LinkedEntityTree
}

type ImportTemplateItem = {
  id: string
  name: string
}

type StepState = 'done' | 'current' | 'upcoming'
type BulkFlowStep = 'setup' | 'review' | 'execution'

const props = withDefaults(defineProps<{
  initialImportMode?: string
}>(), {
  initialImportMode: '',
})

const emit = defineEmits<{ 'back-to-landing': [] }>()

const apiStore = useApiStore()
const userStore = useUserStore()
const runtimeConfig = useRuntimeConfig()
const DEFAULT_MAX_IMPORT_FILE_SIZE_BYTES = 50 * 1024 * 1024

function normalizeImportFileSizeBytes(value: unknown) {
  const normalized = Number(value)
  if (!Number.isFinite(normalized) || normalized <= 0) {
    return DEFAULT_MAX_IMPORT_FILE_SIZE_BYTES
  }

  return Math.floor(normalized)
}

function formatImportFileSizeLabel(sizeInBytes: number) {
  const sizeInMegabytes = sizeInBytes / (1024 * 1024)
  if (Number.isInteger(sizeInMegabytes)) {
    return `${sizeInMegabytes} МБ`
  }

  return `${sizeInMegabytes.toFixed(1)} МБ`
}

const MAX_IMPORT_FILE_SIZE_BYTES = normalizeImportFileSizeBytes(runtimeConfig.public.importMaxFileSizeBytes)
const MAX_IMPORT_FILE_SIZE_LABEL = formatImportFileSizeLabel(MAX_IMPORT_FILE_SIZE_BYTES)
const IMPORT_FILE_PICKER_HELPER_TEXT = `Поддерживаются форматы Excel и CSV, размер файла до ${MAX_IMPORT_FILE_SIZE_LABEL}`
const IMPORT_FILE_DROPDOWN_LIMIT_TEXT = `XLSX, XLS, CSV · до ${MAX_IMPORT_FILE_SIZE_LABEL}`
const BULK_ATTACH_FILE_PICKER_HELPER_TEXT = `Загрузите один файл любого формата, размер файла до ${MAX_IMPORT_FILE_SIZE_LABEL}`
const BULK_ATTACH_FILE_DROPDOWN_LIMIT_TEXT = `Любой файл · до ${MAX_IMPORT_FILE_SIZE_LABEL}`
const PER_ROW_DEDUP_DECISION_VALUES = new Set(['create', 'update', 'skip'])
const DRY_RUN_RESULTS_PAGE_SIZE = 20
const COLLAPSIBLE_TEXT_LIMIT = 220

const importMode = ref('')
const entityType = ref('')
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const session = ref<Record<string, any> | null>(null)
const preview = ref<Record<string, any> | null>(null)
const mappingData = ref<Record<string, any> | null>(null)
const mappingRows = ref<MappingRow[]>([])
const taskDefaultResponsibleId = ref('')
const taskDefaultCreatorId = ref('')
const taskDefaultCommentAuthorId = ref('')
const dedupStrategy = ref('create')
const dedupCondition = ref<'any' | 'all'>('any')
const linkedDedupSettings = ref<Record<string, { strategy: string, condition: 'any' | 'all', fields: string[] }>>({})
const perRowDedupDecisions = ref<Record<string, any>>({})
const mappingDragSourceIndex = ref<number | null>(null)
const mappingDragOverIndex = ref<number | null>(null)
const dedupFields = ref<string[]>([])
const validationData = ref<Record<string, any> | null>(null)
const dryRunData = ref<Record<string, any> | null>(null)
const preimportScanData = ref<Record<string, any> | null>(null)
const importRunData = ref<Record<string, any> | null>(null)
const importTemplates = ref<ImportTemplateItem[]>([])
const importAliasRules = ref<Record<string, any>[]>([])
const selectedTemplateId = ref('')
const templateNameInput = ref('')
const headerRowInput = ref(1)
const dataStartRowInput = ref(2)
const currentStep = ref(1)
const activeImportRunFilter = ref('all')
const activeDryRunDedupRiskOnly = ref(false)
const dryRunPage = ref(1)
const importRunPage = ref(1)
const linkedSummaryPage = ref(1)
const isStepSevenDryRunExpanded = ref(false)
const busyAction = ref('')
const cancelRequested = ref(false)
const skippedDedupStep = ref(false)
const importExecutionStage = ref<'idle' | 'sample-preview' | 'duplicate-decisions' | 'running'>('idle')
const errorMessage = ref('')
const successMessage = ref('')
const expandedTextBlocks = ref<Record<string, boolean>>({})
const recentSessions = ref<Record<string, any>[]>([])
const historyLoadError = ref('')
const currentView = ref<'wizard' | 'history'>('wizard')

function isBulkAttachSessionSnapshot(snapshot: Record<string, any> | null | undefined) {
  const normalizedSourceFormat = String(snapshot?.source_format || '').trim().toLowerCase()
  const normalizedEntityType = String(snapshot?.entity_type || '').trim().toLowerCase()
  const summary = snapshot?.summary && typeof snapshot.summary === 'object' ? snapshot.summary : {}
  const bulkAttachSummary = summary.bulk_attach && typeof summary.bulk_attach === 'object'
    ? summary.bulk_attach
    : null

  return normalizedSourceFormat === 'bulk_attach'
    || normalizedEntityType.startsWith('crm_files_')
    || Boolean(bulkAttachSummary)
}
const activeRunningSession = computed(() =>
  recentSessions.value.find(s => String(s?.status || '').trim().toLowerCase() === 'running') ?? null
)
const activeRunningSessionId = computed(() => String(activeRunningSession.value?.id || activeRunningSession.value?.session_id || '').trim())
const currentSessionId = computed(() => String(session.value?.id || session.value?.session_id || '').trim())
const isViewingActiveRunningSession = computed(() => (
  Boolean(activeRunningSessionId.value && currentSessionId.value && activeRunningSessionId.value === currentSessionId.value)
))
const isBlockedByActiveSession = computed(() =>
  Boolean(activeRunningSessionId.value && !isViewingActiveRunningSession.value)
)
const restoringHistorySessionId = ref('')
const isRestoringImporterSession = ref(false)

function isValidPerRowDedupDecision(value: unknown): value is string {
  return PER_ROW_DEDUP_DECISION_VALUES.has(String(value || '').trim().toLowerCase())
}

function createDefaultDedupState(): { strategy: string, condition: 'any' | 'all', fields: string[] } {
  return {
    strategy: 'create',
    condition: 'any',
    fields: [],
  }
}

function normalizeDedupState(input: Record<string, any> | null | undefined) {
  const normalizedStrategy = String(input?.strategy || 'create').trim().toLowerCase()
  return {
    strategy: ['create', 'update', 'skip', 'ask'].includes(normalizedStrategy) ? normalizedStrategy : 'create',
    condition: String(input?.condition || 'any').trim().toLowerCase() === 'all' ? 'all' as const : 'any' as const,
    fields: Array.from(new Set(
      (Array.isArray(input?.fields) ? input.fields : [])
        .map((field) => String(field || '').trim())
        .filter(Boolean),
    )),
  }
}

function normalizePerRowEntityDecision(value: unknown): string {
  return isValidPerRowDedupDecision(value) ? String(value || '').trim().toLowerCase() : ''
}

function getPendingDecisionLinkedEntityIds(row: Record<string, any> | null | undefined) {
  const linkedSummary = row?.linked && typeof row.linked === 'object' ? row.linked : {}
  return Object.entries(linkedSummary)
    .filter(([, meta]) => (
      meta
      && typeof meta === 'object'
      && Array.isArray((meta as Record<string, any>).duplicate_match_fields)
      && (meta as Record<string, any>).duplicate_match_fields.length > 0
    ))
    .map(([entityId]) => String(entityId || '').trim().toLowerCase())
    .filter(Boolean)
}

function getPerRowDedupDecision(rowNumber: string, entityId = ''): string {
  const rowDecision = perRowDedupDecisions.value[String(rowNumber || '')]
  const normalizedEntityId = String(entityId || '').trim().toLowerCase()

  if (!normalizedEntityId) {
    return normalizePerRowEntityDecision(rowDecision)
  }

  if (rowDecision && typeof rowDecision === 'object' && !Array.isArray(rowDecision)) {
    return normalizePerRowEntityDecision((rowDecision as Record<string, any>)[normalizedEntityId])
  }

  return normalizePerRowEntityDecision(rowDecision)
}

function getPendingDecisionMatchFieldsLabel(row: Record<string, any> | null | undefined, entityId = ''): string {
  const normalizedEntityId = String(entityId || '').trim().toLowerCase()
  const rawFieldIds = normalizedEntityId
    ? (Array.isArray(row?.linked?.[normalizedEntityId]?.duplicate_match_fields) ? row.linked[normalizedEntityId].duplicate_match_fields : [])
    : (Array.isArray(row?.duplicate_match_fields) ? row.duplicate_match_fields : [])

  if (!rawFieldIds.length) {
    return normalizedEntityId ? 'Совпадение найдено' : '—'
  }

  const linkedEntityGroup = normalizedEntityId
    ? linkedDedupEntityGroups.value.find((item) => item.id === normalizedEntityId)
    : null
  const prefix = String(linkedEntityGroup?.prefix || '').trim().toUpperCase()
  const labels = rawFieldIds
    .map((fieldId) => String(fieldId || '').trim())
    .filter(Boolean)
    .map((fieldId) => resolveImporterFieldLabel(prefix ? `${prefix}${fieldId}` : fieldId))
    .filter(Boolean)

  return labels.length ? labels.join(', ') : (normalizedEntityId ? 'Совпадение найдено' : '—')
}

function setPerRowDedupDecision(rowNumber: string, entityId: string, decision: string) {
  const normalizedRowNumber = String(rowNumber || '').trim()
  const normalizedEntityId = String(entityId || '').trim().toLowerCase()
  const normalizedDecision = normalizePerRowEntityDecision(decision)
  if (!normalizedRowNumber || !normalizedEntityId || !normalizedDecision) {
    return
  }

  const currentRowDecision = perRowDedupDecisions.value[normalizedRowNumber]
  const nextRowDecision = currentRowDecision && typeof currentRowDecision === 'object' && !Array.isArray(currentRowDecision)
    ? { ...(currentRowDecision as Record<string, any>) }
    : {}

  nextRowDecision[normalizedEntityId] = normalizedDecision
  perRowDedupDecisions.value = {
    ...perRowDedupDecisions.value,
    [normalizedRowNumber]: nextRowDecision,
  }
}

function applyBulkPerRowDedupDecision(decision: string) {
  const normalizedDecision = normalizePerRowEntityDecision(decision)
  if (!normalizedDecision) {
    return
  }

  const nextDecisions = { ...perRowDedupDecisions.value }
  pendingDecisionRows.value.forEach((row: Record<string, any>) => {
    const rowNumber = String(row?.row_number || '').trim()
    if (!rowNumber) {
      return
    }

    const linkedEntityIds = getPendingDecisionLinkedEntityIds(row)
    if (linkedEntityIds.length) {
      const currentRowDecision = nextDecisions[rowNumber]
      const nextRowDecision = currentRowDecision && typeof currentRowDecision === 'object' && !Array.isArray(currentRowDecision)
        ? { ...(currentRowDecision as Record<string, any>) }
        : {}

      linkedEntityIds.forEach((entityId) => {
        nextRowDecision[entityId] = normalizedDecision
      })
      nextDecisions[rowNumber] = nextRowDecision
      return
    }

    nextDecisions[rowNumber] = normalizedDecision
  })

  perRowDedupDecisions.value = nextDecisions
}

function rowHasUnresolvedPendingDedupDecision(row: Record<string, any> | null | undefined) {
  const rowNumber = String(row?.row_number || '').trim()
  if (!rowNumber) {
    return false
  }

  const linkedEntityIds = getPendingDecisionLinkedEntityIds(row)
  if (linkedEntityIds.length > 0) {
    return linkedEntityIds.some((entityId) => !getPerRowDedupDecision(rowNumber, entityId))
  }

  return !getPerRowDedupDecision(rowNumber)
}

function getRowNumberDisplayValue(row: { rowNumber?: number, rowNumberLabel?: string } | null | undefined) {
  return String(row?.rowNumberLabel || row?.rowNumber || '—')
}

function hasLinkedEntityTree(row: DryRunRow | ImportRunRow | null | undefined) {
  return Boolean(row?.entityTree?.primary)
}

function getLinkedEntityTreeStatusClass(status: string) {
  const normalizedStatus = String(status || '').trim().toLowerCase()
  if (['created', 'ready'].includes(normalizedStatus)) {
    return 'border-[#cfe5d8] bg-[#edf7f0] text-[#1a7f3c]'
  }
  if (['updated', 'ready_update', 'existing'].includes(normalizedStatus)) {
    return 'border-[#d7e7ff] bg-[#edf5ff] text-[#2e6bd9]'
  }
  if (['pending_decision'].includes(normalizedStatus)) {
    return 'border-[#ffe1c7] bg-[#fff7ef] text-[#c77d2b]'
  }
  if (['failed', 'skipped', 'skipped_duplicate', 'cancelled'].includes(normalizedStatus)) {
    return 'border-[#f1d4d7] bg-[#fff5f5] text-[#c24b53]'
  }

  return 'border-[#d9e2ec] bg-[#f4f7fa] text-[#516478]'
}

function getLinkedEntityTreeRowNumbersLabel(item: LinkedEntityTreeItem | null | undefined) {
  return Array.isArray(item?.rowNumbers) && item.rowNumbers.length
    ? item.rowNumbers.join(', ')
    : '—'
}

function hasExecutionRowHeading(row: DryRunRow | ImportRunRow | null | undefined) {
  return Boolean(String((row as any)?.entityLabel || '').trim() || String((row as any)?.title || '').trim())
}

function buildCurrentDedupPayload() {
  if (isLinkedImportEntityType(entityType.value)) {
    const filteredLinked = Object.fromEntries(
      Object.entries(linkedDedupSettings.value).map(([entityId, settings]: [string, any]) => {
        const allowedIds = new Set((linkedDedupFieldOptions.value[entityId] || []).map((opt: any) => opt.id))
        return [entityId, {
          ...settings,
          fields: (Array.isArray(settings?.fields) ? settings.fields : []).filter((f: any) => allowedIds.has(String(f || ''))),
        }]
      }),
    )
    return buildDedupPayload(filteredLinked)
  }

  return buildDedupPayload({
    strategy: dedupStrategy.value,
    fields: effectiveDedupFields.value,
    condition: dedupCondition.value,
  })
}

function normalizeDedupPayloadForCompare(payload: Record<string, any> | null | undefined): Record<string, any> {
  if (!payload || typeof payload !== 'object') {
    return {}
  }

  const linkedEntityGroups = buildLinkedImportEntityGroups(entityType.value)
  const linkedEntityIds = linkedEntityGroups.map((item) => String(item.id || '').trim()).filter(Boolean)
  if (linkedEntityIds.length > 0 && linkedEntityIds.some((entityId) => payload[entityId] && typeof payload[entityId] === 'object')) {
    return linkedEntityIds.reduce((result, entityId) => {
      result[entityId] = normalizeDedupPayloadForCompare(payload[entityId])
      return result
    }, {} as Record<string, any>)
  }

  return {
    strategy: String(payload.strategy || '').trim(),
    condition: String(payload.condition || '').trim(),
    fields: [...(Array.isArray(payload.fields) ? payload.fields : [])]
      .map((field) => String(field || '').trim())
      .filter(Boolean)
      .sort(),
  }
}

const importerPermissionState = computed(() => buildImporterPermissionState({
  role: userStore.importerRole,
  permissions: userStore.importerPermissions,
  isPortalAdmin: userStore.importerIsPortalAdmin,
}))
const hasNoImporterAccess = computed(() => (
  importerPermissionState.value.role === 'none'
  && importerPermissionState.value.permissions.length === 0
  && !importerPermissionState.value.isPortalAdmin
))

const historyRows = computed(() => buildSessionHistoryRows(recentSessions.value))
const fileName = computed(() => selectedFile.value?.name || String(session.value?.original_filename || ''))
const sourceFormat = computed(() => (
  detectSourceFormat(fileName.value)
  || String(session.value?.source_format || '').trim()
))
const importModeOptions = computed(() => buildImportModeOptions())
const importModeMeta = computed(() => getImportModeMeta(importMode.value))
const isSimpleImportMode = computed(() => importModeMeta.value.value === 'simple')
const showsAdvancedImportTools = computed(() => !importModeMeta.value.hidesAdvancedTools)
const scenarioSections = computed(() => buildImportScenarioSections())
const crmScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'crm')?.items || [])
const taskScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'task')?.items || [])
const linkedScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'linked')?.items || [])
const linkedPrimaryEntityItems = computed(() => buildLinkedPrimaryEntityOptions())
const linkedSecondaryEntityItems = computed(() => buildLinkedSecondaryEntityOptions(selectedLinkedPrimaryEntityType.value))
const hrScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'hr')?.items || [])
const fileAttachCrmEntityItems = computed(() =>
  Object.values(FILE_ATTACH_IMPORT_SCENARIOS).map((s) => ({ value: s.value, label: s.entityLabel })),
)
const isFileAttachMode = computed(() => String(entityType.value || '').startsWith('crm_files_'))
const isTaskBulkAttachFlow = computed(() => (
  selectedFamily.value === 'task'
  && entityType.value === 'task_attachment'
))
const selectedBulkAttachEntityType = computed(() => (
  isTaskBulkAttachFlow.value
    ? 'task'
    : String(selectedFileAttachEntityType.value || '').replace(/^crm_files_/, '')
))
const currentScenarioSummary = computed(() => buildScenarioSelectionSummary(entityType.value))
const isTaskEntityImport = computed(() => entityType.value === 'task')
const isDirectCrmEntityImport = computed(() => ['lead', 'contact', 'company', 'deal'].includes(entityType.value))
const DEDUP_NONAPPLICABLE_TYPES = new Set([
  'task', 'task_comment', 'task_checklist_item', 'task_attachment',
  'crm_files_lead', 'crm_files_contact', 'crm_files_company', 'crm_files_deal',
  'crm_activity', 'crm_note', 'department', 'user',
])
const isDedupApplicable = computed(() => !DEDUP_NONAPPLICABLE_TYPES.has(entityType.value))
const linkedDedupEntityGroups = computed(() => buildLinkedImportEntityGroups(entityType.value))
const simpleDedupPreset = computed(() => buildSimpleDedupPreset({
  entityType: entityType.value,
  mappingRows: mappingRows.value,
}))
const exampleTemplateDownloadMeta = computed(() => buildExampleTemplateDownloadMeta(entityType.value))
const currentImportTitle = computed(() => 'Excel Migration')
const selectedFamily = ref('')
const crmFlavor = ref<'direct' | 'linked' | 'bulk'>('direct')
const domainAccent = computed(() => {
  const p: Record<string, { bg: string; ink: string }> = {
    crm:  { bg: '#EEF2FF', ink: '#3B47D6' },
    task: { bg: '#FFF1E8', ink: '#D8632A' },
    hr:   { bg: '#E8F6EE', ink: '#1E8A52' },
  }
  return p[selectedFamily.value] ?? p.crm
})
const selectedCrmEntityType = ref('')
const selectedTaskEntityType = ref('')
const selectedLinkedPrimaryEntityType = ref('')
const selectedLinkedSecondaryEntityType = ref('')
const selectedHrEntityType = ref('')
const selectedFileAttachEntityType = ref('')
const selectedBulkFileField = ref('')
const bulkFileFields = ref<{ value: string; label: string }[]>([])
const loadingBulkFileFields = ref(false)
const bulkEntityFields = ref<{ id: string; title: string; type: string; items: { value: string; label: string }[] }[]>([])
const bulkFilterPreview = ref<{ total: number; sample: { id: number; title: string }[] } | null>(null)
const loadingBulkFilterPreview = ref(false)
const bulkFilterConditions = ref<{ fieldId: string; value: string }[]>([])
const bulkAttachSessionId = ref('')
const bulkAttachSessionStatus = ref('')
const bulkAttachResultTotal = ref(0)
const bulkAttachResultSuccessful = ref(0)
const bulkAttachResultFailed = ref(0)
const bulkAttachProgressProcessed = ref(0)
const bulkAttachProgressTotal = ref(0)
const bulkAttachPollingHandle = ref<ReturnType<typeof setInterval> | null>(null)
const isAddingBulkFilterField = ref(false)
const pendingBulkFilterFieldId = ref('')
const dropzoneDragOver = ref(false)
const smartProcesses = ref<Record<string, any>[]>([])
const loadingSmartProcesses = ref(false)
const selectedSmartProcessId = ref('')
const departments = ref<{ id: string, name: string, parent_id: string | null }[]>([])
const loadingDepartments = ref(false)
const departmentsExpanded = ref(false)
const smartProcessOptions = computed(() => (
  smartProcesses.value.map((item) => ({
    value: String(item?.entityTypeId || ''),
    label: String(item?.title || `Smart Process ${String(item?.entityTypeId || '')}`),
  }))
))
const selectedSmartProcessConfig = computed(() => {
  if (entityType.value !== 'smart_process') {
    return null
  }

  const normalizedId = Number.parseInt(String(selectedSmartProcessId.value || '').trim(), 10)
  if (!Number.isInteger(normalizedId) || normalizedId <= 0) {
    return null
  }

  const matched = smartProcesses.value.find((item) => Number(item?.entityTypeId || 0) === normalizedId)
  return {
    entityTypeId: normalizedId,
    ...(matched?.title ? { title: String(matched.title) } : {}),
  }
})
const fieldOptions = computed(() => Array.isArray(mappingData.value?.fields) ? mappingData.value.fields : [])
const fieldOptionsIndex = computed(() => new Map(
  fieldOptions.value
    .filter((field: Record<string, any>) => String(field?.id || '').trim().length > 0)
    .map((field: Record<string, any>) => [String(field.id || ''), field]),
))
const normalizedFieldOptionsIndex = computed(() => new Map(
  fieldOptions.value
    .filter((field: Record<string, any>) => String(field?.id || '').trim().length > 0)
    .map((field: Record<string, any>) => [String(field.id || '').trim().toUpperCase(), field]),
))
const previewRows = computed(() => Array.isArray(preview.value?.preview_rows) ? preview.value.preview_rows : [])
const previewColumnsSource = computed(() => Array.isArray(preview.value?.columns) ? preview.value.columns : [])
const previewTotalRows = computed(() => Number(preview.value?.total_rows || session.value?.total_rows || 0))
const previewMaxImportRows = computed(() => Number(preview.value?.max_import_rows || 0))
const previewRowLimitExceeded = computed(() => Boolean(preview.value?.row_limit_exceeded))
const previewRowLimitError = computed(() => String(preview.value?.row_limit_error || '').trim())
const sessionSavedMapping = computed(() => (
  mappingData.value?.saved_mapping && typeof mappingData.value.saved_mapping === 'object'
    ? mappingData.value.saved_mapping
    : {}
))
const effectiveSavedMapping = computed(() => sessionSavedMapping.value)
const mappingSavedCount = computed(() => (
  sessionSavedMapping.value && typeof sessionSavedMapping.value === 'object'
    ? Object.keys(sessionSavedMapping.value).length
    : 0
))
const requiredFieldSummary = computed(() => buildRequiredFieldSummary({
  fields: mappingData.value?.fields,
  mappingRows: mappingRows.value,
  defaultFieldIds: [
    ...(taskDefaultResponsibleId.value ? ['RESPONSIBLE_ID'] : []),
    ...(taskDefaultCreatorId.value ? ['CREATED_BY'] : []),
    ...(taskDefaultCommentAuthorId.value ? ['AUTHOR_ID'] : []),
  ],
  ignoreFieldIds: entityType.value === 'contact' ? ['SECOND_NAME'] : [],
}))
const effectiveDedupFields = computed(() => {
  if (isLinkedImportEntityType(entityType.value)) {
    return []
  }

  const mappedFieldIds = new Set(
    (Array.isArray(mappingRows.value) ? mappingRows.value : [])
      .map((row) => String(row?.targetFieldId || '').trim().toUpperCase())
      .filter((id) => id && /^[A-Z][A-Z0-9_]*$/.test(id)),
  )

  if (!isSimpleImportMode.value) {
    return dedupFields.value.filter((fieldId) => mappedFieldIds.has(String(fieldId || '').toUpperCase()))
  }

  if (dedupStrategy.value === 'create') {
    return []
  }

  const filtered = dedupFields.value.filter((fieldId) => mappedFieldIds.has(String(fieldId || '').toUpperCase()))
  return filtered.length ? filtered : simpleDedupPreset.value.fields
})
const simpleDedupFieldLabels = computed(() => (
  effectiveDedupFields.value
    .map((fieldId) => resolveImporterFieldLabel(fieldId))
    .filter(Boolean)
))
const bulkFilterFieldOptions = computed(() => (
  bulkEntityFields.value
    .filter((field) => !bulkFilterConditions.value.some((condition) => condition.fieldId === field.id))
    .map((field) => ({
      value: field.id,
      label: field.title,
    }))
))
const linkedDedupFieldOptions = computed(() => linkedDedupEntityGroups.value.reduce((result, group) => {
  const prefix = String(group.prefix || '').trim().toUpperCase()
  result[group.id] = dedupFieldOptions.value
    .filter((item) => String(item.id || '').trim().toUpperCase().startsWith(prefix))
    .map((item) => ({
      id: String(item.id || '').trim().slice(prefix.length),
      label: String(item.label || '').trim(),
      hint: item.hint,
    }))
  return result
}, {} as Record<string, Array<{ id: string, label: string, hint?: string }>>))
const requiredFieldMissingIds = computed(() => new Set(
  requiredFieldSummary.value.missingRequired.map((field) => field.id),
))
const mappingPreflight = computed(() => {
  const payload = mappingData.value?.preflight
  if (payload && typeof payload === 'object') {
    return payload
  }
  return {
    blocking_issue_count: 0,
    warning_count: 0,
    issues: [],
  }
})
const mappingPreflightIssues = computed<Record<string, any>[]>(() => (
  Array.isArray(mappingPreflight.value?.issues) ? mappingPreflight.value.issues : []
))
const hasBlockingPreflightIssues = computed(() => Number(mappingPreflight.value?.blocking_issue_count || 0) > 0)
const isMappingAdvanceBlocked = computed(() => (
  currentStep.value === 4
  && requiredFieldSummary.value.hasMissingRequired
))
const unmappedValueSummary = computed(() => buildUnmappedValueSummary({
  unmappedValues: mappingData.value?.unmapped_values,
  fields: mappingData.value?.fields,
}))
const validationIssueCount = computed(() => Number(validationData.value?.issue_count || 0))
const validationCheckedRows = computed(() => Number(validationData.value?.checked_rows || 0))
const validationValidRows = computed(() => Number(validationData.value?.valid_rows || 0))
const validationInvalidRows = computed(() => Number(validationData.value?.invalid_rows || 0))
const resolvedDryRunData = computed(() => buildResolvedDryRunSummary(dryRunData.value, perRowDedupDecisions.value))
const dryRunCheckedRows = computed(() => Number(resolvedDryRunData.value?.checked_rows || 0))
const dryRunReadyRows = computed(() => Number(resolvedDryRunData.value?.ready_rows || 0))
const dryRunSkippedRows = computed(() => Number(resolvedDryRunData.value?.skipped_rows || 0))
const dryRunPendingDecisionRows = computed(() => Number(resolvedDryRunData.value?.pending_decision_rows || 0))
const requiresPerRowDedupDecision = computed(() => (
  isDedupApplicable.value
  && importModeMeta.value.allowsPerRowDedupDecisions
  && (
    isLinkedImportEntityType(entityType.value)
      ? linkedDedupEntityGroups.value.some((group) => linkedDedupSettings.value[group.id]?.strategy === 'ask')
      : dedupStrategy.value === 'ask'
  )
))
const pendingDecisionRows = computed(() =>
  (Array.isArray(dryRunData.value?.results) ? dryRunData.value.results : []).filter(
    (r: any) => r?.status === 'pending_decision'
  )
)
const hasUnresolvedPendingDedupDecisions = computed(() => pendingDecisionRows.value.some((row: any) => (
  rowHasUnresolvedPendingDedupDecision(row)
)))
const importRunCheckedRows = computed(() => Number(importRunData.value?.checked_rows || 0))
const importRunCreatedRows = computed(() => Number(importRunData.value?.created_rows || 0))
const importRunUpdatedRows = computed(() => Number(importRunData.value?.updated_rows || 0))
const importRunFailedRows = computed(() => Number(importRunData.value?.failed_rows || 0))
const importRunSkippedRows = computed(() => Number(importRunData.value?.skipped_rows || 0))
const importRunRetryState = computed(() => buildImportRunRetryState(importRunData.value))
const retryTotalRows = computed(() => Number(session.value?.summary?.retry_total_rows || session.value?.total_rows || 0))
const canStart = computed(() => (
  importerPermissionState.value.canCreateSessions
  && Boolean(entityType.value)
  && (entityType.value !== 'smart_process' || Boolean(selectedSmartProcessConfig.value?.entityTypeId))
  && Boolean(selectedFile.value)
  && Boolean(sourceFormat.value)
  && !busyAction.value
))
const canDownloadExampleTemplate = computed(() => (
  importerPermissionState.value.canCreateSessions
  && Boolean(entityType.value)
  && entityType.value !== 'task_attachment'
  && (entityType.value !== 'smart_process' || Boolean(selectedSmartProcessConfig.value?.entityTypeId))
  && !busyAction.value
))
const isSpreadsheetUploadRequired = computed(() => !isBulkAttachFlow.value)
const currentFilePickerHelperText = computed(() => (
  isBulkAttachFlow.value ? BULK_ATTACH_FILE_PICKER_HELPER_TEXT : IMPORT_FILE_PICKER_HELPER_TEXT
))
const currentFileDropdownLimitText = computed(() => (
  isBulkAttachFlow.value ? BULK_ATTACH_FILE_DROPDOWN_LIMIT_TEXT : IMPORT_FILE_DROPDOWN_LIMIT_TEXT
))
const canApplyStructure = computed(() => (
  importerPermissionState.value.canEditSessions
  && Boolean(session.value?.id)
  && Boolean(preview.value)
  && !busyAction.value
))
const canSaveMapping = computed(() => (
  importerPermissionState.value.canEditSessions
  && Boolean(session.value?.id)
  && Boolean(mappingData.value)
  && !busyAction.value
))
const canSaveDedup = computed(() => (
  importerPermissionState.value.canEditSessions
  && Boolean(session.value?.id)
  && Boolean(mappingData.value)
  && !busyAction.value
))
const canSaveTemplate = computed(() => (
  importerPermissionState.value.canManageTemplates
  && importerPermissionState.value.canEditSessions
  && Boolean(session.value?.id)
  && templateNameInput.value.trim().length > 0
  && mappingSavedCount.value > 0
  && !busyAction.value
))
const canApplyTemplate = computed(() => (
  importerPermissionState.value.canManageTemplates
  && importerPermissionState.value.canEditSessions
  && Boolean(session.value?.id)
  && selectedTemplateId.value.trim().length > 0
  && Boolean(mappingData.value)
  && !busyAction.value
))
const currentDedupSettingsPayload = computed(() => buildCurrentDedupPayload())
const savedDedupSettingsPayload = computed(() => buildDedupPayload(mappingData.value?.saved_dedup || {}))
const hasPendingDedupChanges = computed(() => (
  JSON.stringify(normalizeDedupPayloadForCompare(currentDedupSettingsPayload.value))
    !== JSON.stringify(normalizeDedupPayloadForCompare(savedDedupSettingsPayload.value))
))
const canRunValidation = computed(() => (
  importerPermissionState.value.canRunSessions
  && Boolean(session.value?.id)
  && mappingSavedCount.value > 0
  && !unmappedValueSummary.value.hasUnmappedValues
  && !previewRowLimitExceeded.value
  && !hasBlockingPreflightIssues.value
  && !busyAction.value
))
const canRunImport = computed(() => (
  importerPermissionState.value.canRunSessions
  && Boolean(session.value?.id)
  && Boolean(validationData.value)
  && Boolean(preimportScanData.value)
  && !hasBlockingPreflightIssues.value
  && !busyAction.value
))
const canCancelActiveImport = computed(() => (
  importerPermissionState.value.canCancelSessions
  && Boolean(session.value?.id)
  && !cancelRequested.value
  && ['run', 'retry', 'sample-preview'].includes(String(busyAction.value || '').trim())
))
const canRetryFailedRows = computed(() => (
  importerPermissionState.value.canRunSessions
  && Boolean(session.value?.id)
  && Boolean(importRunData.value)
  && importRunRetryState.value.hasRetryableRows
  && !busyAction.value
))
const canDownloadImportReport = computed(() => (
  importerPermissionState.value.canViewReports
  && Boolean(session.value?.id)
  && Boolean(importRunData.value)
  && !busyAction.value
))
const maxAvailableStep = computed(() => {
  if (importRunData.value) {
    return 7
  }

  if (dryRunData.value || (!isDedupApplicable.value && validationData.value)) {
    return 6
  }

  if (mappingData.value) {
    return 5
  }

  if (preview.value) {
    return 3
  }

  if (session.value?.id) {
    return 2
  }

  return 1
})
const sessionJobMode = computed(() => String(session.value?.summary?.job?.mode || '').trim())
const importJobState = computed(() => String(session.value?.summary?.job?.state || '').trim())
const showsSessionProgress = computed(() => (
  ['run', 'retry'].includes(String(busyAction.value || '').trim())
))
const sessionProgressPercent = computed(() => (
  session.value?.total_rows
    ? Math.min(100, Math.round(((session.value?.processed_rows ?? 0) / session.value.total_rows) * 100))
    : 0
))
const sessionProgressTitle = computed(() => (
  busyAction.value === 'retry'
    ? 'Повтор импорта'
    : 'Выполнение импорта'
))
const executionProgressProcessedRows = computed(() => (
  importExecutionStage.value === 'duplicate-decisions' && dryRunData.value
    ? Number(dryRunData.value?.checked_rows || 0)
    : Number(session.value?.processed_rows || 0)
))
const executionProgressTotalRows = computed(() => {
  if (busyAction.value === 'retry') {
    return retryTotalRows.value
  }

  if (importExecutionStage.value === 'duplicate-decisions' && dryRunData.value) {
    return Number(dryRunData.value?.full_total_rows || dryRunData.value?.checked_rows || session.value?.total_rows || 0)
  }

  return Number(session.value?.total_rows || 0)
})
const executionProgressPercent = computed(() => (
  executionProgressTotalRows.value > 0
    ? Math.min(100, Math.round((executionProgressProcessedRows.value / executionProgressTotalRows.value) * 100))
    : 0
))
const executionProgressTitle = computed(() => {
  if (showsSessionProgress.value) {
    return sessionProgressTitle.value
  }

  if (importExecutionStage.value === 'duplicate-decisions') {
    return 'Тестовый импорт завершён'
  }

  return dedupProgressTitle.value
})
const executionProgressCounterLabel = computed(() => (
  busyAction.value === 'sample-preview'
    ? `${executionProgressProcessedRows.value} из ${executionProgressTotalRows.value || '...'} строк файла`
    : importExecutionStage.value === 'duplicate-decisions'
      ? `${executionProgressProcessedRows.value} из ${executionProgressTotalRows.value || '...'} строк файла`
      : `${executionProgressProcessedRows.value} из ${executionProgressTotalRows.value || '...'} строк`
))
const showsDedupProgress = computed(() => (
  ['dedup', 'validation', 'sample-preview'].includes(String(busyAction.value || '').trim())
))
const dedupProgressTitle = computed(() => {
  if (busyAction.value === 'sample-preview') {
    return 'Тестовый импорт'
  }
  if (busyAction.value === 'dedup') {
    return 'Сохраняем правила дублей'
  }

  return 'Проверяем данные перед следующим шагом'
})
const dedupProgressDescription = computed(() => {
  if (busyAction.value === 'sample-preview') {
    return 'Тестовый импорт проверяет весь файл и заранее показывает, что будет создано, обновлено или потребует решения по дублям.'
  }
  if (busyAction.value === 'dedup') {
    return 'Сохраняем текущие правила, чтобы следующий запуск использовал актуальные настройки.'
  }

  return 'На больших файлах проверка может занять время. После завершения обновим экран автоматически.'
})
const currentStepMeta = computed(() => {
  const items: Record<number, { eyebrow: string, title: string, description: string }> = {
    1: {
      eyebrow: 'Шаг 1 · Настройки',
      title: 'Файл и назначение',
      description: 'Выберите сценарий импорта, файл и базовые настройки запуска.',
    },
    2: {
      eyebrow: 'Шаг 2 · Структура',
      title: 'Параметры чтения файла',
      description: 'Проверьте строки заголовков, начало данных и структуру листа.',
    },
    3: {
      eyebrow: 'Шаг 3 · Предпросмотр',
      title: 'Пример файла',
      description: 'Просмотрите первые строки файла перед сопоставлением полей.',
    },
    4: {
      eyebrow: 'Шаг 4 · Соответствие',
      title: 'Соответствие полей',
      description: 'Сопоставьте колонки файла с полями Bitrix24.',
    },
    5: {
      eyebrow: 'Шаг 5 · Дубли',
      title: 'Обработка дублей',
      description: 'Настройте правила поиска и обработки дублей.',
    },
    6: {
      eyebrow: 'Шаг 6 · Тестовый импорт',
      title: 'Тестовый импорт и запуск',
      description: 'Проверьте результаты тестового прогона перед основным запуском.',
    },
    7: {
      eyebrow: 'Шаг 7 · Результат',
      title: 'Результат импорта',
      description: 'Проверьте итоговую статистику и завершите сценарий.',
    },
  }

  return items[currentStep.value] || items[1]
})
const isBulkAttachFlow = computed(() => (
  (selectedFamily.value === 'crm' && crmFlavor.value === 'bulk')
  || isTaskBulkAttachFlow.value
))
const bulkFlowStep = computed<BulkFlowStep>(() => {
  if (showBulkAttachExecutionState.value) return 'execution'
  if (bulkFilterPreview.value) return 'review'
  return 'setup'
})
const bulkFlowStepMeta = computed(() => {
  const items: Record<BulkFlowStep, { eyebrow: string, title: string, description: string }> = {
    setup: {
      eyebrow: 'Шаг 1 · Назначение',
      title: 'Назначение',
      description: isTaskBulkAttachFlow.value
        ? 'Настройте фильтр задач и подготовьте один файл-вложение.'
        : 'Выберите CRM-сущность, поле для файлов и настройте фильтр отбора.',
    },
    review: {
      eyebrow: 'Шаг 2 · Файл и выборка',
      title: 'Файл и выборка',
      description: isTaskBulkAttachFlow.value
        ? 'Проверьте найденные задачи и подготовьте массовое добавление вложения.'
        : 'Загрузите файл, проверьте найденные записи и подготовьте массовую загрузку.',
    },
    execution: {
      eyebrow: 'Шаг 3 · Загрузка',
      title: isTaskBulkAttachFlow.value ? 'Загрузка вложений' : 'Загрузка файлов',
      description: isTaskBulkAttachFlow.value
        ? 'Следите за прогрессом прикрепления файла к найденным задачам.'
        : 'Следите за прогрессом загрузки, при необходимости остановите импорт и завершите сценарий.',
    },
  }

  return items[bulkFlowStep.value]
})
const selectedFamilyHeaderMeta = computed(() => {
  if (isBulkAttachFlow.value) {
    return bulkFlowStepMeta.value
  }

  return {
    eyebrow: 'Шаг 1 · Настройки',
    title: 'Источник и назначение',
    description: 'Выберите способ импорта и загрузите файл.',
  }
})
const selectedFamilyHeaderStatusMeta = computed(() => {
  if (!isBulkAttachFlow.value) {
    return {
      dotClass: 'bg-[#E8B53A]',
      label: 'Ожидает запуска',
    }
  }

  if (busyAction.value === 'bulk-attach-cancel') {
    return {
      dotClass: 'bg-[#D8632A]',
      label: 'Останавливаем загрузку',
    }
  }

  if (isBulkAttachExecutionLocked.value) {
    return {
      dotClass: 'bg-[#3B47D6]',
      label: 'Загрузка выполняется',
    }
  }

  if (bulkAttachSessionStatus.value === 'completed') {
    return {
      dotClass: 'bg-[#1E8A52]',
      label: 'Загрузка завершена',
    }
  }

  if (bulkAttachSessionStatus.value === 'cancelled') {
    return {
      dotClass: 'bg-[#D8632A]',
      label: 'Загрузка остановлена',
    }
  }

  if (bulkAttachSessionStatus.value === 'failed') {
    return {
      dotClass: 'bg-[#C24B53]',
      label: 'Есть ошибка загрузки',
    }
  }

  if (bulkFlowStep.value === 'review') {
    return {
      dotClass: 'bg-[#E8B53A]',
      label: 'Готово к запуску',
    }
  }

  return {
    dotClass: 'bg-[#E8B53A]',
    label: 'Ожидает запуска',
  }
})
const canGoBack = computed(() => currentStep.value > 1)
const wizardAdvanceMode = computed(() => getWizardAdvanceMode(currentStep.value, maxAvailableStep.value))
const canGoNext = computed(() => {
  if (currentStep.value === 5 && hasUnresolvedPendingDedupDecisions.value) {
    return false
  }

  return canAdvanceWizard(currentStep.value, maxAvailableStep.value, {
    hasMissingRequiredFields: requiredFieldSummary.value.hasMissingRequired,
  })
})
const nextStepLabel = computed(() => getWizardNextLabel(currentStep.value))
function normalizeMappingPayloadForCompare(payload: Record<string, any> | null | undefined) {
  const safePayload = payload && typeof payload === 'object' ? payload : {}

  return Object.keys(safePayload)
    .sort((left, right) => left.localeCompare(right))
    .reduce((normalized: Record<string, any>, fieldId) => {
      const item = safePayload[fieldId] && typeof safePayload[fieldId] === 'object' ? safePayload[fieldId] : {}
      const normalizedItem: Record<string, any> = {
        source_header: String(item.source_header || ''),
        column: String(item.column || ''),
        target_field: String(item.target_field || fieldId),
      }
      const columnType = String(item.column_type || '').trim().toLowerCase()
      if (columnType) {
        normalizedItem.column_type = columnType
      }

      const valueMappingSource = item.value_mapping && typeof item.value_mapping === 'object' ? item.value_mapping : {}
      const normalizedValueMapping = Object.keys(valueMappingSource)
        .sort((left, right) => left.localeCompare(right))
        .reduce((mapping: Record<string, string>, sourceValue) => {
          mapping[sourceValue] = String(valueMappingSource[sourceValue] || '')
          return mapping
        }, {})

      if (Object.keys(normalizedValueMapping).length > 0) {
        normalizedItem.value_mapping = normalizedValueMapping
      }

      normalized[fieldId] = normalizedItem
      return normalized
    }, {})
}

function normalizeTaskDefaultsForCompare(taskDefaults: Record<string, any> | null | undefined) {
  const safeTaskDefaults = taskDefaults && typeof taskDefaults === 'object' ? taskDefaults : {}
  return {
    default_responsible_id: String(safeTaskDefaults.default_responsible_id || ''),
    default_creator_id: String(safeTaskDefaults.default_creator_id || ''),
    default_comment_author_id: String(safeTaskDefaults.default_comment_author_id || ''),
  }
}

const currentMappingPayload = computed(() => normalizeMappingPayloadForCompare(buildMappingPayload(mappingRows.value)))
const savedMappingPayload = computed(() => normalizeMappingPayloadForCompare(sessionSavedMapping.value))
const currentTaskDefaultsPayload = computed(() => normalizeTaskDefaultsForCompare({
  default_responsible_id: taskDefaultResponsibleId.value,
  default_creator_id: taskDefaultCreatorId.value,
  default_comment_author_id: taskDefaultCommentAuthorId.value,
}))
const savedTaskDefaultsPayload = computed(() => normalizeTaskDefaultsForCompare(mappingData.value?.task_defaults))
const hasPendingMappingChanges = computed(() => (
  JSON.stringify(currentMappingPayload.value) !== JSON.stringify(savedMappingPayload.value)
  || JSON.stringify(currentTaskDefaultsPayload.value) !== JSON.stringify(savedTaskDefaultsPayload.value)
))
const canGoNextFromMapping = computed(() => !hasPendingMappingChanges.value && canGoNext.value)
const importSteps = computed(() => {
  const stepState = (id: number): StepState => {
    if (id < currentStep.value && id <= maxAvailableStep.value) {
      return 'done'
    }

    if (id === currentStep.value) {
      return 'current'
    }

    return 'upcoming'
  }

  return [
    {
      id: 1,
      title: 'Настройки',
      description: 'Назначение и файл',
      state: stepState(1),
    },
    {
      id: 2,
      title: 'Структура',
      description: 'Строки и чтение',
      state: stepState(2),
    },
    {
      id: 3,
      title: 'Предпросмотр',
      description: 'Первые строки',
      state: stepState(3),
    },
    {
      id: 4,
      title: 'Соответствие',
      description: 'Поля Bitrix24',
      state: stepState(4),
    },
    {
      id: 5,
      title: 'Дубли',
      description: 'Правила поиска',
      state: stepState(5),
    },
    {
      id: 6,
      title: 'Тестовый импорт',
      description: 'Проверка и запуск',
      state: stepState(6),
    },
    {
      id: 7,
      title: 'Импорт',
      description: 'Итог запуска',
      state: stepState(7),
    },
  ].map((step) => ({
    ...step,
    enabled: step.id <= maxAvailableStep.value && !(isMappingAdvanceBlocked.value && step.id > currentStep.value),
  }))
})
const bulkImportSteps = computed(() => {
  const currentBulkStepId = bulkFlowStep.value === 'setup'
    ? 1
    : bulkFlowStep.value === 'review'
      ? 2
      : 3
  const stepState = (id: number): StepState => {
    if (id < currentBulkStepId) {
      return 'done'
    }

    if (id === currentBulkStepId) {
      return 'current'
    }

    return 'upcoming'
  }

  return [
    {
      id: 1,
      title: 'Назначение',
      description: 'Сущность, поле и фильтр',
      state: stepState(1),
      enabled: currentBulkStepId >= 1,
    },
    {
      id: 2,
      title: 'Файл и выборка',
      description: 'Файл и найденные записи',
      state: stepState(2),
      enabled: currentBulkStepId >= 2,
    },
    {
      id: 3,
      title: 'Загрузка',
      description: 'Выполнение и результат',
      state: stepState(3),
      enabled: currentBulkStepId >= 3,
    },
  ]
})
const visibleSteps = computed(() => (
  isBulkAttachFlow.value && currentStep.value === 1
    ? bulkImportSteps.value
    : importSteps.value
))
const selectedBulkFileFieldLabel = computed(() => (
  isTaskBulkAttachFlow.value
    ? 'Вложение задачи'
    : (
      bulkFileFields.value.find((field) => field.value === selectedBulkFileField.value)?.label
      || String(selectedBulkFileField.value || '').trim()
      || 'Не выбрано'
    )
))
const sidebarFacts = computed(() => {
  if (isBulkAttachFlow.value && currentStep.value === 1) {
    const selectedRowsTotal = bulkFilterPreview.value?.total || bulkAttachProgressTotal.value || 0
    return [
      { label: isTaskBulkAttachFlow.value ? 'Сценарий' : 'CRM-сущность', value: currentScenarioSummary.value.selectedLabel },
      ...(isTaskBulkAttachFlow.value ? [] : [{ label: 'Поле файла', value: selectedBulkFileFieldLabel.value }]),
      { label: 'Файл', value: fileName.value || 'Не выбран' },
      { label: 'Записей', value: selectedRowsTotal ? String(selectedRowsTotal) : '—' },
    ]
  }

  return [
    { label: 'Назначение', value: currentScenarioSummary.value.selectedLabel },
    { label: 'Файл', value: fileName.value || 'Не выбран' },
    { label: 'Колонки', value: previewColumnsSource.value.length ? String(previewColumnsSource.value.length) : '—' },
    { label: 'Строки', value: previewRows.value.length ? String(previewRows.value.length) : '—' },
  ]
})
const mappingFieldItems = computed(() => buildMappingFieldItems(fieldOptions.value))
const taskDefaultUserOptions = computed(() => (
  Array.isArray(mappingData.value?.task_user_options) ? mappingData.value.task_user_options : []
))
const showsTaskDefaultResponsible = computed(() => entityType.value === 'task')
const showsTaskDefaultCreator = computed(() => entityType.value === 'task')
const showsTaskCommentDefaultAuthor = computed(() => entityType.value === 'task_comment')
const templateItems = computed(() => importTemplates.value.map((template) => ({
  value: template.id,
  label: template.name,
})))
const migrationStatusBadge = computed(() => buildMigrationStatusBadge({
  sessionId: session.value?.id,
  busyAction: busyAction.value,
  errorMessage: errorMessage.value,
  validationIssueCount: validationIssueCount.value,
  importRunFailedRows: importRunFailedRows.value,
}))
const currentStepHeaderStatusMeta = computed(() => {
  if (migrationStatusBadge.value.tone === 'busy') {
    return {
      dotClass: 'bg-[#3B47D6]',
      label: migrationStatusBadge.value.label,
    }
  }

  if (migrationStatusBadge.value.tone === 'ok') {
    return {
      dotClass: 'bg-[#1E8A52]',
      label: migrationStatusBadge.value.label,
    }
  }

  if (migrationStatusBadge.value.tone === 'error') {
    return {
      dotClass: 'bg-[#C24B53]',
      label: migrationStatusBadge.value.label,
    }
  }

  return {
    dotClass: 'bg-[#E8B53A]',
    label: migrationStatusBadge.value.label,
  }
})
const headerNotice = computed(() => {
  if (String(errorMessage.value || '').trim()) {
    return {
      label: 'Ошибка',
      message: errorMessage.value,
      tone: 'error',
    }
  }

  if (String(successMessage.value || '').trim()) {
    return {
      label: 'Готово',
      message: successMessage.value,
      tone: 'ok',
    }
  }

  return null
})
const isBulkFilePickerReady = computed(() => (
  !isBulkAttachFlow.value
  || isTaskBulkAttachFlow.value
  || (Boolean(String(selectedFileAttachEntityType.value || '').trim()) && Boolean(String(selectedBulkFileField.value || '').trim()))
))
const bulkAttachSessionStatusNormalized = computed(() => String(bulkAttachSessionStatus.value || '').trim().toLowerCase())
const isBulkAttachExecutionLocked = computed(() => (
  isBulkAttachFlow.value
  && (
    busyAction.value === 'bulk-attach-run'
    || busyAction.value === 'bulk-attach-cancel'
    || ['created', 'queued', 'pending', 'running', 'cancelling', 'stopping'].includes(bulkAttachSessionStatusNormalized.value)
  )
))
const isBulkAttachScenarioLocked = computed(() => (
  isBulkAttachFlow.value
  && isBulkAttachExecutionLocked.value
))
const isBulkFilePickerLocked = computed(() => (
  crmFlavor.value === 'bulk'
  && (!isBulkFilePickerReady.value || isBulkAttachExecutionLocked.value)
))
const showBulkAttachExecutionState = computed(() => (
  busyAction.value === 'bulk-attach-run'
  || busyAction.value === 'bulk-attach-cancel'
  || Boolean(bulkAttachSessionId.value)
  || Boolean(bulkAttachSessionStatusNormalized.value)
))
const bulkAttachProgressPercent = computed(() => {
  if (!bulkAttachProgressTotal.value) return 0
  return Math.min(100, Math.round((bulkAttachProgressProcessed.value / bulkAttachProgressTotal.value) * 100))
})
const bulkAttachActionLabel = computed(() => {
  const normalizedStatus = String(bulkAttachSessionStatus.value || '').trim().toLowerCase()
  if (busyAction.value === 'bulk-attach-run') return 'Начинаем загрузку'
  if (normalizedStatus === 'running') return 'Загрузка выполняется'
  if (normalizedStatus === 'completed') return 'Загрузка завершена'
  if (normalizedStatus === 'failed') return 'Повторить загрузку'
  if (normalizedStatus === 'cancelled') return 'Запустить заново'
  return 'Начать загрузку'
})
const bulkPreviewActionLabel = computed(() => (
  isTaskBulkAttachFlow.value ? 'Показать задачи →' : 'Далее →'
))
const isBulkAttachActionDisabled = computed(() => {
  if (
    busyAction.value === 'bulk-attach-run'
    || busyAction.value === 'bulk-attach-cancel'
    || loadingBulkFilterPreview.value
    || loadingBulkFileFields.value
  ) {
    return true
  }

  if (
    !bulkFilterPreview.value
    || !selectedBulkAttachEntityType.value
    || (!isTaskBulkAttachFlow.value && !selectedBulkFileField.value)
    || !selectedFile.value
  ) {
    return true
  }

  return ['running', 'completed'].includes(String(bulkAttachSessionStatus.value || '').trim().toLowerCase())
})
const canCancelBulkAttach = computed(() => (
  Boolean(String(bulkAttachSessionId.value || '').trim())
  && String(bulkAttachSessionStatus.value || '').trim().toLowerCase() === 'running'
  && busyAction.value !== 'bulk-attach-cancel'
  && busyAction.value !== 'bulk-attach-run'
))
const dedupStrategyItems = computed(() => {
  const baseItems = [
    { value: 'create', label: 'Всегда создавать' },
  ]

  if (!isLinkedImportEntityType(entityType.value) && isSimpleImportMode.value && !simpleDedupPreset.value.available) {
    return baseItems
  }

  return [
    ...baseItems,
    { value: 'update', label: 'Обновлять найденный дубль' },
    { value: 'skip', label: 'Пропускать дубль' },
    ...(showsAdvancedImportTools.value ? [{ value: 'ask', label: 'Спросить по каждому дублю' }] : []),
  ]
})
const dedupFieldOptions = computed(() => buildDedupFieldOptions(
  mappingRows.value,
  mappingData.value?.fields,
))
const previewTableRows = computed(() => {
  const headerRowIndex = (headerRowInput.value || 1) - 1
  return previewRows.value
    .filter((_: any[], rowIndex: number) => rowIndex !== headerRowIndex)
    .map((row: any[], filteredIndex: number) => {
      const originalIndex = filteredIndex >= headerRowIndex ? filteredIndex + 1 : filteredIndex
      const record: Record<string, string | number> = {
        rowNumber: originalIndex + 1,
      }
      previewColumnsSource.value.forEach((column: string, columnIndex: number) => {
        record[`column_${columnIndex}`] = String(row?.[columnIndex] || '—')
      })
      return record
    })
})
const previewTableColumns = computed(() => {
  const headerRowIndex = (headerRowInput.value || 1) - 1
  const headerRow = previewRows.value[headerRowIndex]
  return [
    {
      accessorKey: 'rowNumber',
      header: '#',
      meta: {
        class: {
          th: 'w-[68px]',
          td: 'font-medium text-(--ui-color-base-60)',
        },
      },
    },
    ...previewColumnsSource.value.map((column: string, index: number) => {
      const headerValue = headerRow?.[index]
      return {
        accessorKey: `column_${index}`,
        header: headerValue ? String(headerValue) : String(column || `Колонка ${index + 1}`),
      }
    }),
  ]
})
const mappingTableColumns = computed(() => [
  {
    accessorKey: 'column',
    header: 'Колонка',
    meta: {
      class: {
        th: 'w-[120px]',
        td: 'font-medium text-(--ui-color-base-60)',
      },
    },
  },
  {
    accessorKey: 'sourceHeader',
    header: 'Колонка файла',
  },
  {
    accessorKey: 'targetFieldId',
    header: 'Поле Bitrix24',
    meta: {
      class: {
        th: 'min-w-[280px]',
      },
    },
  },
])
const valueMappingRows = computed<ValueMappingRow[]>(() => buildValueMappingRows({
  previewRows: preview.value?.preview_rows,
  headerRow: preview.value?.header_row,
  dataStartRow: preview.value?.data_start_row,
  observedValues: mappingData.value?.observed_values,
  mappingRows: mappingRows.value,
  fields: mappingData.value?.fields,
  savedMapping: sessionSavedMapping.value,
}))
const valueMappingStatus = computed(() => buildValueMappingStatus(valueMappingRows.value))
const valueMappingExpanded = ref(false)
const validationIssueRows = computed<ValidationIssueRow[]>(() => buildValidationIssueRows(validationData.value))
const dryRunRows = computed<DryRunRow[]>(() => buildDryRunRows(resolvedDryRunData.value, entityType.value))
const importRunRows = computed<ImportRunRow[]>(() => buildImportRunRows(importRunData.value, entityType.value))
const linkedImportRunSummary = computed(() => buildLinkedImportRunSummary(importRunData.value))
const linkedSummaryPageCount = computed(() => (
  linkedImportRunSummary.value.sections.reduce((maxPageCount, section) => Math.max(maxPageCount, section.pageCount || 1), 1)
))
const dryRunDedupWeakeningNotice = computed(() => buildDedupWeakeningNotice(resolvedDryRunData.value))
const importRunDedupWeakeningNotice = computed(() => buildDedupWeakeningNotice(importRunData.value))
const filteredDryRunRows = computed<DryRunRow[]>(() => (
  activeDryRunDedupRiskOnly.value
    ? dryRunRows.value.filter((row) => (
      hasLinkedEntityTree(row)
        ? (row.entityTree?.primary.rowNumbers || []).some((rowNumber) => dryRunDedupWeakeningNotice.value.rowNumbers.includes(rowNumber))
        : dryRunDedupWeakeningNotice.value.rowNumbers.includes(row.rowNumber)
    ))
    : dryRunRows.value
))
const dryRunPageCount = computed(() => (
  Math.max(1, Math.ceil(filteredDryRunRows.value.length / DRY_RUN_RESULTS_PAGE_SIZE))
))
const paginatedDryRunRows = computed<DryRunRow[]>(() => {
  const page = Math.min(dryRunPage.value, dryRunPageCount.value)
  const startIndex = (page - 1) * DRY_RUN_RESULTS_PAGE_SIZE
  return filteredDryRunRows.value.slice(startIndex, startIndex + DRY_RUN_RESULTS_PAGE_SIZE)
})
const dryRunPageRangeStart = computed(() => (
  filteredDryRunRows.value.length
    ? ((Math.min(dryRunPage.value, dryRunPageCount.value) - 1) * DRY_RUN_RESULTS_PAGE_SIZE) + 1
    : 0
))
const dryRunPageRangeEnd = computed(() => (
  filteredDryRunRows.value.length
    ? Math.min(dryRunPageRangeStart.value + DRY_RUN_RESULTS_PAGE_SIZE - 1, filteredDryRunRows.value.length)
    : 0
))
const importRunStatusFilters = computed<ImportRunFilterItem[]>(() => (
  buildImportRunStatusFilters(importRunData.value, entityType.value).filter((item) => item.count > 0)
))
const importRunProblemGroups = computed<ImportRunProblemGroup[]>(() => buildImportRunProblemGroups(importRunData.value))
const filteredImportRunRows = computed<ImportRunRow[]>(() => (
  filterImportRunRows(importRunRows.value, activeImportRunFilter.value)
))
const importRunPageCount = computed(() => (
  Math.max(1, Math.ceil(filteredImportRunRows.value.length / DRY_RUN_RESULTS_PAGE_SIZE))
))
const paginatedImportRunRows = computed<ImportRunRow[]>(() => {
  const page = Math.min(importRunPage.value, importRunPageCount.value)
  const startIndex = (page - 1) * DRY_RUN_RESULTS_PAGE_SIZE
  return filteredImportRunRows.value.slice(startIndex, startIndex + DRY_RUN_RESULTS_PAGE_SIZE)
})
const importRunPageRangeStart = computed(() => (
  filteredImportRunRows.value.length
    ? ((Math.min(importRunPage.value, importRunPageCount.value) - 1) * DRY_RUN_RESULTS_PAGE_SIZE) + 1
    : 0
))
const importRunPageRangeEnd = computed(() => (
  filteredImportRunRows.value.length
    ? Math.min(importRunPageRangeStart.value + DRY_RUN_RESULTS_PAGE_SIZE - 1, filteredImportRunRows.value.length)
    : 0
))
const isLinkedEntityImport = computed(() => isLinkedImportEntityType(entityType.value))
const importPhaseSummary = computed<Record<string, any>>(() => (
  session.value?.summary?.import_progress && typeof session.value.summary.import_progress === 'object'
    ? session.value.summary.import_progress
    : { phases: [] }
))
const stepSixStatusLabel = computed(() => {
  if (importExecutionStage.value === 'duplicate-decisions' && pendingDecisionRows.value.length) {
    return dryRunPendingDecisionRows.value > 0
      ? `Ожидают решения: ${dryRunPendingDecisionRows.value}`
      : `Решения выбраны: ${pendingDecisionRows.value.length}`
  }
  if (resolvedDryRunData.value) {
    const fullTotalRows = Number(resolvedDryRunData.value?.full_total_rows || dryRunCheckedRows.value || 0)
    return fullTotalRows > dryRunCheckedRows.value
      ? `Проверено: ${dryRunCheckedRows.value} из ${fullTotalRows}`
      : `Проверено строк: ${dryRunCheckedRows.value}`
  }

  return validationIssueCount.value > 0
    ? `Ошибок: ${validationIssueCount.value}`
    : 'Ошибок не найдено'
})
const stepSixMetricCards = computed(() => {
  if (importExecutionStage.value === 'duplicate-decisions' && dryRunData.value) {
    return [
      { label: 'Проверено строк', value: Number(dryRunData.value?.checked_rows || 0) },
      { label: 'Найдено дублей', value: pendingDecisionRows.value.length },
      dryRunPendingDecisionRows.value > 0
        ? { label: 'Осталось решить', value: dryRunPendingDecisionRows.value }
        : { label: 'Готово к импорту', value: dryRunReadyRows.value },
    ]
  }
  if (resolvedDryRunData.value) {
    const cards = [
      { label: 'Проверено строк', value: dryRunCheckedRows.value },
      { label: 'Всего строк в файле', value: Number(resolvedDryRunData.value?.full_total_rows || dryRunCheckedRows.value) },
      { label: 'Готово к импорту', value: dryRunReadyRows.value },
    ]
    if (dryRunPendingDecisionRows.value > 0) {
      cards.push({ label: 'Ожидают решения', value: dryRunPendingDecisionRows.value })
    } else if (dryRunSkippedRows.value > 0) {
      cards.push({ label: 'Будет пропущено', value: dryRunSkippedRows.value })
    }
    return cards
  }

  return [
    { label: 'Проверено', value: validationCheckedRows.value },
    { label: 'Без ошибок', value: validationValidRows.value },
    { label: 'С ошибками', value: validationInvalidRows.value },
  ]
})
const importExecutionPhaseCards = computed(() => {
  const phaseItems = Array.isArray(importPhaseSummary.value?.phases) ? importPhaseSummary.value.phases : []
  return phaseItems.map((item: any) => ({
      id: String(item?.id || ''),
      label: String(
        item?.label
        || (String(item?.id || '') === 'new_records'
          ? 'Импорт новых записей'
          : String(item?.id || '') === 'duplicates'
            ? 'Обработка дублей'
            : ''),
      ),
      description: `${Number(item?.processed_rows || 0)} из ${Number(item?.total_rows || 0)} строк`,
      status: String(item?.status || 'upcoming'),
    }))
})
const validationTableColumns = computed(() => [
  {
    accessorKey: 'rowNumber',
    header: 'Строка',
    meta: {
      class: {
        th: 'w-[92px]',
        td: 'font-medium text-(--ui-color-base-60)',
      },
    },
  },
  {
    accessorKey: 'column',
    header: 'Колонка',
    meta: {
      class: {
        th: 'w-[92px]',
      },
    },
  },
  {
    accessorKey: 'sourceHeader',
    header: 'Колонка файла',
  },
  {
    accessorKey: 'message',
    header: 'Проблема',
    meta: {
      class: {
        th: 'min-w-[320px]',
      },
    },
  },
  {
    accessorKey: 'value',
    header: 'Значение',
  },
])
const dryRunTableColumns = computed(() => [
  {
    accessorKey: 'details',
    header: 'Что уйдет в Bitrix24',
    meta: {
      class: {
        th: 'min-w-[360px]',
      },
    },
  },
  {
    accessorKey: 'rowNumber',
    header: 'Строка',
    meta: {
      class: {
        th: 'w-[92px]',
        td: 'font-medium text-(--ui-color-base-60)',
      },
    },
  },
])
const importRunTableColumns = computed(() => [
  {
    accessorKey: 'details',
    header: 'Что попало в Bitrix24',
    meta: {
      class: {
        th: 'min-w-[360px]',
      },
    },
  },
  {
    accessorKey: 'rowNumber',
    header: 'Строка',
    meta: {
      class: {
        th: 'w-[110px]',
        td: 'font-medium text-(--ui-color-base-60)',
      },
    },
  },
])

watch(maxAvailableStep, (value) => {
  if (currentStep.value > value && !busyAction.value) {
    currentStep.value = value
  }
})

watch(importRunData, (value) => {
  activeImportRunFilter.value = resolveImportRunFilterId(value, activeImportRunFilter.value, entityType.value)
}, { immediate: true })

watch(dryRunData, (value) => {
  if (!buildDedupWeakeningNotice(value).hasWarnings) {
    activeDryRunDedupRiskOnly.value = false
  }

  if (value && requiresPerRowDedupDecision.value) {
    const decisions: Record<string, any> = {}
    for (const row of (Array.isArray(value.results) ? value.results : [])) {
      if (row?.status === 'pending_decision') {
        const rowNumber = String(row.row_number || '')
        const previousDecision = perRowDedupDecisions.value[rowNumber]
        if (rowNumber && isValidPerRowDedupDecision(previousDecision)) {
          decisions[rowNumber] = previousDecision
          continue
        }

        if (
          rowNumber
          && previousDecision
          && typeof previousDecision === 'object'
          && !Array.isArray(previousDecision)
        ) {
          const linkedEntityIds = getPendingDecisionLinkedEntityIds(row)
          const filteredDecision = linkedEntityIds.reduce((result, entityId) => {
            const entityDecision = normalizePerRowEntityDecision((previousDecision as Record<string, any>)[entityId])
            if (entityDecision) {
              result[entityId] = entityDecision
            }
            return result
          }, {} as Record<string, string>)
          if (Object.keys(filteredDecision).length > 0) {
            decisions[rowNumber] = filteredDecision
          }
        }
      }
    }
    perRowDedupDecisions.value = decisions
  } else {
    perRowDedupDecisions.value = {}
  }
})

function goToStep(step: number) {
  if (step < 1 || step > maxAvailableStep.value) {
    return
  }

  if (step > currentStep.value && !canGoNext.value) {
    return
  }

  currentStep.value = step
}

function goToBulkFlowStep(step: number) {
  const currentBulkStep = bulkFlowStep.value === 'setup'
    ? 1
    : bulkFlowStep.value === 'review'
      ? 2
      : 3

  if (step < 1 || step > currentBulkStep || step === currentBulkStep) {
    return
  }

  if (isBulkAttachExecutionLocked.value) {
    return
  }

  if (step === 1) {
    resetBulkAttachExecutionState()
    bulkFilterPreview.value = null
    clearSelectedFile()
    resetMessages()
    return
  }

  resetBulkAttachExecutionState()
  resetMessages()
}

function goToSidebarStep(step: number) {
  if (isBulkAttachFlow.value && currentStep.value === 1) {
    goToBulkFlowStep(step)
    return
  }

  goToStep(step)
}

function goNext() {
  if (!canGoNext.value) {
    return
  }

  if (wizardAdvanceMode.value === 'finish') {
    finishImporterFlow()
    return
  }

  currentStep.value += 1
}

function goBack() {
  if (!canGoBack.value) {
    return
  }

  currentStep.value -= 1
}

function resetMessages() {
  errorMessage.value = ''
  successMessage.value = ''
}

function selectImportRunFilter(filterId: string) {
  activeImportRunFilter.value = resolveImportRunFilterId(importRunData.value, filterId)
}

function toggleDryRunDedupRiskOnly() {
  activeDryRunDedupRiskOnly.value = !activeDryRunDedupRiskOnly.value
}

function setError(message: string) {
  errorMessage.value = message
  successMessage.value = ''
}

function setSuccess(message: string) {
  successMessage.value = message
  errorMessage.value = ''
}

function buildImportFileSizeErrorMessage(file: File) {
  const sizeInMegabytes = (Number(file?.size || 0) / (1024 * 1024)).toFixed(1)
  return `Файл слишком большой: ${sizeInMegabytes} МБ. Максимум для импорта — ${MAX_IMPORT_FILE_SIZE_LABEL}.`
}

function clearSelectedFile() {
  selectedFile.value = null

  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

function stopBulkAttachPolling() {
  if (bulkAttachPollingHandle.value) {
    clearInterval(bulkAttachPollingHandle.value)
    bulkAttachPollingHandle.value = null
  }
}

function resetBulkAttachExecutionState() {
  stopBulkAttachPolling()
  bulkAttachSessionId.value = ''
  bulkAttachSessionStatus.value = ''
  bulkAttachResultTotal.value = 0
  bulkAttachResultSuccessful.value = 0
  bulkAttachResultFailed.value = 0
  bulkAttachProgressProcessed.value = 0
  bulkAttachProgressTotal.value = 0
}

async function loadBulkAttachEntityFields(entityType: string) {
  const normalizedValue = String(entityType || '').trim()
  if (!normalizedValue) {
    bulkFileFields.value = []
    bulkEntityFields.value = []
    return
  }

  loadingBulkFileFields.value = true
  try {
    if (normalizedValue === 'task_attachment') {
      const response = await apiStore.getImportFields('task')
      const rawItems = Array.isArray(response.items) ? response.items : []
      bulkFileFields.value = []
      bulkEntityFields.value = rawItems
        .map((item: any) => ({
          id: String(item?.id || '').trim(),
          title: String(item?.title || item?.id || '').trim(),
          type: String(item?.type || '').trim(),
          items: Array.isArray(item?.items)
            ? item.items
              .map((option: any) => ({
                value: String(option?.id ?? option?.value ?? '').trim(),
                label: String(option?.title ?? option?.label ?? option?.id ?? option?.value ?? '').trim(),
              }))
              .filter((option: { value: string, label: string }) => option.value && option.label)
            : [],
        }))
        .filter((field: { id: string, title: string }) => field.id && field.title)
      return
    }

    const [fileResult, allResult] = await Promise.all([
      apiStore.fetchCrmFileFields(normalizedValue),
      apiStore.fetchCrmEntityFields(normalizedValue),
    ])
    bulkFileFields.value = (fileResult.fields || []).map((field) => ({ value: field.id, label: field.title }))
    bulkEntityFields.value = allResult.fields || []
  } catch {
    bulkFileFields.value = []
    bulkEntityFields.value = []
  } finally {
    loadingBulkFileFields.value = false
  }
}

function resetFlowState() {
  session.value = null
  preview.value = null
  mappingData.value = null
  mappingRows.value = []
  linkedDedupSettings.value = {}
  dedupStrategy.value = 'create'
  dedupCondition.value = 'any'
  dedupFields.value = []
  perRowDedupDecisions.value = {}
  validationData.value = null
  dryRunData.value = null
  preimportScanData.value = null
  importRunData.value = null
  importTemplates.value = []
  importAliasRules.value = []
  selectedTemplateId.value = ''
  templateNameInput.value = ''
  headerRowInput.value = 1
  dataStartRowInput.value = 2
  activeImportRunFilter.value = 'all'
  linkedSummaryPage.value = 1
  cancelRequested.value = false
  importExecutionStage.value = 'idle'
}

function finishImporterFlow() {
  resetFlowState()
  importMode.value = ''
  selectedFamily.value = ''
  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedLinkedPrimaryEntityType.value = ''
  selectedLinkedSecondaryEntityType.value = ''
  selectedHrEntityType.value = ''
  selectedFileAttachEntityType.value = ''
  selectedSmartProcessId.value = ''
  entityType.value = ''
  currentStep.value = 1

  clearSelectedFile()

  setSuccess('Импорт завершен. Можно начать новый импорт.')
  loadHistory()
}

function syncDedupSettings() {
  const savedDedup = mappingData.value?.saved_dedup
  if (isLinkedImportEntityType(entityType.value)) {
    linkedDedupSettings.value = linkedDedupEntityGroups.value.reduce((result, group) => {
      result[group.id] = normalizeDedupState(
        savedDedup && typeof savedDedup === 'object' ? savedDedup[group.id] : null,
      )
      return result
    }, {} as Record<string, { strategy: string, condition: 'any' | 'all', fields: string[] }>)
    dedupStrategy.value = 'create'
    dedupFields.value = []
    dedupCondition.value = 'any'
    return
  }

  linkedDedupSettings.value = {}
  const payload = buildDedupPayload(savedDedup || {})
  dedupStrategy.value = String(payload.strategy || 'create')
  dedupFields.value = Array.isArray(payload.fields) ? payload.fields.map((field) => String(field || '').trim()).filter(Boolean) : []
  dedupCondition.value = String(payload.condition || 'any') === 'all' ? 'all' : 'any'
}

function syncMappingRows() {
  if (!mappingData.value) {
    mappingRows.value = []
    importAliasRules.value = []
    taskDefaultResponsibleId.value = ''
    taskDefaultCreatorId.value = ''
    taskDefaultCommentAuthorId.value = ''
    linkedDedupSettings.value = {}
    dedupStrategy.value = 'create'
    dedupCondition.value = 'any'
    dedupFields.value = []
    return
  }

  mappingRows.value = buildMappingRows({
    headers: mappingData.value.headers,
    columns: mappingData.value.columns,
    fields: mappingData.value.fields,
    candidateMapping: mappingData.value.candidate_mapping,
    candidateSuggestions: mappingData.value.candidate_suggestions,
    savedMapping: sessionSavedMapping.value,
    preferSavedMapping: Object.keys(sessionSavedMapping.value).length > 0,
  })
  importAliasRules.value = Array.isArray(mappingData.value.alias_rules) ? mappingData.value.alias_rules : []
  taskDefaultResponsibleId.value = String(mappingData.value?.task_defaults?.default_responsible_id || '')
  taskDefaultCreatorId.value = String(mappingData.value?.task_defaults?.default_creator_id || '')
  taskDefaultCommentAuthorId.value = String(mappingData.value?.task_defaults?.default_comment_author_id || '')
  syncDedupSettings()
}

function normalizeAliasRuleSourceLabel(value: string) {
  return String(value || '').trim().toLowerCase()
}

function hasImportAliasRule(row: MappingRow) {
  const sourceLabel = normalizeAliasRuleSourceLabel(row.sourceHeader)
  const targetFieldId = String(row.targetFieldId || '').trim()
  if (!sourceLabel || !targetFieldId) {
    return false
  }

  return importAliasRules.value.some((item) => (
    normalizeAliasRuleSourceLabel(String(item?.source_label || '')) === sourceLabel
    && String(item?.target_field_id || '').trim() === targetFieldId
  ))
}

function applyCandidateSuggestion(
  row: MappingRow,
  suggestion: {
    targetFieldId: string
    matchType?: string
    matchLabel?: string
    matchReason?: string
    matchReasonLabel?: string
  },
) {
  updateMappingFieldSelection(row, suggestion.targetFieldId)
  row.autoMatchType = String(suggestion.matchType || '').trim().toLowerCase()
  row.autoMatchLabel = String(suggestion.matchLabel || '').trim()
  row.autoMatchReason = String(suggestion.matchReason || '').trim().toLowerCase()
  row.autoMatchReasonLabel = String(suggestion.matchReasonLabel || '').trim()
}

function buildPreflightSeverityLabel(severity: string) {
  return String(severity || '').trim().toLowerCase() === 'error' ? 'Ошибка' : 'Предупреждение'
}

function resolveImporterFieldLabel(fieldId: string, fieldTitle = '') {
  const normalizedFieldId = String(fieldId || '').trim()
  if (!normalizedFieldId) {
    return ''
  }

  const resolvedField = normalizedFieldOptionsIndex.value.get(normalizedFieldId.toUpperCase())
  const resolvedTitle = String(resolvedField?.title || fieldTitle || '').trim()
  return formatImporterFieldLabel(normalizedFieldId, resolvedTitle)
}

function buildPreflightIssueMeta(issue: Record<string, any>) {
  const fieldLabel = resolveImporterFieldLabel(
    String(issue?.field_id || ''),
    String(issue?.field_title || ''),
  )
  return fieldLabel || String(issue?.code || '')
}

function buildPreflightIssueDescription(issue: Record<string, any>) {
  const code = String(issue?.code || '').trim()
  const fieldId = String(issue?.field_id || '').trim()
  const entity = String(issue?.entity || '').trim()
  const rowCount = Number(issue?.row_count || 0)
  const valueCount = Number(issue?.value_count || 0)
  const values = Array.isArray(issue?.values)
    ? issue.values.map((value: any) => String(value || '').trim()).filter(Boolean)
    : []
  const activityTypes = Array.isArray(issue?.activity_types)
    ? issue.activity_types.map((value: any) => String(value || '').trim()).filter(Boolean)
    : []

  if (code === 'required_field_unmapped') {
    return `Не сопоставлено обязательное поле ${resolveImporterFieldLabel(fieldId)}.`
  }
  if (code === 'dedup_field_unmapped') {
    const entityLabelMap: Record<string, string> = {
      company: 'компании',
      contact: 'контакта',
      deal: 'сделки',
      lead: 'лида',
    }
    const entityLabel = entity ? ` для ${entityLabelMap[entity] || entity}` : ''
    return `Не выбрано поле поиска дублей${entityLabel}: ${resolveImporterFieldLabel(fieldId)}.`
  }
  if (code === 'field_values_unmapped') {
    const valuesLabel = values.length ? ` Значения: ${values.join(', ')}.` : ''
    const countLabel = valueCount > 0 ? ` Не сопоставлено значений: ${valueCount}.` : ''
    return `Не заполнено соответствие значений для поля ${resolveImporterFieldLabel(fieldId)}.${countLabel}${valuesLabel}`
  }
  if (code === 'field_options_unavailable') {
    const valuesLabel = values.length ? ` Значения из файла: ${values.join(', ')}.` : ''
    const countLabel = valueCount > 0 ? ` Найдено значений: ${valueCount}.` : ''
    return `Для поля ${resolveImporterFieldLabel(fieldId)} не загрузились варианты Bitrix24.${countLabel}${valuesLabel}`
  }
  if (code === 'crm_activity_communications_missing') {
    const activityTypeLabels: Record<string, string> = {
      call: 'звонков',
      email: 'писем',
    }
    const activityLabel = activityTypes.length
      ? activityTypes.map((item) => activityTypeLabels[item] || item).join(', ')
      : 'звонков и писем'
    const rowCountLabel = rowCount > 0 ? ` Строк: ${rowCount}.` : ''
    return `Для ${activityLabel} не заполнено поле ${resolveImporterFieldLabel(fieldId)}.${rowCountLabel}`
  }
  if (code === 'linked_company_identity_missing') {
    const companyRowLabel = rowCount > 0 ? ` Повторяющихся строк: ${rowCount}.` : ''
    return `В связанных данных компании повторяются по названию без явного идентификатора. Добавьте COMPANY__XML_ID или настройте дедупликацию компании.${companyRowLabel}`
  }
  return code || 'Проблема предварительной проверки.'
}

function makeCollapsibleKey(section: string, key: string | number) {
  return `${String(section || '').trim()}:${String(key || '').trim()}`
}

function normalizeCollapsibleText(value: unknown) {
  return String(value ?? '').trim()
}

function isTextCollapsible(value: unknown, limit = COLLAPSIBLE_TEXT_LIMIT) {
  return normalizeCollapsibleText(value).length > limit
}

function buildCollapsedText(value: unknown, limit = COLLAPSIBLE_TEXT_LIMIT) {
  const text = normalizeCollapsibleText(value)
  if (!isTextCollapsible(text, limit)) {
    return text
  }

  return `${text.slice(0, limit).trimEnd()}…`
}

function isTextBlockExpanded(key: string) {
  return Boolean(expandedTextBlocks.value[key])
}

function toggleTextBlock(key: string) {
  expandedTextBlocks.value = {
    ...expandedTextBlocks.value,
    [key]: !expandedTextBlocks.value[key],
  }
}

function getTextBlockDisplayValue(key: string, value: unknown) {
  const text = normalizeCollapsibleText(value)
  if (!isTextCollapsible(text)) {
    return text
  }

  return isTextBlockExpanded(key) ? text : buildCollapsedText(text)
}

watch(dedupStrategy, (value, previousValue) => {
  if (isLinkedImportEntityType(entityType.value)) {
    return
  }

  if (value === 'create') {
    dedupFields.value = []
  }

  if (previousValue !== undefined && value !== previousValue && busyAction.value !== 'dedup-skip') {
    skippedDedupStep.value = false
  }
})

watch([isSimpleImportMode, simpleDedupPreset], ([simpleModeEnabled, preset]) => {
  if (isLinkedImportEntityType(entityType.value)) {
    return
  }

  if (!simpleModeEnabled) {
    return
  }

  if (!preset.available && dedupStrategy.value !== 'create') {
    dedupStrategy.value = 'create'
  }

  if (dedupStrategy.value === 'ask') {
    dedupStrategy.value = preset.available ? 'update' : 'create'
  }

  if (dedupStrategy.value !== 'create') {
    dedupFields.value = preset.fields
  }
}, { immediate: true })

watch(isDedupApplicable, (applicable) => {
  if (!applicable) {
    linkedDedupSettings.value = {}
    dedupStrategy.value = 'create'
    dedupFields.value = []
    skippedDedupStep.value = false
  }
})

watch(dedupCondition, (value, previousValue) => {
  if (isLinkedImportEntityType(entityType.value)) {
    return
  }

  if (previousValue !== undefined && value !== previousValue && busyAction.value !== 'dedup-skip') {
    skippedDedupStep.value = false
  }
})

watch(() => String(session.value?.id || ''), () => {
  skippedDedupStep.value = false
})

watch(entityType, (value) => {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) {
    return
  }

  if (crmScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedCrmEntityType.value = normalizedValue
    selectedTaskEntityType.value = ''
    selectedLinkedPrimaryEntityType.value = ''
    selectedLinkedSecondaryEntityType.value = ''
    selectedHrEntityType.value = ''
    if (normalizedValue !== 'smart_process') {
      selectedSmartProcessId.value = ''
    }
  }

  if (taskScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedTaskEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedLinkedPrimaryEntityType.value = ''
    selectedLinkedSecondaryEntityType.value = ''
    selectedHrEntityType.value = ''
    selectedSmartProcessId.value = ''
  }

  if (linkedScenarioItems.value.some((item) => item.value === normalizedValue)) {
    const linkedStrategyPair = resolveLinkedStrategyPair(normalizedValue)
    selectedLinkedPrimaryEntityType.value = linkedStrategyPair.primaryEntityType
    selectedLinkedSecondaryEntityType.value = linkedStrategyPair.secondaryEntityType
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedHrEntityType.value = ''
    selectedSmartProcessId.value = ''
  }

  if (hrScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedHrEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedLinkedPrimaryEntityType.value = ''
    selectedLinkedSecondaryEntityType.value = ''
    selectedSmartProcessId.value = ''
  }
}, { immediate: true })

watch(selectedCrmEntityType, async (value) => {
  if (String(value || '').trim() !== 'smart_process') {
    selectedSmartProcessId.value = ''
    return
  }

  if (smartProcesses.value.length > 0 || loadingSmartProcesses.value) {
    return
  }

  await loadSmartProcesses()
})

watch(selectedFileAttachEntityType, async (value) => {
  if (isRestoringImporterSession.value) {
    return
  }

  selectedBulkFileField.value = ''
  bulkFileFields.value = []
  bulkEntityFields.value = []
  bulkFilterPreview.value = null
  bulkFilterConditions.value = []
  resetBulkAttachExecutionState()
  clearSelectedFile()
  isAddingBulkFilterField.value = false
  pendingBulkFilterFieldId.value = ''
  if (!value) return
  await loadBulkAttachEntityFields(value)
})

watch(selectedTaskEntityType, async (value, previousValue) => {
  if (isRestoringImporterSession.value) {
    return
  }

  const normalizedValue = String(value || '').trim()
  const normalizedPreviousValue = String(previousValue || '').trim()
  if (normalizedValue === normalizedPreviousValue) {
    return
  }

  if (normalizedValue === 'task_attachment') {
    selectedBulkFileField.value = ''
    bulkFileFields.value = []
    bulkEntityFields.value = []
    bulkFilterPreview.value = null
    bulkFilterConditions.value = []
    resetBulkAttachExecutionState()
    clearSelectedFile()
    isAddingBulkFilterField.value = false
    pendingBulkFilterFieldId.value = ''
    await loadBulkAttachEntityFields('task_attachment')
    return
  }

  if (normalizedPreviousValue === 'task_attachment') {
    selectedBulkFileField.value = ''
    bulkFileFields.value = []
    bulkEntityFields.value = []
    bulkFilterPreview.value = null
    bulkFilterConditions.value = []
    resetBulkAttachExecutionState()
    clearSelectedFile()
    isAddingBulkFilterField.value = false
    pendingBulkFilterFieldId.value = ''
  }
})

watch(selectedBulkFileField, (value, previousValue) => {
  if (String(value || '').trim() === String(previousValue || '').trim()) {
    return
  }

  if (isRestoringImporterSession.value) {
    return
  }

  bulkFilterPreview.value = null
  resetBulkAttachExecutionState()
  dropzoneDragOver.value = false
})

watch(selectedFile, (value, previousValue) => {
  if (value === previousValue) {
    return
  }

  resetBulkAttachExecutionState()
})

watch(dedupFieldOptions, (options) => {
  if (isLinkedImportEntityType(entityType.value)) {
    return
  }

  const allowed = new Set(options.map((option) => option.id))
  dedupFields.value = dedupFields.value.filter((field) => allowed.has(field))
})

watch(linkedImportRunSummary, () => {
  linkedSummaryPage.value = 1
})

watch(dryRunData, () => {
  dryRunPage.value = 1
})

watch(activeDryRunDedupRiskOnly, () => {
  dryRunPage.value = 1
})

watch(() => filteredDryRunRows.value.length, () => {
  dryRunPage.value = Math.min(dryRunPage.value, dryRunPageCount.value)
})

watch(importRunData, () => {
  importRunPage.value = 1
})

watch(activeImportRunFilter, () => {
  importRunPage.value = 1
})

watch(() => filteredImportRunRows.value.length, () => {
  importRunPage.value = Math.min(importRunPage.value, importRunPageCount.value)
})

function setLinkedSummaryPage(page: number) {
  linkedSummaryPage.value = Math.min(
    Math.max(1, Number(page || 1)),
    Math.max(1, Number(linkedSummaryPageCount.value || 1)),
  )
}

function buildLinkedSummaryPages(): number[] {
  return Array.from({ length: linkedSummaryPageCount.value }, (_, index) => index + 1)
}

function setDryRunPage(page: number) {
  dryRunPage.value = Math.min(
    Math.max(1, Number(page || 1)),
    Math.max(1, Number(dryRunPageCount.value || 1)),
  )
}

function buildVisibleDryRunPageItems(): Array<number | 'start-ellipsis' | 'end-ellipsis'> {
  const totalPages = dryRunPageCount.value
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const currentPage = Math.min(dryRunPage.value, totalPages)
  const lastPage = totalPages
  let startPage = Math.max(2, currentPage - 1)
  let endPage = Math.min(lastPage - 1, currentPage + 1)

  if (currentPage <= 4) {
    endPage = 4
  } else if (currentPage >= lastPage - 3) {
    startPage = lastPage - 3
  }

  const items: Array<number | 'start-ellipsis' | 'end-ellipsis'> = [1]

  if (startPage > 2) {
    items.push('start-ellipsis')
  }

  for (let page = startPage; page <= endPage; page += 1) {
    items.push(page)
  }

  if (endPage < lastPage - 1) {
    items.push('end-ellipsis')
  }

  items.push(lastPage)
  return items
}

function setImportRunPage(page: number) {
  importRunPage.value = Math.min(
    Math.max(1, Number(page || 1)),
    Math.max(1, Number(importRunPageCount.value || 1)),
  )
}

function buildVisibleImportRunPageItems(): Array<number | 'start-ellipsis' | 'end-ellipsis'> {
  const totalPages = importRunPageCount.value
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const currentPage = Math.min(importRunPage.value, totalPages)
  const lastPage = totalPages
  let startPage = Math.max(2, currentPage - 1)
  let endPage = Math.min(lastPage - 1, currentPage + 1)

  if (currentPage <= 4) {
    endPage = 4
  } else if (currentPage >= lastPage - 3) {
    startPage = lastPage - 3
  }

  const items: Array<number | 'start-ellipsis' | 'end-ellipsis'> = [1]

  if (startPage > 2) {
    items.push('start-ellipsis')
  }

  for (let page = startPage; page <= endPage; page += 1) {
    items.push(page)
  }

  if (endPage < lastPage - 1) {
    items.push('end-ellipsis')
  }

  items.push(lastPage)
  return items
}

function buildVisibleLinkedSummaryItems(section: LinkedImportSummarySection): LinkedImportSummaryItem[] {
  const page = Math.min(linkedSummaryPage.value, Math.max(1, section.pageCount || 1))
  const startIndex = (page - 1) * section.pageSize
  return section.items.slice(startIndex, startIndex + section.pageSize)
}

function resolveActiveCrmFlavorEntityType(flavor: 'direct' | 'linked' | 'bulk') {
  if (flavor === 'direct') {
    return String(selectedCrmEntityType.value || '').trim()
  }

  if (flavor === 'linked') {
    return resolveLinkedStrategyEntityType(
      selectedLinkedPrimaryEntityType.value,
      selectedLinkedSecondaryEntityType.value,
    )
  }

  return String(selectedFileAttachEntityType.value || '').trim()
}

function selectCrmFlavor(value: 'direct' | 'linked' | 'bulk') {
  const normalizedValue = value === 'linked' || value === 'bulk' ? value : 'direct'
  if (isBulkAttachScenarioLocked.value && normalizedValue !== crmFlavor.value) {
    return
  }

  crmFlavor.value = normalizedValue

  if (normalizedValue === 'direct') {
    entityType.value = selectedCrmEntityType.value
  } else if (normalizedValue === 'linked') {
    entityType.value = resolveLinkedStrategyEntityType(
      selectedLinkedPrimaryEntityType.value,
      selectedLinkedSecondaryEntityType.value,
    )
  } else {
    entityType.value = selectedFileAttachEntityType.value
  }
}

function formatDedupFieldList(fields: unknown): string {
  const normalizedFields = Array.isArray(fields)
    ? fields.map((field) => resolveImporterFieldLabel(String(field || '').trim())).filter(Boolean)
    : []
  return normalizedFields.length ? normalizedFields.join(', ') : '—'
}

function selectImportMode(mode: string) {
  importMode.value = getImportModeMeta(mode).value
  goBackToFamilySelection()
  clearSelectedFile()
  resetFlowState()
  currentStep.value = 1
}

function goBackToImportModeSelection() {
  currentView.value = 'wizard'
  importMode.value = ''
  goBackToFamilySelection()
  clearSelectedFile()
  resetFlowState()
  currentStep.value = 1
}

function selectFamily(family: string) {
  selectedFamily.value = family
  selectCrmFlavor('direct')
  bulkFilterPreview.value = null
  bulkFileFields.value = []
  selectedBulkFileField.value = ''
  isAddingBulkFilterField.value = false
  pendingBulkFilterFieldId.value = ''
  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedLinkedPrimaryEntityType.value = ''
  selectedLinkedSecondaryEntityType.value = ''
  selectedHrEntityType.value = ''
  selectedFileAttachEntityType.value = ''
  selectedSmartProcessId.value = ''
  entityType.value = ''
  departmentsExpanded.value = false
  resetMessages()
}

async function runBulkFilterPreview() {
  const plainType = String(selectedBulkAttachEntityType.value || '').trim()
  if (!plainType) return
  const filter = buildBulkFilterPayload()
  loadingBulkFilterPreview.value = true
  resetBulkAttachExecutionState()
  bulkFilterPreview.value = null
  try {
    const result = await apiStore.crmFilterPreview({ entity_type: plainType, filter })
    bulkFilterPreview.value = { total: result.total, sample: result.sample }
  }
  catch {
    bulkFilterPreview.value = { total: 0, sample: [] }
  }
  finally {
    loadingBulkFilterPreview.value = false
  }
}

function buildBulkFilterPayload() {
  const filter: Record<string, string> = {}
  for (const cond of bulkFilterConditions.value) {
    if (cond.fieldId.trim() && cond.value.trim()) {
      filter[cond.fieldId.trim()] = cond.value.trim()
    }
  }
  return filter
}

function applyBulkAttachSnapshot(snapshot: Record<string, any> | null | undefined, result?: Record<string, any> | null) {
  const snap = snapshot && typeof snapshot === 'object' ? snapshot : {}
  const normalizedStatus = String(snap.status || bulkAttachSessionStatus.value || '').trim().toLowerCase()

  bulkAttachSessionId.value = String(snap.id || bulkAttachSessionId.value || '')
  bulkAttachSessionStatus.value = normalizedStatus
  bulkAttachProgressTotal.value = Number(snap.total_rows || bulkFilterPreview.value?.total || bulkAttachProgressTotal.value || 0)
  bulkAttachProgressProcessed.value = Number(
    snap.processed_rows
    ?? (normalizedStatus === 'running' ? bulkAttachProgressProcessed.value : bulkAttachProgressTotal.value),
  )
  bulkAttachResultTotal.value = Number(result?.total ?? snap.total_rows ?? bulkAttachResultTotal.value)
  bulkAttachResultSuccessful.value = Number(result?.successful ?? snap.successful_rows ?? bulkAttachResultSuccessful.value)
  bulkAttachResultFailed.value = Number(result?.failed ?? snap.failed_rows ?? bulkAttachResultFailed.value)

  if (normalizedStatus && normalizedStatus !== 'running') {
    stopBulkAttachPolling()
    if (!bulkAttachResultTotal.value) {
      bulkAttachResultTotal.value = bulkAttachProgressTotal.value
    }
    bulkAttachProgressProcessed.value = bulkAttachResultTotal.value || bulkAttachProgressProcessed.value
  }
}

function buildBulkAttachPreviewFromSnapshot(snapshot: Record<string, any> | null | undefined) {
  const totalRows = Number(snapshot?.total_rows || snapshot?.processed_rows || 0)
  return {
    total: totalRows,
    sample: [] as Array<{ id: number, title: string }>,
  }
}

function startBulkAttachPolling(sessionId: string) {
  if (!sessionId || bulkAttachPollingHandle.value) {
    return
  }

  bulkAttachPollingHandle.value = setInterval(async () => {
    try {
      const response = await apiStore.getImportSession(sessionId)
      applyBulkAttachSnapshot(response.item)
    } catch {
      // Ignore polling errors. The next poll or manual navigation will reconcile the state.
    }
  }, 2000)
}

function resolveBulkFilterField(fieldId: string) {
  return bulkEntityFields.value.find((field) => field.id === fieldId) || null
}

function openAddBulkFilterField() {
  isAddingBulkFilterField.value = true
  pendingBulkFilterFieldId.value = ''
}

function addBulkFilterField(fieldId: string) {
  const normalizedFieldId = String(fieldId || '').trim()
  if (!normalizedFieldId) {
    return
  }

  if (bulkFilterConditions.value.some((condition) => condition.fieldId === normalizedFieldId)) {
    pendingBulkFilterFieldId.value = ''
    isAddingBulkFilterField.value = false
    return
  }

  bulkFilterConditions.value = [
    ...bulkFilterConditions.value,
    { fieldId: normalizedFieldId, value: '' },
  ]
  pendingBulkFilterFieldId.value = ''
  isAddingBulkFilterField.value = false
}

function removeBulkFilterField(fieldId: string) {
  bulkFilterConditions.value = bulkFilterConditions.value.filter((condition) => condition.fieldId !== fieldId)
}

function getBulkFilterValueOptions(fieldId: string) {
  const field = resolveBulkFilterField(fieldId)
  return Array.isArray(field?.items) ? field.items : []
}

function goBackFromBulkPreview() {
  resetBulkAttachExecutionState()
  bulkFilterPreview.value = null
  resetMessages()
}

function handleStepOneBack() {
  if (isBulkAttachFlow.value) {
    if (isBulkAttachExecutionLocked.value) {
      return
    }

    if (bulkFlowStep.value === 'execution') {
      goToBulkFlowStep(2)
      return
    }

    if (bulkFlowStep.value === 'review') {
      goToBulkFlowStep(1)
      return
    }
  }

  goBackToFamilySelection()
}

async function cancelBulkAttachExecution() {
  const sessionId = String(bulkAttachSessionId.value || '').trim()
  if (!sessionId || !canCancelBulkAttach.value) {
    return
  }

  resetMessages()
  busyAction.value = 'bulk-attach-cancel'

  try {
    const response = await apiStore.cancelImportSession(sessionId)
    applyBulkAttachSnapshot(response.item)
    setSuccess('Загрузка остановлена.')
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    if (busyAction.value === 'bulk-attach-cancel') {
      busyAction.value = ''
    }
  }
}

function goBackToFamilySelection() {
  currentView.value = 'wizard'
  selectedFamily.value = ''
  selectCrmFlavor('direct')
  resetBulkAttachExecutionState()
  bulkFilterPreview.value = null
  bulkFilterConditions.value = []
  bulkFileFields.value = []
  selectedBulkFileField.value = ''
  isAddingBulkFilterField.value = false
  pendingBulkFilterFieldId.value = ''
  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedLinkedPrimaryEntityType.value = ''
  selectedLinkedSecondaryEntityType.value = ''
  selectedHrEntityType.value = ''
  selectedFileAttachEntityType.value = ''
  selectedSmartProcessId.value = ''
  entityType.value = ''
  departmentsExpanded.value = false
  resetMessages()
}

function finishToEntitySelection() {
  resetBulkAttachExecutionState()
  resetFlowState()
  clearSelectedFile()
  goBackToFamilySelection()
  currentStep.value = 1
}

function finishInlineBulkAttachFlow() {
  resetBulkAttachExecutionState()
  bulkFilterPreview.value = null
  clearSelectedFile()
  resetMessages()
}

function updateDedupStrategySelection(value: string) {
  const normalizedValue = String(value || 'create').trim()
  if (
    isSimpleImportMode.value
    && normalizedValue !== 'create'
    && !simpleDedupPreset.value.available
  ) {
    dedupStrategy.value = 'create'
    return
  }

  dedupStrategy.value = normalizedValue
}

function updateLinkedDedupStrategySelection(entityId: string, value: string) {
  const normalizedEntityId = String(entityId || '').trim().toLowerCase()
  if (!normalizedEntityId) {
    return
  }

  const nextState = normalizeDedupState({
    ...createDefaultDedupState(),
    ...(linkedDedupSettings.value[normalizedEntityId] || {}),
    strategy: value,
  })

  if (nextState.strategy === 'create') {
    nextState.fields = []
  }

  linkedDedupSettings.value = {
    ...linkedDedupSettings.value,
    [normalizedEntityId]: nextState,
  }
  skippedDedupStep.value = false
}

function toggleLinkedDedupField(entityId: string, fieldId: string) {
  const normalizedEntityId = String(entityId || '').trim().toLowerCase()
  const normalizedFieldId = String(fieldId || '').trim()
  if (!normalizedEntityId || !normalizedFieldId) {
    return
  }

  const currentState = normalizeDedupState(linkedDedupSettings.value[normalizedEntityId] || createDefaultDedupState())
  if (currentState.strategy === 'create') {
    return
  }

  const nextFields = currentState.fields.includes(normalizedFieldId)
    ? currentState.fields.filter((value) => value !== normalizedFieldId)
    : [...currentState.fields, normalizedFieldId]

  linkedDedupSettings.value = {
    ...linkedDedupSettings.value,
    [normalizedEntityId]: {
      ...currentState,
      fields: nextFields,
    },
  }
  skippedDedupStep.value = false
}

function updateLinkedDedupCondition(entityId: string, value: 'any' | 'all') {
  const normalizedEntityId = String(entityId || '').trim().toLowerCase()
  if (!normalizedEntityId) {
    return
  }

  linkedDedupSettings.value = {
    ...linkedDedupSettings.value,
    [normalizedEntityId]: {
      ...normalizeDedupState(linkedDedupSettings.value[normalizedEntityId] || createDefaultDedupState()),
      condition: value === 'all' ? 'all' : 'any',
    },
  }
  skippedDedupStep.value = false
}

async function toggleDepartments() {
  if (departmentsExpanded.value) {
    departmentsExpanded.value = false
    return
  }
  departmentsExpanded.value = true
  if (departments.value.length > 0 || loadingDepartments.value) return
  loadingDepartments.value = true
  try {
    const response = await apiStore.getImportDepartments()
    departments.value = Array.isArray(response.items) ? response.items : []
  } catch {
    departments.value = []
  } finally {
    loadingDepartments.value = false
  }
}

async function loadSmartProcesses() {
  loadingSmartProcesses.value = true
  try {
    const response = await apiStore.getImportSmartProcesses()
    smartProcesses.value = Array.isArray(response.items) ? response.items : []
  } catch {
    smartProcesses.value = []
  } finally {
    loadingSmartProcesses.value = false
  }
}

function updateScenarioEntityType(family: 'crm' | 'task' | 'linked' | 'hr', value: string) {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) {
    return
  }

  if (family === 'crm') {
    selectedCrmEntityType.value = normalizedValue
    selectedTaskEntityType.value = ''
    selectedLinkedPrimaryEntityType.value = ''
    selectedLinkedSecondaryEntityType.value = ''
    selectedHrEntityType.value = ''
    selectedFileAttachEntityType.value = ''
    if (normalizedValue !== 'smart_process') {
      selectedSmartProcessId.value = ''
    }
  } else if (family === 'task') {
    selectedTaskEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedLinkedPrimaryEntityType.value = ''
    selectedLinkedSecondaryEntityType.value = ''
    selectedHrEntityType.value = ''
    selectedFileAttachEntityType.value = ''
    selectedSmartProcessId.value = ''
  } else if (family === 'linked') {
    const linkedStrategyPair = resolveLinkedStrategyPair(normalizedValue)
    selectedLinkedPrimaryEntityType.value = linkedStrategyPair.primaryEntityType
    selectedLinkedSecondaryEntityType.value = linkedStrategyPair.secondaryEntityType
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedHrEntityType.value = ''
    selectedFileAttachEntityType.value = ''
    selectedSmartProcessId.value = ''
  } else {
    selectedHrEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedLinkedPrimaryEntityType.value = ''
    selectedLinkedSecondaryEntityType.value = ''
    selectedFileAttachEntityType.value = ''
    selectedSmartProcessId.value = ''
  }

  selectedFamily.value = family === 'linked' ? 'crm' : family
  entityType.value = normalizedValue
  resetMessages()
}

function setSelectedFileAttachEntityType(value: string) {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) return

  selectedFileAttachEntityType.value = normalizedValue
  selectedCrmEntityType.value = ''
  selectedLinkedPrimaryEntityType.value = ''
  selectedLinkedSecondaryEntityType.value = ''
  selectedHrEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedSmartProcessId.value = ''
  selectedFamily.value = 'crm'
  entityType.value = normalizedValue
  currentView.value = 'wizard'
  resetMessages()
}

function selectBulkFileAttachEntityType(value: string) {
  setSelectedFileAttachEntityType(value)
}

function startBulkAttachSetup() {
  resetMessages()

  const normalizedEntityType = String(selectedBulkAttachEntityType.value || '').trim()
  const normalizedFieldId = String(selectedBulkFileField.value || '').trim()

  if (!normalizedEntityType) {
    setError(isTaskBulkAttachFlow.value
      ? 'Выберите сценарий «Вложения задач».'
      : 'Выберите CRM-сущность для массового добавления файлов.')
    return
  }

  if (!isTaskBulkAttachFlow.value && !normalizedFieldId) {
    setError('Выберите поле типа «Файл», куда нужно прикреплять вложение.')
    return
  }

  if (!selectedFile.value) {
    setError('Выберите файл для массового добавления.')
    return
  }

  if (!bulkFilterPreview.value) {
    setError('Сначала проверьте выборку записей по фильтру.')
    return
  }

  const plainType = normalizedEntityType.replace(/^crm_files_/, '')
  const filter = buildBulkFilterPayload()

  resetBulkAttachExecutionState()
  bulkAttachProgressTotal.value = Number(bulkFilterPreview.value.total || 0)
  busyAction.value = 'bulk-attach-run'

  Promise.resolve()
    .then(async () => {
      const uploadResponse = await apiStore.uploadBulkAttachFile(selectedFile.value as File)
      const created = await apiStore.createBulkAttachSession({
        entity_type: plainType,
        filter,
        file_id: String(uploadResponse.file_id || '').trim(),
        file_name: String(uploadResponse.file_name || selectedFile.value?.name || '').trim(),
        ...(isTaskBulkAttachFlow.value ? {} : { field_id: normalizedFieldId }),
      })

      const sessionId = String(created.item?.id || '').trim()
      if (!sessionId) {
        throw new Error('Не удалось создать сессию массовой загрузки.')
      }

      bulkAttachSessionId.value = sessionId
      bulkAttachSessionStatus.value = 'running'

      const runResponse = await apiStore.runBulkAttachSession(sessionId)
      applyBulkAttachSnapshot(runResponse.item, runResponse.result)

      if (String(runResponse.item?.status || '').trim().toLowerCase() === 'running') {
        startBulkAttachPolling(sessionId)
        setSuccess('Загрузка запущена. Следим за выполнением прямо в этом блоке.')
        return
      }

      setSuccess('Загрузка файла завершена.')
    })
    .catch((error: unknown) => {
      resetBulkAttachExecutionState()
      setError(error instanceof Error ? error.message : String(error))
    })
    .finally(() => {
      if (busyAction.value === 'bulk-attach-run') {
        busyAction.value = ''
      }
    })
}

function updateLinkedPrimaryEntityType(value: string) {
  const normalizedValue = String(value || '').trim()
  selectedLinkedPrimaryEntityType.value = normalizedValue

  const allowedSecondaryValues = new Set(linkedSecondaryEntityItems.value.map((item) => String(item?.value || '').trim()))
  if (!allowedSecondaryValues.has(selectedLinkedSecondaryEntityType.value)) {
    selectedLinkedSecondaryEntityType.value = ''
  }

  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedHrEntityType.value = ''
  selectedFileAttachEntityType.value = ''
  selectedSmartProcessId.value = ''
  selectedFamily.value = 'crm'

  const resolvedStrategyEntityType = resolveLinkedStrategyEntityType(
    selectedLinkedPrimaryEntityType.value,
    selectedLinkedSecondaryEntityType.value,
  )
  entityType.value = resolvedStrategyEntityType
  resetMessages()
}

function updateLinkedSecondaryEntityType(value: string) {
  selectedLinkedSecondaryEntityType.value = String(value || '').trim()
  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedHrEntityType.value = ''
  selectedFileAttachEntityType.value = ''
  selectedSmartProcessId.value = ''
  selectedFamily.value = 'crm'
  entityType.value = resolveLinkedStrategyEntityType(
    selectedLinkedPrimaryEntityType.value,
    selectedLinkedSecondaryEntityType.value,
  )
  resetMessages()
}

async function refreshMapping() {
  if (!session.value?.id) {
    return
  }

  const response = await apiStore.getImportMapping(String(session.value.id), importModeMeta.value.value)
  mappingData.value = response.item
  validationData.value = null
  dryRunData.value = null
  preimportScanData.value = null
  importRunData.value = null
  importExecutionStage.value = 'idle'
  syncMappingRows()
  await Promise.all([
    refreshTemplates(),
    refreshAliasRules(),
  ])
}

async function refreshTemplates() {
  const response = await apiStore.getImportTemplates(entityType.value, selectedSmartProcessConfig.value)
  importTemplates.value = (Array.isArray(response.items) ? response.items : []).map((item: Record<string, any>) => ({
    id: String(item.id || ''),
    name: String(item.name || ''),
  })).filter((item) => item.id && item.name)

  if (selectedTemplateId.value && !importTemplates.value.find((item) => item.id === selectedTemplateId.value)) {
    selectedTemplateId.value = ''
  }
}

async function refreshAliasRules() {
  if (!entityType.value) {
    importAliasRules.value = []
    return
  }

  if (!importerPermissionState.value.canManageTemplates) {
    importAliasRules.value = Array.isArray(mappingData.value?.alias_rules) ? mappingData.value.alias_rules : []
    return
  }

  const response = await apiStore.getImportAliasRules(
    entityType.value,
    selectedSmartProcessConfig.value,
    importModeMeta.value.value,
  )
  importAliasRules.value = Array.isArray(response.items) ? response.items : []
}

function openFilePicker() {
  if (
    !importerPermissionState.value.canCreateSessions
    || busyAction.value
    || (isBulkAttachFlow.value && isBulkFilePickerLocked.value)
  ) {
    return
  }

  fileInputRef.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  resetMessages()
  resetBulkAttachExecutionState()
  dryRunData.value = null
  preimportScanData.value = null
  importRunData.value = null
  importExecutionStage.value = 'idle'

  const nextFile = target.files?.[0] || null
  if (nextFile && isSpreadsheetUploadRequired.value && !detectSourceFormat(nextFile.name)) {
    selectedFile.value = null
    target.value = ''
    setError('Неподдерживаемый формат файла. Загрузите файл в формате .xlsx, .xls или .csv.')
    return
  }
  if (nextFile && nextFile.size > MAX_IMPORT_FILE_SIZE_BYTES) {
    selectedFile.value = null
    target.value = ''
    setError(buildImportFileSizeErrorMessage(nextFile))
    return
  }

  selectedFile.value = nextFile
}

function handleDropFile(event: DragEvent) {
  dropzoneDragOver.value = false
  if (
    !importerPermissionState.value.canCreateSessions
    || busyAction.value
    || (isBulkAttachFlow.value && isBulkFilePickerLocked.value)
  ) return
  const file = event.dataTransfer?.files?.[0] || null
  if (!file) return
  resetMessages()
  resetBulkAttachExecutionState()
  dryRunData.value = null
  preimportScanData.value = null
  importRunData.value = null
  importExecutionStage.value = 'idle'
  if (isSpreadsheetUploadRequired.value && !detectSourceFormat(file.name)) {
    setError('Неподдерживаемый формат файла. Загрузите файл в формате .xlsx, .xls или .csv.')
    return
  }
  if (file.size > MAX_IMPORT_FILE_SIZE_BYTES) {
    setError(buildImportFileSizeErrorMessage(file))
    return
  }
  selectedFile.value = file
}

async function startImporterSetup() {
  resetMessages()

  if (!selectedFile.value) {
    setError('Сначала выберите файл для импорта.')
    return
  }

  if (!entityType.value) {
    setError('Сначала выберите сущность для импорта.')
    return
  }

  if (entityType.value === 'smart_process' && !selectedSmartProcessConfig.value?.entityTypeId) {
    setError('Сначала выберите конкретный смарт-процесс.')
    return
  }

  if (!sourceFormat.value) {
    setError('Можно загрузить только файлы .xlsx, .xls или .csv.')
    return
  }

  if (selectedFile.value.size > MAX_IMPORT_FILE_SIZE_BYTES) {
    setError(buildImportFileSizeErrorMessage(selectedFile.value))
    return
  }

  try {
    const slice = await selectedFile.value.slice(0, 4).arrayBuffer()
    const b = new Uint8Array(slice)
    if (sourceFormat.value === 'xls') {
      const ok = b[0] === 0xD0 && b[1] === 0xCF && b[2] === 0x11 && b[3] === 0xE0
      if (!ok) {
        setError('Файл имеет расширение .xls, но его содержимое не соответствует формату Excel. Такое бывает с выгрузками из браузера, Google Аналитики или Search Console — откройте файл в Excel и пересохраните как .xlsx или .csv.')
        return
      }
    }
    if (sourceFormat.value === 'xlsx') {
      const ok = b[0] === 0x50 && b[1] === 0x4B && b[2] === 0x03 && b[3] === 0x04
      if (!ok) {
        setError('Файл имеет расширение .xlsx, но его содержимое повреждено или не соответствует формату. Попробуйте пересохранить файл в Excel заново.')
        return
      }
    }
  } catch {}

  busyAction.value = 'start'
  resetFlowState()
  currentStep.value = 1

  try {
    const createResponse = await apiStore.createImportSession({
      entity_type: entityType.value,
      source_format: sourceFormat.value,
      original_filename: selectedFile.value.name,
      import_mode: importModeMeta.value.value,
      ...(selectedSmartProcessConfig.value ? { entity_config: selectedSmartProcessConfig.value } : {}),
    })
    session.value = createResponse.item

    await apiStore.uploadImportFile(String(session.value.id), selectedFile.value)

    const previewResponse = await apiStore.getImportPreview(String(session.value.id))
    preview.value = previewResponse.item
    headerRowInput.value = Number(previewResponse.item.header_row || 1)
    dataStartRowInput.value = Number(previewResponse.item.data_start_row || 2)

    await refreshMapping()
    setSuccess('Файл загружен. Можно проверить структуру и заполнить соответствие полей.')
    currentStep.value = 2
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function applyStructure() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  busyAction.value = 'structure'

  try {
    const previewResponse = await apiStore.updateImportPreview(String(session.value.id), {
      header_row: Number(headerRowInput.value),
      data_start_row: Number(dataStartRowInput.value),
    })
    preview.value = previewResponse.item
    headerRowInput.value = Number(previewResponse.item.header_row || 1)
    dataStartRowInput.value = Number(previewResponse.item.data_start_row || 2)

    await refreshMapping()
    setSuccess('Параметры чтения файла обновлены.')
    currentStep.value = 3
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

function applyCandidateMapping() {
  if (!mappingData.value) {
    return
  }

  const newRows = buildMappingRows({
    headers: mappingData.value.headers,
    columns: mappingData.value.columns,
    fields: mappingData.value.fields,
    candidateMapping: mappingData.value.candidate_mapping,
    candidateSuggestions: mappingData.value.candidate_suggestions,
    savedMapping: {},
  })

  const mappedCount = newRows.filter((row) => row.targetFieldId).length
  if (mappedCount === 0) {
    setError('Не удалось автоматически подобрать соответствие. Проверьте, что заголовки колонок в файле совпадают с названиями полей Bitrix24.')
    return
  }

  mappingRows.value = newRows
  validationData.value = null
  dryRunData.value = null
  preimportScanData.value = null
  importRunData.value = null
  importExecutionStage.value = 'idle'
  setSuccess(`Расставлено ${mappedCount} соответствий автоматически. Проверьте результат перед сохранением.`)
}

function updateMappingFieldSelection(row: MappingRow, value: string) {
  const nextTargetFieldId = normalizeMappingSelectValue(value)
  if (row.targetFieldId !== nextTargetFieldId) {
    row.valueMapping = {}
  }

  row.targetFieldId = nextTargetFieldId
  const selectedField = fieldOptionsIndex.value.get(nextTargetFieldId)
  row.targetFieldTitle = nextTargetFieldId ? String(selectedField?.title || nextTargetFieldId) : ''
  row.targetFieldType = nextTargetFieldId ? String(selectedField?.type || '') : ''
  row.targetFieldTypeLabel = nextTargetFieldId
    ? buildFieldTypeLabel(selectedField?.type)
    : ''
  row.targetFieldRequired = Boolean(selectedField?.required)
  row.targetFieldIsCustom = Boolean(selectedField?.is_custom)
  row.targetFieldIsMultiple = Boolean(selectedField?.multiple)
  row.targetFieldGuidanceHints = selectedField ? buildFieldGuidanceHints(selectedField) : []
  row.autoMatchType = ''
  row.autoMatchLabel = ''
  row.autoMatchReason = ''
  row.autoMatchReasonLabel = ''
}

async function saveImportAliasRule(row: MappingRow) {
  if (!session.value?.id || !row.targetFieldId || !row.sourceHeader || !importerPermissionState.value.canManageTemplates) {
    return
  }

  if (hasImportAliasRule(row)) {
    setSuccess('Такое правило сопоставления уже сохранено.')
    return
  }

  resetMessages()
  busyAction.value = 'alias-rule'

  try {
    const response = await apiStore.saveImportAliasRule(
      String(session.value.id),
      row.sourceHeader,
      row.targetFieldId,
    )
    const savedRule = response.item && typeof response.item === 'object' ? response.item : null
    if (savedRule) {
      const sourceLabel = normalizeAliasRuleSourceLabel(String(savedRule.source_label || ''))
      importAliasRules.value = [
        savedRule,
        ...importAliasRules.value.filter((item) => (
          normalizeAliasRuleSourceLabel(String(item?.source_label || '')) !== sourceLabel
        )),
      ]
    }
    setSuccess(`Правило сохранено: «${row.sourceHeader}» → «${row.targetFieldTitle || row.targetFieldId}».`)
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

function onMappingDragStart(index: number, event: DragEvent) {
  mappingDragSourceIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function onMappingDragOver(index: number, event: DragEvent) {
  event.preventDefault()
  if (mappingDragSourceIndex.value !== null && mappingDragSourceIndex.value !== index) {
    mappingDragOverIndex.value = index
  }
}

function onMappingDragLeave() {
  mappingDragOverIndex.value = null
}

function onMappingDrop(toIndex: number, event: DragEvent) {
  event.preventDefault()
  const fromIndex = mappingDragSourceIndex.value
  if (fromIndex === null || fromIndex === toIndex) {
    mappingDragSourceIndex.value = null
    mappingDragOverIndex.value = null
    return
  }
  const rows = [...mappingRows.value]
  const [moved] = rows.splice(fromIndex, 1)
  rows.splice(toIndex, 0, moved)
  mappingRows.value = rows
  mappingDragSourceIndex.value = null
  mappingDragOverIndex.value = null
}

function onMappingDragEnd() {
  mappingDragSourceIndex.value = null
  mappingDragOverIndex.value = null
}

function updateValueMappingSelection(targetFieldId: string, sourceValue: string, targetValue: string) {
  const mappingRow = mappingRows.value.find((row) => row.targetFieldId === targetFieldId)
  if (!mappingRow) {
    return
  }

  const currentValueMapping = { ...(mappingRow.valueMapping || {}) }
  const normalizedSourceValue = String(sourceValue || '').trim()
  const normalizedTargetValue = String(targetValue || '').trim()
  if (!normalizedSourceValue) {
    return
  }

  if (!normalizedTargetValue) {
    delete currentValueMapping[normalizedSourceValue]
  } else {
    currentValueMapping[normalizedSourceValue] = normalizedTargetValue
  }

  mappingRow.valueMapping = currentValueMapping
}

function toggleDedupField(fieldId: string) {
  if (dedupStrategy.value === 'create') {
    return
  }

  skippedDedupStep.value = false

  if (dedupFields.value.includes(fieldId)) {
    dedupFields.value = dedupFields.value.filter((value) => value !== fieldId)
    return
  }

  dedupFields.value = [...dedupFields.value, fieldId]
}

async function saveMapping() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  busyAction.value = 'mapping'

  try {
    const response = await apiStore.saveImportMapping(
      String(session.value.id),
      buildMappingPayload(mappingRows.value),
      currentDedupSettingsPayload.value,
      importModeMeta.value.value,
      {
        default_responsible_id: taskDefaultResponsibleId.value,
        default_creator_id: taskDefaultCreatorId.value,
        default_comment_author_id: taskDefaultCommentAuthorId.value,
      },
    )
    mappingData.value = response.item
    validationData.value = null
    dryRunData.value = null
    preimportScanData.value = null
    importRunData.value = null
    importExecutionStage.value = 'idle'
    syncMappingRows()
    setSuccess(
      Number(response.item?.unmapped_value_count || 0) > 0
        ? `Соответствие полей сохранено. Осталось сопоставить значений: ${Number(response.item?.unmapped_value_count || 0)}.`
        : 'Соответствие полей сохранено.',
    )
    if (!isDedupApplicable.value) {
      currentStep.value = 5
    }
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function saveDedupSettings() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  busyAction.value = 'dedup'

  try {
    await persistDedupSettings()

    if (hasBlockingPreflightIssues.value) {
      const dedupIssues = mappingPreflightIssues.value.filter(
        (issue: any) => String(issue?.code || '').trim() === 'dedup_field_unmapped',
      )
      if (dedupIssues.length > 0) {
        const descriptions = dedupIssues.map((issue: any) => buildPreflightIssueDescription(issue)).join(' ')
        setError(`${descriptions} Добавьте поле в шаг «Маппинг полей» или уберите его из настроек поиска дублей.`)
      } else {
        setError('Маппинг содержит ошибки, мешающие запуску. Проверьте настройки на шаге «Маппинг полей».')
      }
      return
    }

    currentStep.value = 6
    setSuccess('Правила обработки дублей сохранены.')
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function persistDedupSettings() {
  if (!session.value?.id) {
    return null
  }

  const response = await apiStore.saveImportMapping(
    String(session.value.id),
    buildMappingPayload(mappingRows.value),
    currentDedupSettingsPayload.value,
    importModeMeta.value.value,
    {
      default_responsible_id: taskDefaultResponsibleId.value,
      default_creator_id: taskDefaultCreatorId.value,
      default_comment_author_id: taskDefaultCommentAuthorId.value,
    },
  )
  mappingData.value = response.item
  validationData.value = null
  dryRunData.value = null
  preimportScanData.value = null
  importRunData.value = null
  importExecutionStage.value = 'idle'
  syncMappingRows()
  return response.item
}

async function persistDedupSettingsIfNeeded() {
  if (!hasPendingDedupChanges.value) {
    return null
  }

  return await persistDedupSettings()
}

async function skipDedupStep() {
  if (!session.value?.id || !isDedupApplicable.value) {
    return
  }

  if (isLinkedImportEntityType(entityType.value)) {
    linkedDedupSettings.value = linkedDedupEntityGroups.value.reduce((result, group) => {
      result[group.id] = createDefaultDedupState()
      return result
    }, {} as Record<string, { strategy: string, condition: 'any' | 'all', fields: string[] }>)
  }
  dedupStrategy.value = 'create'
  dedupFields.value = []
  dedupCondition.value = 'any'
  skippedDedupStep.value = true
  await runDedupCheck({ skippedDedup: true })
}

async function saveTemplate() {
  if (!session.value?.id || !templateNameInput.value.trim()) {
    return
  }

  resetMessages()
  busyAction.value = 'template-save'

  try {
    const response = await apiStore.saveImportTemplate(
      String(session.value.id),
      templateNameInput.value.trim(),
      buildMappingPayload(mappingRows.value),
      currentDedupSettingsPayload.value,
    )
    await refreshTemplates()
    selectedTemplateId.value = String(response.item?.id || '')
    templateNameInput.value = String(response.item?.name || templateNameInput.value.trim())
    setSuccess('Шаблон импорта сохранен.')
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function applyTemplate() {
  if (!session.value?.id || !selectedTemplateId.value) {
    return
  }

  resetMessages()
  busyAction.value = 'template-apply'

  try {
    const response = await apiStore.applyImportTemplate(
      String(session.value.id),
      selectedTemplateId.value,
    )
    headerRowInput.value = Number(response.item?.header_row || headerRowInput.value)
    dataStartRowInput.value = Number(response.item?.data_start_row || dataStartRowInput.value)

    const previewResponse = await apiStore.getImportPreview(String(session.value.id))
    preview.value = previewResponse.item
    headerRowInput.value = Number(previewResponse.item.header_row || headerRowInput.value)
    dataStartRowInput.value = Number(previewResponse.item.data_start_row || dataStartRowInput.value)

    await refreshMapping()
    currentStep.value = 4
    setSuccess('Шаблон применен к текущей сессии.')
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function executeValidation({
  persistDedup = true,
  resetStatus = true,
  busyState = 'validation',
  nextStep = 6,
}: {
  persistDedup?: boolean
  resetStatus?: boolean
  busyState?: string
  nextStep?: number | null
} = {}) {
  if (!session.value?.id) {
    return null
  }

  if (resetStatus) {
    resetMessages()
  }

  if (unmappedValueSummary.value.hasUnmappedValues) {
    setError('Сначала сопоставьте все значения статусов и списков.')
    return null
  }
  busyAction.value = busyState

  try {
    if (persistDedup) {
      await persistDedupSettingsIfNeeded()
    }
    const response = await apiStore.validateImportSession(String(session.value.id))
    validationData.value = response.item
    dryRunData.value = null
    preimportScanData.value = null
    activeDryRunDedupRiskOnly.value = false
    importRunData.value = null
    importExecutionStage.value = 'idle'
    if (typeof nextStep === 'number') {
      currentStep.value = nextStep
    }
    setSuccess(
      validationIssueCount.value > 0
        ? 'Проверка завершена. Исправьте строки с ошибками перед следующим этапом.'
        : 'Проверка завершена. Критичных ошибок не найдено.',
    )
    return response.item
  } catch (error) {
    throw error
  } finally {
    busyAction.value = ''
  }
}

async function runValidation() {
  try {
    await executeValidation()
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  }
}

async function ensureValidationBeforeExecution() {
  if (validationData.value) {
    return validationData.value
  }

  return await executeValidation({
    persistDedup: false,
    resetStatus: false,
    busyState: 'validation',
    nextStep: null,
  })
}

async function runSamplePreview({ skippedDedup = false }: { skippedDedup?: boolean } = {}) {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  busyAction.value = 'sample-preview'
  importExecutionStage.value = 'sample-preview'

  try {
    await persistDedupSettingsIfNeeded()
    const validationResult = await ensureValidationBeforeExecution()
    if (!validationResult && !validationData.value) {
      return
    }
    if (!skippedDedup) {
      skippedDedupStep.value = false
    }
    busyAction.value = 'sample-preview'
    const dryRunResult = await executeDryRunRequest(String(session.value.id), {
      mode: 'preimport_scan',
      target: 'full',
      runningStep: 6,
      resolvedStep: 6,
      cancelledStep: 6,
    })
    if (dryRunResult?.status === 'cancelled' || dryRunResult?.cancelled) {
      importExecutionStage.value = 'idle'
      setSuccess('Тестовый импорт остановлен. Можно скорректировать настройки и запустить его повторно.')
      return
    }
    importExecutionStage.value = Number(dryRunResult?.pending_decision_rows || 0) > 0 ? 'duplicate-decisions' : 'idle'
    setSuccess(
      Number(dryRunResult?.pending_decision_rows || 0) > 0
        ? 'Тестовый импорт завершён. Выберите действие для найденных дублей, затем отдельно запустите реальный импорт.'
        : Number(dryRunResult?.skipped_rows || 0) > 0
        ? 'Тестовый импорт завершён. Полный файл проверен, часть строк будет пропущена.'
        : skippedDedup
        ? 'Шаг дублей пропущен. Тестовый импорт проверил весь файл по правилу «Всегда создавать».'
        : 'Тестовый импорт завершён. Полный файл проверен, можно запускать реальный импорт.',
    )
  } catch (error) {
    importExecutionStage.value = 'idle'
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function runDedupCheck({ skippedDedup = false }: { skippedDedup?: boolean } = {}) {
  await runSamplePreview({ skippedDedup })
}

async function executeImportRunRequest() {
  if (!session.value?.id) {
    return
  }

  try {
    if (requiresPerRowDedupDecision.value && hasUnresolvedPendingDedupDecisions.value) {
      importExecutionStage.value = 'duplicate-decisions'
      currentStep.value = 6
      setError('Выберите действие для каждой строки с найденным дублем.')
      return
    }

    if (!await confirmMassCreateImport()) {
      setError('Импорт остановлен. Подтвердите массовое создание новых CRM-записей, если это ожидаемое действие.')
      return
    }

    busyAction.value = 'run'
    importExecutionStage.value = 'running'
    session.value = session.value ? { ...session.value, status: 'running' } : session.value
    const response = await apiStore.runImportSession(String(session.value.id), perRowDedupDecisions.value)
    const queuedImportRun = await resolveImportExecutionResult(String(session.value.id), response.item)
    importRunData.value = queuedImportRun
    currentStep.value = 7
    importExecutionStage.value = 'idle'
    const completionNotice = buildImportRunCompletionNotice(queuedImportRun, { mode: 'run' })
    if (completionNotice.type === 'error') {
      setError(completionNotice.message)
    } else {
      setSuccess(completionNotice.message)
    }
  } catch (error) {
    importExecutionStage.value = 'idle'
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    cancelRequested.value = false
    busyAction.value = ''
  }
}

async function runImport() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  cancelRequested.value = false

  try {
    await persistDedupSettingsIfNeeded()
    const validationResult = await ensureValidationBeforeExecution()
    if (!validationResult && !validationData.value) {
      return
    }

    if (!preimportScanData.value) {
      currentStep.value = 6
      importExecutionStage.value = 'idle'
      setError('Сначала запустите тестовый импорт по всему файлу.')
      return
    }

    await executeImportRunRequest()
  } catch (error) {
    importExecutionStage.value = 'idle'
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    cancelRequested.value = false
  }
}

async function executeDryRunRequest(
  sessionId: string,
  {
    mode = 'sample_preview',
    target = 'sample',
    runningStep = 6,
    resolvedStep = 6,
    cancelledStep = runningStep,
  }: {
    mode?: string
    target?: 'sample' | 'scan' | 'full'
    runningStep?: number
    resolvedStep?: number
    cancelledStep?: number
  } = {},
) {
  const response = await apiStore.dryRunImportSession(sessionId, { mode })
  if (target === 'sample') {
    dryRunData.value = null
  } else if (target === 'scan') {
    preimportScanData.value = null
  } else {
    dryRunData.value = null
    preimportScanData.value = null
  }
  activeDryRunDedupRiskOnly.value = false
  importRunData.value = null
  currentStep.value = runningStep
  const dryRunResult = await resolveDryRunExecutionResult(sessionId, response.item, mode)
  if (target === 'sample') {
    dryRunData.value = dryRunResult
  } else if (target === 'scan') {
    preimportScanData.value = dryRunResult
  } else {
    dryRunData.value = dryRunResult
    preimportScanData.value = dryRunResult
  }
  currentStep.value = dryRunResult?.status === 'cancelled' || dryRunResult?.cancelled ? cancelledStep : resolvedStep
  return dryRunResult
}

async function confirmMassCreateImport() {
  if (!isDirectCrmEntityImport.value || dedupStrategy.value !== 'create') {
    return true
  }

  const readyCreateRows = Number(dryRunData.value?.ready_create_rows || dryRunData.value?.ready_rows || 0)
  if (readyCreateRows <= 0) {
    return true
  }

  if (typeof window === 'undefined' || typeof window.confirm !== 'function') {
    return true
  }

  const entityLabel = String(currentScenarioSummary.value?.selectedLabel || 'CRM-записи').trim().toLowerCase()
  const confirmMessage = [
    `Будет создано ${readyCreateRows.toLocaleString('ru-RU')} новых записей в разделе «${entityLabel}».`,
    'Существующие записи не будут обновлены, потому что сейчас выбрано правило дублей «Всегда создавать».',
    'Продолжить импорт?',
  ].join('\n\n')

  return window.confirm(confirmMessage)
}

async function retryFailedRows() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  cancelRequested.value = false
  busyAction.value = 'retry'
  session.value = session.value ? { ...session.value, status: 'running' } : session.value

  try {
    const response = await apiStore.retryFailedImportSession(String(session.value.id))
    const queuedImportRun = await resolveImportExecutionResult(String(session.value.id), response.item)
    importRunData.value = queuedImportRun
    currentStep.value = 7
    const completionNotice = buildImportRunCompletionNotice(queuedImportRun, { mode: 'retry' })
    if (completionNotice.type === 'error') {
      setError(completionNotice.message)
    } else {
      setSuccess(completionNotice.message)
    }
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    cancelRequested.value = false
    busyAction.value = ''
  }
}

async function cancelActiveImport() {
  if (!session.value?.id || !canCancelActiveImport.value) {
    return
  }

  resetMessages()
  cancelRequested.value = true

  try {
    const response = await apiStore.cancelImportSession(String(session.value.id))
    session.value = session.value ? { ...session.value, ...response.item } : response.item
    setSuccess(
      busyAction.value === 'sample-preview'
        ? 'Остановка запрошена. Текущая строка завершится, после чего тестовый импорт остановится.'
        : 'Остановка запрошена. Текущая строка завершится, после чего импорт остановится.',
    )
  } catch (error) {
    const cancelErrorStatus = Number((error as any)?.statusCode || (error as any)?.response?.status || 0)
    if (cancelErrorStatus === 400 && session.value?.id) {
      try {
        const latestResponse = await apiStore.getImportSession(String(session.value.id))
        const latestSession = latestResponse?.item && typeof latestResponse.item === 'object'
          ? latestResponse.item
          : null

        if (latestSession && String(latestSession.status || '').trim().toLowerCase() !== 'running') {
          session.value = session.value ? { ...session.value, ...latestSession } : latestSession
          syncRestoredExecutionState(latestSession)
          cancelRequested.value = false
          setSuccess('Импорт уже завершён или остановлен. Остановка больше не требуется.')
          return
        }
      } catch {
        // Ignore reload errors and show the original cancel error below.
      }
    }

    cancelRequested.value = false
    setError(error instanceof Error ? error.message : String(error))
  }
}

async function downloadImportReport() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  busyAction.value = 'report'

  try {
    const { blob, filename } = await apiStore.downloadImportSessionReportCsv(String(session.value.id))
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
    setSuccess('CSV-отчет подготовлен и скачан.')
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function downloadExampleTemplate() {
  if (!canDownloadExampleTemplate.value) {
    return
  }

  resetMessages()
  busyAction.value = 'example-template'

  try {
    const { blob, filename } = await apiStore.downloadImportExampleTemplateXlsx(
      entityType.value,
      selectedSmartProcessConfig.value,
    )
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    window.setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
    }, 1000)
    setSuccess(`Шаблон для «${currentScenarioSummary.value.selectedLabel}» скачан.`)
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function loadHistory() {
  historyLoadError.value = ''

  try {
    const response = await apiStore.listImportSessions()
    recentSessions.value = Array.isArray(response?.items) ? response.items : []
  } catch (error) {
    historyLoadError.value = error instanceof Error ? error.message : 'Не удалось загрузить историю импортов.'
  }
}

function syncSessionSnapshot(snapshot: Record<string, any> | null | undefined) {
  if (!snapshot || typeof snapshot !== 'object') {
    return
  }

  session.value = session.value ? { ...session.value, ...snapshot } : snapshot
}

function getSessionSnapshotId(snapshot: Record<string, any> | null | undefined) {
  return String(snapshot?.session_id || snapshot?.id || '').trim()
}

function syncPreviewSnapshot(snapshot: Record<string, any> | null | undefined) {
  const previewSnapshot = snapshot?.preview_data && typeof snapshot.preview_data === 'object'
    ? snapshot.preview_data
    : null

  preview.value = previewSnapshot
  headerRowInput.value = Number(previewSnapshot?.header_row || 1)
  dataStartRowInput.value = Number(previewSnapshot?.data_start_row || 2)
}

function applyHistoryScenarioSelection(snapshot: Record<string, any> | null | undefined) {
  const normalizedEntityType = String(snapshot?.entity_type || '').trim()
  if (!normalizedEntityType) {
    return
  }

  importMode.value = 'advanced'

  if (fileAttachCrmEntityItems.value.some((item) => String(item?.value || '').trim() === normalizedEntityType)) {
    selectBulkFileAttachEntityType(normalizedEntityType)
  } else if (crmScenarioItems.value.some((item) => String(item?.value || '').trim() === normalizedEntityType)) {
    updateScenarioEntityType('crm', normalizedEntityType)
  } else if (taskScenarioItems.value.some((item) => String(item?.value || '').trim() === normalizedEntityType)) {
    updateScenarioEntityType('task', normalizedEntityType)
  } else if (linkedScenarioItems.value.some((item) => String(item?.value || '').trim() === normalizedEntityType)) {
    updateScenarioEntityType('linked', normalizedEntityType)
  } else if (hrScenarioItems.value.some((item) => String(item?.value || '').trim() === normalizedEntityType)) {
    updateScenarioEntityType('hr', normalizedEntityType)
  } else {
    selectedFamily.value = 'crm'
    entityType.value = normalizedEntityType
  }

  const entityConfig = snapshot?.entity_config && typeof snapshot.entity_config === 'object'
    ? snapshot.entity_config
    : null
  if (normalizedEntityType === 'smart_process' && entityConfig?.entityTypeId) {
    selectedSmartProcessId.value = String(entityConfig.entityTypeId)
  }
}

function resolveRestoredCurrentStep(snapshot: Record<string, any> | null | undefined) {
  if (importRunData.value) {
    return 7
  }
  if (shouldWaitForImportExecutionSnapshot(snapshot)) {
    return 6
  }

  if (shouldWaitForDryRunExecutionSnapshot(snapshot)) {
    return 5
  }

  if (dryRunData.value) {
    return 6
  }

  if (preimportScanData.value) {
    return 6
  }

  if (validationData.value && !isDedupApplicable.value) {
    return 6
  }

  const savedMapping = sessionSavedMapping.value

  if (mappingData.value && Object.keys(savedMapping).length > 0) {
    return 5
  }

  if (mappingData.value) {
    return 4
  }

  if (preview.value) {
    return 2
  }

  if (session.value?.id) {
    return 2
  }

  return 1
}

function syncRestoredExecutionState(snapshot: Record<string, any> | null | undefined) {
  const summary = snapshot?.summary && typeof snapshot.summary === 'object' ? snapshot.summary : {}
  validationData.value = summary.validation && typeof summary.validation === 'object'
    ? summary.validation
    : null
  preimportScanData.value = buildDryRunSummaryFromSessionSnapshot(snapshot, { preferredMode: 'preimport_scan' })
  dryRunData.value = preimportScanData.value || buildDryRunSummaryFromSessionSnapshot(snapshot, { preferredMode: 'sample_preview' })
  importRunData.value = buildImportRunSummaryFromSessionSnapshot(snapshot)
  skippedDedupStep.value = false
  importExecutionStage.value = pendingDecisionRows.value.length ? 'duplicate-decisions' : 'idle'

  const job = summary.job && typeof summary.job === 'object' ? summary.job : {}
  const jobMode = String(job.mode || '').trim().toLowerCase()
  const jobState = String(job.state || '').trim().toLowerCase()
  const sessionStatus = String(snapshot?.status || '').trim().toLowerCase()
  const isTerminalSessionStatus = ['completed', 'failed', 'cancelled'].includes(sessionStatus)
  if (!isTerminalSessionStatus && ['queued', 'running'].includes(jobState)) {
    busyAction.value = jobMode === 'sample_preview' || jobMode === 'preimport_scan' || jobMode === 'dry_run'
      ? 'sample-preview'
      : jobMode === 'retry'
        ? 'retry'
      : jobMode === 'run'
          ? 'run'
          : ''
  } else {
    busyAction.value = ''
  }

  currentStep.value = resolveRestoredCurrentStep(snapshot)
}

async function resumeHistorySessionBackground(snapshot: Record<string, any> | null | undefined) {
  const sessionId = getSessionSnapshotId(snapshot)
  if (!sessionId) {
    return
  }

  if (shouldWaitForDryRunExecutionSnapshot(snapshot)) {
    const jobMode = String(snapshot?.summary?.job?.mode || '').trim().toLowerCase()
    const preferredMode = jobMode === 'sample_preview' ? 'sample_preview' : 'preimport_scan'
    busyAction.value = 'sample-preview'
    currentStep.value = 6

    try {
      const resolvedDryRun = await resolveDryRunExecutionResult(sessionId, snapshot, preferredMode)
      if (preferredMode === 'preimport_scan') {
        dryRunData.value = resolvedDryRun
        preimportScanData.value = resolvedDryRun
        importExecutionStage.value = Number(resolvedDryRun?.pending_decision_rows || 0) > 0 ? 'duplicate-decisions' : 'idle'
      } else {
        dryRunData.value = resolvedDryRun
        importExecutionStage.value = 'idle'
      }
      currentStep.value = 6
    } catch (error) {
      setError(error instanceof Error ? error.message : String(error))
    } finally {
      if (String(busyAction.value || '').trim() === 'sample-preview') {
        busyAction.value = ''
      }
    }

    return
  }

  if (!shouldWaitForImportExecutionSnapshot(snapshot)) {
    return
  }

  const jobMode = String(snapshot?.summary?.job?.mode || '').trim().toLowerCase()
  busyAction.value = jobMode === 'retry' ? 'retry' : 'run'
  currentStep.value = 6

  try {
    importRunData.value = await resolveImportExecutionResult(sessionId, snapshot)
    currentStep.value = 7
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    if (['run', 'retry'].includes(String(busyAction.value || '').trim())) {
      busyAction.value = ''
    }
  }
}

async function resumeHistorySession(sessionId: string) {
  if (!sessionId || restoringHistorySessionId.value) {
    return false
  }

  resetMessages()
  restoringHistorySessionId.value = sessionId
  isRestoringImporterSession.value = true

  try {
    const response = await apiStore.getImportSession(sessionId)
    const snapshot = response.item && typeof response.item === 'object' ? response.item : null
    if (!snapshot) {
      throw new Error('Не удалось загрузить сохранённую сессию импорта.')
    }

    resetFlowState()
    clearSelectedFile()
    currentView.value = 'wizard'
    const isBulkAttach = isBulkAttachSessionSnapshot(snapshot)

    if (!isBulkAttach) {
      applyHistoryScenarioSelection(snapshot)
    }

    if (isBulkAttach) {
      const bulkAttachSummary = snapshot.summary?.bulk_attach && typeof snapshot.summary.bulk_attach === 'object'
        ? snapshot.summary.bulk_attach
        : {}
      const bulkAttachMode = String(bulkAttachSummary.mode || '').trim().toLowerCase()
      const rawEntityType = String(bulkAttachSummary.entity_type || snapshot.entity_type || '').trim()
      const fieldId = String(bulkAttachSummary.field_id || '').trim()
      const filter = bulkAttachSummary.filter && typeof bulkAttachSummary.filter === 'object' ? bulkAttachSummary.filter : {}

      session.value = snapshot
      importMode.value = 'advanced'
      selectedCrmEntityType.value = ''
      selectedTaskEntityType.value = ''
      selectedLinkedPrimaryEntityType.value = ''
      selectedLinkedSecondaryEntityType.value = ''
      selectedHrEntityType.value = ''
      selectedSmartProcessId.value = ''
      currentView.value = 'wizard'

      if (
        bulkAttachMode === 'task'
        || rawEntityType === 'task'
        || String(snapshot.entity_type || '').trim() === 'task_attachment'
      ) {
        selectedFamily.value = 'task'
        crmFlavor.value = 'direct'
        selectedFileAttachEntityType.value = ''
        selectedTaskEntityType.value = 'task_attachment'
        entityType.value = 'task_attachment'
        await loadBulkAttachEntityFields('task_attachment')
      } else {
        const normalizedEntityType = rawEntityType.startsWith('crm_files_') ? rawEntityType : `crm_files_${rawEntityType}`
        selectedFamily.value = 'crm'
        crmFlavor.value = 'bulk'
        selectedFileAttachEntityType.value = normalizedEntityType
        entityType.value = normalizedEntityType
        await loadBulkAttachEntityFields(normalizedEntityType)
      }

      selectedBulkFileField.value = fieldId
      bulkFilterConditions.value = Object.entries(filter).map(([filterFieldId, value]) => ({
        fieldId: String(filterFieldId || '').trim(),
        value: String(value || '').trim(),
      })).filter((row) => row.fieldId && row.value)
      bulkFilterPreview.value = buildBulkAttachPreviewFromSnapshot(snapshot)
      applyBulkAttachSnapshot(snapshot)

      if (String(snapshot.status || '').trim().toLowerCase() === 'running' && bulkAttachSessionId.value) {
        startBulkAttachPolling(bulkAttachSessionId.value)
      }
    } else {
      session.value = snapshot
      syncPreviewSnapshot(snapshot)

      if (preview.value) {
        await refreshMapping()
      }

      syncRestoredExecutionState(snapshot)
      currentView.value = 'wizard'

      if (
        shouldWaitForDryRunExecutionSnapshot(snapshot)
        || shouldWaitForImportExecutionSnapshot(snapshot)
      ) {
        void resumeHistorySessionBackground(snapshot)
      }
    }

    setSuccess(`Сессия «${String(snapshot.original_filename || 'Без имени')}» восстановлена.`)
    await loadHistory()
    return true
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
    return false
  } finally {
    isRestoringImporterSession.value = false
    restoringHistorySessionId.value = ''
  }
}

function buildImportRunFromSnapshot(snapshot: Record<string, any> | null | undefined) {
  return buildImportRunSummaryFromSessionSnapshot(snapshot)
}

function buildDryRunFromSnapshot(snapshot: Record<string, any> | null | undefined) {
  return buildDryRunSummaryFromSessionSnapshot(snapshot, { preferredMode: 'preimport_scan' })
}

function buildPreimportScanFromSnapshot(snapshot: Record<string, any> | null | undefined) {
  return buildDryRunSummaryFromSessionSnapshot(snapshot, { preferredMode: 'preimport_scan' })
}

function buildCancelledDryRunSummary(snapshot: Record<string, any> | null | undefined) {
  const processedRows = Number(snapshot?.processed_rows || 0)
  const totalRows = Number(snapshot?.total_rows || 0)
  return {
    session_id: getSessionSnapshotId(snapshot),
    status: 'cancelled',
    checked_rows: processedRows,
    ready_rows: Number(snapshot?.successful_rows || 0),
    ready_create_rows: 0,
    ready_update_rows: 0,
    skipped_rows: Number(snapshot?.failed_rows || 0),
    pending_decision_rows: 0,
    cancelled: true,
    cancelled_rows: Math.max(0, totalRows - processedRows),
    remaining_rows: Math.max(0, totalRows - processedRows),
    results: [],
  }
}

function buildCancelledImportRunSummary(snapshot: Record<string, any> | null | undefined) {
  const processedRows = Number(snapshot?.processed_rows || 0)
  const totalRows = Number(snapshot?.total_rows || 0)
  return {
    session_id: getSessionSnapshotId(snapshot),
    status: 'cancelled',
    checked_rows: processedRows,
    created_rows: Number(snapshot?.successful_rows || 0),
    updated_rows: 0,
    failed_rows: Number(snapshot?.failed_rows || 0),
    skipped_rows: 0,
    cancelled: true,
    cancelled_rows: Math.max(0, totalRows - processedRows),
    remaining_rows: Math.max(0, totalRows - processedRows),
    created_ids: [],
    updated_ids: [],
    results: [],
  }
}

async function waitForDryRunExecutionResult(sessionId: string) {
  const maxAttempts = 600

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await apiStore.getImportSession(sessionId)
    const snapshot = response.item
    syncSessionSnapshot(snapshot)

    const jobMode = String(snapshot?.summary?.job?.mode || '').trim().toLowerCase()
    const resolvedDryRun = jobMode === 'sample_preview'
      ? buildDryRunSummaryFromSessionSnapshot(snapshot, { preferredMode: 'sample_preview' })
      : buildPreimportScanFromSnapshot(snapshot)
    if (resolvedDryRun && !shouldWaitForDryRunExecutionSnapshot(snapshot)) {
      return resolvedDryRun
    }

    const currentStatus = String(snapshot?.status || '')
    const runLabel = 'Тестовый импорт'
    if (currentStatus === 'failed') {
      throw new Error(String(snapshot?.last_error || `${runLabel} завершился с ошибкой в фоновом worker.`))
    }
    if (currentStatus === 'cancelled') {
      return resolvedDryRun || buildCancelledDryRunSummary(snapshot)
    }

    if (!shouldWaitForDryRunExecutionSnapshot(snapshot)) {
      throw new Error(`${runLabel} завершился без итогового отчета.`)
    }

    await sleepAction(1500)
  }

  const response = await apiStore.getImportSession(sessionId)
  const snapshot = response.item
  syncSessionSnapshot(snapshot)
  const jobMode = String(snapshot?.summary?.job?.mode || '').trim().toLowerCase()
  const resolvedDryRun = jobMode === 'sample_preview'
    ? buildDryRunSummaryFromSessionSnapshot(snapshot, { preferredMode: 'sample_preview' })
    : buildPreimportScanFromSnapshot(snapshot)
  if (resolvedDryRun) {
    return resolvedDryRun
  }
  if (String(snapshot?.status || '') === 'cancelled') {
    return buildCancelledDryRunSummary(snapshot)
  }

  throw new Error(
    'Тестовый импорт запущен, но не удалось получить его текущее состояние.',
  )
}

async function waitForImportExecutionResult(sessionId: string) {
  const maxAttempts = 600

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const response = await apiStore.getImportSession(sessionId)
    const snapshot = response.item
    syncSessionSnapshot(snapshot)

    const resolvedImportRun = buildImportRunFromSnapshot(snapshot)
    if (resolvedImportRun && !shouldWaitForImportExecutionSnapshot(snapshot)) {
      return resolvedImportRun
    }

    const currentStatus = String(snapshot?.status || '')
    if (currentStatus === 'failed') {
      throw new Error(String(snapshot?.last_error || 'Импорт завершился с ошибкой в фоновом worker.'))
    }
    if (currentStatus === 'cancelled') {
      return resolvedImportRun || buildCancelledImportRunSummary(snapshot)
    }

    if (!shouldWaitForImportExecutionSnapshot(snapshot)) {
      throw new Error('Импорт завершился без итогового отчета.')
    }

    await sleepAction(1500)
  }

  const response = await apiStore.getImportSession(sessionId)
  const snapshot = response.item
  syncSessionSnapshot(snapshot)
  const resolvedImportRun = buildImportRunFromSnapshot(snapshot)
  if (resolvedImportRun) {
    return resolvedImportRun
  }
  if (String(snapshot?.status || '') === 'cancelled') {
    return buildCancelledImportRunSummary(snapshot)
  }

  throw new Error('Импорт запущен, но не удалось получить его текущее состояние.')
}

async function resolveDryRunExecutionResult(
  sessionId: string,
  responseItem: Record<string, any> | null | undefined,
  preferredMode: string = 'sample_preview',
) {
  if (responseItem && typeof responseItem === 'object' && Array.isArray(responseItem.results)) {
    syncSessionSnapshot({
      id: sessionId,
      status: responseItem.status,
      summary: {
        dry_run: responseItem,
        ...(preferredMode === 'sample_preview' ? { sample_preview: responseItem } : { preimport_scan: responseItem }),
      },
    })
    await loadHistory()
    return responseItem
  }

  syncSessionSnapshot(responseItem)
  const resolvedDryRun = await waitForDryRunExecutionResult(sessionId)
  await loadHistory()
  return resolvedDryRun
}

async function resolveImportExecutionResult(sessionId: string, responseItem: Record<string, any> | null | undefined) {
  if (responseItem && typeof responseItem === 'object' && Array.isArray(responseItem.results)) {
    syncSessionSnapshot({
      id: sessionId,
      status: responseItem.status,
      summary: { import_run: responseItem },
    })
    await loadHistory()
    return responseItem
  }

  syncSessionSnapshot(responseItem)
  const resolvedImportRun = await waitForImportExecutionResult(sessionId)
  await loadHistory()
  return resolvedImportRun
}

let _historyPollInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  if (props.initialImportMode) {
    selectImportMode(props.initialImportMode)
  }

  await loadHistory()

  _historyPollInterval = setInterval(() => {
    if (activeRunningSession.value && !session.value?.id) {
      void loadHistory()
    }
  }, 5000)
})

onUnmounted(() => {
  if (_historyPollInterval !== null) {
    clearInterval(_historyPollInterval)
    _historyPollInterval = null
  }
  stopBulkAttachPolling()
})

</script>

<template>
  <section class="relative w-full min-w-0">
    <!-- Fullscreen overlay while restoring a session from history -->
    <Transition name="history-restore-fade">
      <div
        v-if="restoringHistorySessionId"
        class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/90 backdrop-blur-sm"
      >
        <div class="h-12 w-12 animate-spin rounded-full border-4 border-[#dfe5eb] border-t-[#2e6bd9]" />
        <div class="mt-5 text-base font-semibold text-[#2f4254]">
          Загружаем импорт…
        </div>
        <div class="mt-1 text-sm text-[#8ea0b2]">
          Восстанавливаем сохранённые настройки
        </div>
      </div>
    </Transition>

    <div
      v-if="currentView === 'history'"
      class="overflow-hidden rounded-[30px] border border-[#dfe5eb] bg-white shadow-[0_24px_60px_rgba(23,54,110,0.10)]"
    >
      <div class="border-b border-[#e5ebf1] bg-[linear-gradient(180deg,#ffffff_0%,#f9fbfe_100%)] px-6 py-5 sm:px-8">
        <div class="flex items-center gap-5">
          <button
            type="button"
            class="flex shrink-0 items-center gap-1.5 rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium text-[#2e6bd9] transition hover:bg-[#ddeeff]"
            @click="currentView = 'wizard'"
          >
            ← Назад
          </button>
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
              Excel Migration
            </div>
            <h1 class="mt-1 text-[26px] font-semibold leading-[1.1] text-[#2f4254]">
              История импортов
            </h1>
          </div>
        </div>
      </div>

      <div class="min-h-[600px] overflow-y-auto px-6 py-6 sm:px-8 sm:py-8">
        <div
          v-if="historyLoadError"
          class="mb-4 rounded-[20px] border border-[#ffd9dd] bg-[#fff7f8] px-5 py-4"
        >
          <div class="text-sm font-semibold text-[#b33a48]">
            Не удалось загрузить историю
          </div>
          <div class="mt-1 text-sm text-[#8f5560]">
            {{ historyLoadError }}
          </div>
        </div>

        <div
          v-if="historyLoadError && historyRows.length === 0"
          class="flex min-h-[300px] items-center justify-center"
        >
          <div class="text-center">
            <div class="text-sm font-medium text-[#314256]">
              История пока недоступна
            </div>
            <div class="mt-1 text-sm text-[#8ea0b2]">
              Попробуйте обновить страницу или открыть раздел позже.
            </div>
          </div>
        </div>

        <div
          v-else-if="historyRows.length === 0"
          class="flex min-h-[300px] items-center justify-center"
        >
          <div class="text-center">
            <div class="text-sm font-medium text-[#314256]">
              История импортов пуста
            </div>
            <div class="mt-1 text-sm text-[#8ea0b2]">
              Здесь появятся все запуски после первого импорта.
            </div>
          </div>
        </div>

        <div
          v-else
          class="space-y-3"
        >
          <div
            v-for="row in historyRows"
            :key="row.key"
            class="overflow-hidden rounded-[20px] border bg-white"
            :class="{
              'border-[#b8e6cc]': row.resultTone === 'success',
              'border-[#f5c2c7]': row.resultTone === 'danger',
              'border-[#f5dfa0]': row.resultTone === 'warning',
              'border-[#bbd6f8]': row.resultTone === 'info',
              'border-[#e3e9f0]': row.resultTone === 'neutral',
            }"
          >
            <!-- color accent strip -->
            <div
              class="h-1 w-full"
              :class="{
                'bg-[#3dba6f]': row.resultTone === 'success',
                'bg-[#d94f5c]': row.resultTone === 'danger',
                'bg-[#e8a32a]': row.resultTone === 'warning',
                'bg-[#2e6bd9]': row.resultTone === 'info',
                'bg-[#c8d5e2]': row.resultTone === 'neutral',
              }"
            />

            <div class="px-5 py-4">
              <!-- Header row: filename + status badge -->
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate text-[13px] font-semibold text-[#2f4254]">{{ row.fileName }}</div>
                </div>
                <span
                  class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
                  :class="{
                    'bg-[#eefaf3] text-[#2b7a4b]': row.resultTone === 'success',
                    'bg-[#fff1f1] text-[#c24b53]': row.resultTone === 'danger',
                    'bg-[#fff8ec] text-[#a0610a]': row.resultTone === 'warning',
                    'bg-[#eef6ff] text-[#2e6bd9]': row.resultTone === 'info',
                    'bg-[#f2f5f9] text-[#6e8193]': row.resultTone === 'neutral',
                  }"
                >{{ row.resultLabel }}</span>
              </div>

              <!-- Meta row: entity + format + date -->
              <div class="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-[#8ea0b2]">
                <span>{{ row.entityType }}</span>
                <span class="text-[#c8d5e2]">·</span>
                <span class="rounded-[6px] bg-[#f2f5f8] px-1.5 py-0.5 text-[11px] font-medium text-[#7a8fa0]">{{ row.sourceFormatLabel }}</span>
                <span class="text-[#c8d5e2]">·</span>
                <span>{{ row.updatedAtLabel }}</span>
              </div>

              <!-- Stats + action -->
              <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div v-if="row.counters.hasData" class="flex flex-wrap items-center gap-2">
                  <span v-if="row.counters.total" class="rounded-[8px] border border-[#e5ebf2] bg-[#f7f9fb] px-2 py-1 text-[11px] font-medium text-[#6e8193]">
                    Всего {{ row.counters.total }}
                  </span>
                  <span v-if="row.counters.created" class="rounded-[8px] border border-[#c3e8d0] bg-[#f0faf4] px-2 py-1 text-[11px] font-semibold text-[#2b7a4b]">
                    +{{ row.counters.created }} созд.
                  </span>
                  <span v-if="row.counters.updated" class="rounded-[8px] border border-[#bbd6f8] bg-[#eef6ff] px-2 py-1 text-[11px] font-semibold text-[#2e6bd9]">
                    {{ row.counters.updated }} обн.
                  </span>
                  <span v-if="row.counters.skipped" class="rounded-[8px] border border-[#e5ebf2] bg-[#f2f5f9] px-2 py-1 text-[11px] font-medium text-[#8ea0b2]">
                    {{ row.counters.skipped }} проп.
                  </span>
                  <span v-if="row.counters.failed" class="rounded-[8px] border border-[#f5c2c7] bg-[#fff1f1] px-2 py-1 text-[11px] font-semibold text-[#c24b53]">
                    {{ row.counters.failed }} ош.
                  </span>
                </div>
                <div v-else class="text-[12px] text-[#b0bec8]">Нет данных</div>

                <B24Button
                  :label="row.actionLabel"
                  color="air-primary"
                  size="md"
                  :loading="restoringHistorySessionId === row.key"
                  :disabled="!importerPermissionState.canViewSessions || Boolean(restoringHistorySessionId)"
                  @click="resumeHistorySession(row.key)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-else
      class="grid min-h-[860px] grid-cols-1 overflow-hidden rounded-[30px] border border-[#dfe5eb] bg-white shadow-[0_24px_60px_rgba(23,54,110,0.10)] xl:grid-cols-[280px_minmax(0,1fr)]"
    >
      <aside class="flex min-w-0 flex-col border-b border-[#e5ebf1] bg-[linear-gradient(180deg,#f7fbff_0%,#f3f7fb_100%)] xl:border-b-0 xl:border-r">
        <div class="flex-1 space-y-6 px-5 py-6">
          <!-- Logo -->
          <div class="flex items-center gap-2.5 px-1">
            <img src="/logo.png" alt="Excel Migration" class="h-8 w-auto object-contain" />
            <span class="text-[14px] font-semibold tracking-tight text-[#2f4254]">Excel Migration</span>
          </div>

          <div class="space-y-4">
            <div class="px-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
              Этапы
            </div>

            <div class="space-y-3">
              <button
                v-for="(step, index) in visibleSteps"
                :key="step.id"
                type="button"
                class="relative flex w-full gap-3 rounded-[18px] px-3 py-3 text-left transition duration-150"
                :style="step.state === 'current' ? { background: domainAccent.bg } : {}"
                :class="{
                  'shadow-[0_10px_26px_rgba(30,80,150,0.08)]': step.state === 'current',
                  'bg-[#eff6ff]': step.state === 'done',
                  'bg-transparent hover:bg-white hover:shadow-[0_10px_26px_rgba(30,80,150,0.08)]': step.state === 'upcoming' && step.enabled,
                  'opacity-60': !step.enabled,
                }"
                :disabled="!step.enabled"
                @click="goToSidebarStep(step.id)"
              >
                <div
                  v-if="index < visibleSteps.length - 1"
                  class="absolute left-[32px] top-[44px] h-[34px] w-[2px] -translate-x-1/2 rounded-full"
                  :class="step.state === 'done' ? 'bg-[#8fd0a1]' : 'bg-[#dbe4ed]'"
                />

                <div
                  class="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
                  :style="step.state === 'current' ? { background: domainAccent.ink, color: '#FFFFFF' } : {}"
                  :class="{
                    'bg-[#dff3e5] text-[#2e8b57]': step.state === 'done',
                    'bg-white text-[#93a1af] border border-[#dde5ee]': step.state === 'upcoming',
                  }"
                >
                  {{ step.id }}
                </div>

                <div class="min-w-0 pt-1">
                  <div
                    class="text-sm font-semibold"
                    :style="step.state === 'current' ? { color: domainAccent.ink } : {}"
                    :class="{
                      'text-[#2f4254]': step.state === 'done',
                      'text-[#8da0b1]': step.state === 'upcoming',
                    }"
                  >
                    {{ step.title }}
                  </div>
                  <div class="mt-1 text-xs text-[#8da0b1]">
                    {{ step.description }}
                  </div>
                </div>
              </button>
            </div>
          </div>

          <div class="rounded-[20px] border border-[#dfe6ee] bg-white px-4 py-4">
            <div class="space-y-3">
              <div
                v-for="fact in sidebarFacts"
                :key="fact.label"
                class="flex items-center justify-between gap-3 text-sm"
              >
                <span class="text-[#7d8d9d]">{{ fact.label }}</span>
                <span class="truncate text-right font-medium text-[#314256]">{{ fact.value }}</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <div class="flex min-w-0 flex-col bg-white">
        <div
          v-if="!(currentStep === 1 && importMode)"
          class="px-6 pt-6 sm:px-8"
        >
          <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div class="min-w-0 flex-1">
              <div class="mb-3 flex flex-wrap items-center gap-2">
                <span class="rounded-full bg-[#EEF2FF] px-2.5 py-0.5 text-[11px] font-medium text-[#3B47D6]">
                  {{ currentStepMeta.eyebrow }}
                </span>
                <span class="text-[11px] text-[#8B8FA0]">·</span>
                <span class="inline-flex items-center gap-1.5 text-[11px] text-[#5A5E6E]">
                  <span class="h-1.5 w-1.5 rounded-full" :class="currentStepHeaderStatusMeta.dotClass" />
                  {{ currentStepHeaderStatusMeta.label }}
                </span>
              </div>
              <h1 class="text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#0F1115]">
                {{ currentStepMeta.title }}
              </h1>
              <p class="mt-2 max-w-[760px] text-[14px] text-[#5A5E6E]">
                {{ currentStepMeta.description }}
              </p>
              <div
                v-if="headerNotice"
                class="mt-3 flex flex-wrap items-center gap-3 text-sm"
              >
                <span
                  class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                  :class="headerNotice.tone === 'error'
                    ? 'bg-[#fff1f1] text-[#c24b53]'
                    : 'bg-[#eefaf3] text-[#2b7a4b]'"
                >
                  {{ headerNotice.label }}
                </span>
                <span class="max-w-full whitespace-pre-wrap break-words text-[#667b8f]">
                  {{ getTextBlockDisplayValue(makeCollapsibleKey('header-notice', headerNotice.label), headerNotice.message) }}
                </span>
                <button
                  v-if="isTextCollapsible(headerNotice.message)"
                  type="button"
                  class="text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                  @click="toggleTextBlock(makeCollapsibleKey('header-notice', headerNotice.label))"
                >
                  {{ isTextBlockExpanded(makeCollapsibleKey('header-notice', headerNotice.label)) ? 'Скрыть' : 'Показать полностью' }}
                </button>
              </div>
            </div>

            <div class="flex shrink-0 flex-col gap-3 xl:items-end">
              <B24Button
                label="История"
                color="air-primary"
                size="lg"
                :disabled="!importerPermissionState.canViewSessions"
                @click="currentView = 'history'"
              />
              <div class="flex flex-wrap gap-2 xl:justify-end">
                <div
                  v-if="importMode"
                  class="rounded-full border border-[#e5ebf2] bg-[#f7f9fb] px-3 py-1.5 text-sm text-[#5e7184]"
                >
                  {{ importModeMeta.label }}
                </div>
                <div class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium text-[#2e6bd9]">
                  {{ currentScenarioSummary.selectedLabel }}
                </div>
                <div
                  v-if="sourceFormat"
                  class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium uppercase text-[#2e6bd9]"
                >
                  {{ sourceFormat }}
                </div>
                <div
                  v-if="fileName"
                  class="rounded-full border border-[#dfe7f2] bg-[#f7f9fb] px-3 py-1.5 text-sm text-[#5e7184]"
                >
                  {{ fileName }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="min-w-0 flex-1 space-y-6 overflow-y-auto px-6 py-6 sm:px-8 sm:py-8">
          <div
            v-if="hasNoImporterAccess"
            class="rounded-[24px] border border-[#ffe0a6] bg-[#fff8eb] px-5 py-5 text-[#8a5b12] shadow-[0_8px_24px_rgba(175,124,18,0.08)]"
          >
            <div class="text-sm font-semibold uppercase tracking-[0.12em] text-[#b07a18]">
              Права доступа
            </div>
            <div class="mt-2 text-lg font-semibold text-[#6d4710]">
              Нет назначенной роли для работы с импортом.
            </div>
            <div class="mt-2 max-w-[760px] text-sm leading-relaxed text-[#8a5b12]">
              Обратитесь к администратору портала, чтобы получить роль оператора или доступ на просмотр истории и отчетов.
            </div>
          </div>

          <div v-if="currentStep === 1">
            <Transition name="step1-fade" mode="out-in">
            <!-- No import mode: simple prompt -->
            <div v-if="!importMode" key="no-mode" class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
              <div class="rounded-[18px] border border-[#dce7f7] bg-[#f4f9ff] px-4 py-3 text-sm text-[#5c7592]">
                Вернитесь на главный экран и выберите режим импорта.
              </div>
            </div>

            <!-- Family selection: flat design (no panel wrapper) -->
            <div v-else-if="!selectedFamily" key="select-family">
              <!-- Page header row -->
              <div class="mb-6 flex items-start justify-between">
                <div>
                  <div class="mb-3 flex items-center gap-2">
                    <span class="rounded-full bg-[#EEF2FF] px-2.5 py-0.5 text-[11px] font-medium text-[#3B47D6]">
                      Шаг 1 · Настройки
                    </span>
                    <span class="text-[11px] text-[#8B8FA0]">·</span>
                    <span class="inline-flex items-center gap-1.5 text-[11px] text-[#5A5E6E]">
                      <span class="h-1.5 w-1.5 rounded-full bg-[#E8B53A]" />
                      Ожидает запуска
                    </span>
                  </div>
                  <h1 class="text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#0F1115]">
                    Выберите тип импорта
                  </h1>
                  <p class="mt-2 max-w-[520px] text-[14px] text-[#5A5E6E]">
                    От выбора зависят следующие шаги — формат файла, сопоставление полей и правила дублей.
                  </p>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    class="h-10 rounded-xl border border-[#d7e7ff] bg-[#f4f9ff] px-4 text-[13px] font-medium text-[#2e6bd9] transition-colors hover:bg-[#ddeeff]"
                    @click="emit('back-to-landing')"
                  >
                    Выбрать режим
                  </button>
                  <button
                    type="button"
                    class="h-10 rounded-xl bg-[#2e6bd9] px-4 text-[13px] font-medium text-white transition-colors hover:bg-[#2560c5]"
                    :disabled="!importerPermissionState.canViewSessions"
                    @click="currentView = 'history'"
                  >
                    История
                  </button>
                </div>
              </div>

              <!-- Active session warning -->
              <div v-if="isBlockedByActiveSession" class="mb-4 flex items-start gap-3 rounded-[16px] border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
                <span class="mt-0.5 shrink-0 text-base">⚠️</span>
                <div>
                  <span class="font-semibold">Идёт импорт:</span> «{{ activeRunningSession?.original_filename || 'без имени' }}». Дождитесь его завершения или
                  <button
                    type="button"
                    class="underline hover:no-underline"
                    @click="resumeHistorySession(String(activeRunningSession?.id || activeRunningSession?.session_id || ''))"
                  >перейдите к нему</button>, чтобы отменить. Новый импорт будет доступен после завершения или отмены.
                </div>
              </div>

              <!-- Category cards -->
              <div class="grid gap-4 sm:grid-cols-3">
                  <!-- CRM -->
                  <button
                    type="button"
                    class="relative overflow-hidden rounded-[16px] text-left transition-all duration-200"
                    style="border: 1.5px solid #ECEEF3; background: #FFFFFF;"
                    :disabled="!importerPermissionState.canCreateSessions || isBlockedByActiveSession"
                    @mouseenter="$event.currentTarget.style.cssText = 'border: 1.5px solid #3B47D6; background: #EEF2FF; border-radius: 16px; text-align: left; transition: all 0.2s; box-shadow: 0 8px 24px -12px #3B47D640;'"
                    @mouseleave="$event.currentTarget.style.cssText = 'border: 1.5px solid #ECEEF3; background: #FFFFFF; border-radius: 16px; text-align: left; transition: all 0.2s;'"
                    @click="selectFamily('crm')"
                  >
                    <div class="flex h-[100px] items-center justify-center bg-[#EEF2FF]">
                      <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                        <circle cx="20" cy="22" r="8" stroke="#3B47D6" stroke-width="2"/>
                        <circle cx="44" cy="22" r="8" stroke="#3B47D6" stroke-width="2" opacity=".7"/>
                        <path d="M8 50c2-7 10-11 16-11" stroke="#3B47D6" stroke-width="2" stroke-linecap="round"/>
                        <path d="M40 39c6 0 14 4 16 11" stroke="#3B47D6" stroke-width="2" stroke-linecap="round" opacity=".7"/>
                        <path d="M28 32l8 8M36 32l-8 8" stroke="#3B47D6" stroke-width="2" stroke-linecap="round"/>
                      </svg>
                    </div>
                    <div class="p-4">
                      <div class="text-[15px] font-semibold text-[#0F1115]">CRM-сущности</div>
                      <p class="mt-1 text-[12.5px] leading-relaxed text-[#5A5E6E]">Лиды, контакты, компании, сделки и связанный импорт.</p>
                      <div class="mt-3 flex flex-wrap gap-1.5">
                        <span class="rounded-full bg-[#EEF2FF] px-2 py-0.5 text-[11px] font-medium text-[#3B47D6]">Лиды</span>
                        <span class="rounded-full bg-[#EEF2FF] px-2 py-0.5 text-[11px] font-medium text-[#3B47D6]">Контакты</span>
                        <span class="rounded-full bg-[#EEF2FF] px-2 py-0.5 text-[11px] font-medium text-[#3B47D6]">Компании</span>
                        <span class="rounded-full bg-[#EEF2FF] px-2 py-0.5 text-[11px] font-medium text-[#3B47D6]">Сделки</span>
                      </div>
                    </div>
                  </button>

                  <!-- Задачи -->
                  <button
                    type="button"
                    class="relative overflow-hidden rounded-[16px] text-left transition-all duration-200"
                    style="border: 1.5px solid #ECEEF3; background: #FFFFFF;"
                    :disabled="!importerPermissionState.canCreateSessions || isBlockedByActiveSession"
                    @mouseenter="$event.currentTarget.style.cssText = 'border: 1.5px solid #D8632A; background: #FFF1E8; border-radius: 16px; text-align: left; transition: all 0.2s; box-shadow: 0 8px 24px -12px #D8632A40;'"
                    @mouseleave="$event.currentTarget.style.cssText = 'border: 1.5px solid #ECEEF3; background: #FFFFFF; border-radius: 16px; text-align: left; transition: all 0.2s;'"
                    @click="selectFamily('task')"
                  >
                    <div class="flex h-[100px] items-center justify-center bg-[#FFF1E8]">
                      <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                        <rect x="14" y="14" width="36" height="36" rx="4" stroke="#D8632A" stroke-width="2"/>
                        <path d="M22 26l4 4 8-8" stroke="#D8632A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M38 28h6" stroke="#D8632A" stroke-width="2" stroke-linecap="round"/>
                        <path d="M22 40h6" stroke="#D8632A" stroke-width="2" stroke-linecap="round" opacity=".5"/>
                        <path d="M32 40h12" stroke="#D8632A" stroke-width="2" stroke-linecap="round" opacity=".5"/>
                      </svg>
                    </div>
                    <div class="p-4">
                      <div class="text-[15px] font-semibold text-[#0F1115]">Задачи</div>
                      <p class="mt-1 text-[12.5px] leading-relaxed text-[#5A5E6E]">Задачи, подзадачи, комментарии, чек-листы и вложения.</p>
                      <div class="mt-3 flex flex-wrap gap-1.5">
                        <span class="rounded-full bg-[#FFF1E8] px-2 py-0.5 text-[11px] font-medium text-[#D8632A]">Задачи</span>
                        <span class="rounded-full bg-[#FFF1E8] px-2 py-0.5 text-[11px] font-medium text-[#D8632A]">Чек-листы</span>
                        <span class="rounded-full bg-[#FFF1E8] px-2 py-0.5 text-[11px] font-medium text-[#D8632A]">Комментарии</span>
                      </div>
                    </div>
                  </button>

                  <!-- HR -->
                  <button
                    type="button"
                    class="relative overflow-hidden rounded-[16px] text-left transition-all duration-200"
                    style="border: 1.5px solid #ECEEF3; background: #FFFFFF;"
                    :disabled="!importerPermissionState.canCreateSessions || isBlockedByActiveSession"
                    @mouseenter="$event.currentTarget.style.cssText = 'border: 1.5px solid #1E8A52; background: #E8F6EE; border-radius: 16px; text-align: left; transition: all 0.2s; box-shadow: 0 8px 24px -12px #1E8A5240;'"
                    @mouseleave="$event.currentTarget.style.cssText = 'border: 1.5px solid #ECEEF3; background: #FFFFFF; border-radius: 16px; text-align: left; transition: all 0.2s;'"
                    @click="selectFamily('hr')"
                  >
                    <div class="flex h-[100px] items-center justify-center bg-[#E8F6EE]">
                      <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                        <rect x="10" y="10" width="14" height="14" rx="2" stroke="#1E8A52" stroke-width="2"/>
                        <rect x="40" y="10" width="14" height="14" rx="2" stroke="#1E8A52" stroke-width="2" opacity=".6"/>
                        <rect x="25" y="40" width="14" height="14" rx="2" stroke="#1E8A52" stroke-width="2"/>
                        <path d="M17 24v8h15M47 24v8H32M32 32v8" stroke="#1E8A52" stroke-width="2" stroke-linecap="round"/>
                      </svg>
                    </div>
                    <div class="p-4">
                      <div class="text-[15px] font-semibold text-[#0F1115]">Пользователи и отделы</div>
                      <p class="mt-1 text-[12.5px] leading-relaxed text-[#5A5E6E]">Сотрудники портала и структура компании.</p>
                      <div class="mt-3 flex flex-wrap gap-1.5">
                        <span class="rounded-full bg-[#E8F6EE] px-2 py-0.5 text-[11px] font-medium text-[#1E8A52]">Сотрудники</span>
                        <span class="rounded-full bg-[#E8F6EE] px-2 py-0.5 text-[11px] font-medium text-[#1E8A52]">Отделы</span>
                      </div>
                    </div>
                  </button>
              </div>

              <!-- Футер -->
              <div class="mt-8 flex items-center justify-between">
                <span class="text-[12.5px] text-[#8B8FA0]">
                  Тип импорта можно сменить позже — состояние сохранится.
                </span>
                <button
                  type="button"
                  class="h-11 rounded-xl border border-[#d7e7ff] bg-[#f4f9ff] px-5 text-[13px] font-medium text-[#2e6bd9] transition-colors hover:bg-[#ddeeff]"
                  @click="emit('back-to-landing')"
                >
                  ← Назад
                </button>
              </div>
            </div>

            <!-- Выбран тип: подэкраны сущностей -->
            <div v-else :key="selectedFamily">
              <div class="mb-6 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div class="min-w-0 flex-1">
                  <div class="mb-3 flex flex-wrap items-center gap-2">
                    <span class="rounded-full bg-[#EEF2FF] px-2.5 py-0.5 text-[11px] font-medium text-[#3B47D6]">
                      {{ selectedFamilyHeaderMeta.eyebrow }}
                    </span>
                    <span class="text-[11px] text-[#8B8FA0]">·</span>
                    <span class="inline-flex items-center gap-1.5 text-[11px] text-[#5A5E6E]">
                      <span class="h-1.5 w-1.5 rounded-full" :class="selectedFamilyHeaderStatusMeta.dotClass" />
                      {{ selectedFamilyHeaderStatusMeta.label }}
                    </span>
                  </div>
                  <h1 class="text-[28px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#0F1115]">
                    {{ selectedFamilyHeaderMeta.title }}
                  </h1>
                  <p class="mt-2 max-w-[760px] text-[14px] text-[#5A5E6E]">
                    {{ selectedFamilyHeaderMeta.description }}
                  </p>
                </div>
                <div class="flex shrink-0 flex-col gap-3 xl:items-end">
                  <div class="flex flex-wrap gap-2 xl:justify-end">
                    <div
                      v-if="importMode"
                      class="rounded-full border border-[#e5ebf2] bg-[#f7f9fb] px-3 py-1.5 text-sm text-[#5e7184]"
                    >
                      {{ importModeMeta.label }}
                    </div>
                    <div class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium text-[#2e6bd9]">
                      {{ currentScenarioSummary.selectedLabel }}
                    </div>
                    <div
                      v-if="sourceFormat"
                      class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium uppercase text-[#2e6bd9]"
                    >
                      {{ sourceFormat }}
                    </div>
                    <div
                      v-if="fileName"
                      class="rounded-full border border-[#dfe7f2] bg-[#f7f9fb] px-3 py-1.5 text-sm text-[#5e7184]"
                    >
                      {{ fileName }}
                    </div>
                  </div>
                  <div class="flex flex-wrap items-center gap-2 xl:justify-end">
                    <button
                      type="button"
                      class="h-10 rounded-xl border border-[#d7e7ff] bg-[#f4f9ff] px-4 text-[13px] font-medium text-[#2e6bd9] transition-colors hover:bg-[#ddeeff]"
                      :disabled="Boolean(busyAction) || (isBulkAttachFlow && isBulkAttachExecutionLocked)"
                      @click="handleStepOneBack()"
                    >
                      ← Назад
                    </button>
                    <B24Button
                      v-if="!isBulkAttachFlow"
                      label="Загрузить файл"
                      color="air-primary"
                      size="lg"
                      :loading="busyAction === 'start'"
                      :disabled="!canStart"
                      @click="startImporterSetup"
                    />
                    <B24Button
                      v-else-if="!bulkFilterPreview"
                      :label="bulkPreviewActionLabel"
                      color="air-primary"
                      size="lg"
                      :loading="loadingBulkFilterPreview"
                      :disabled="!selectedBulkAttachEntityType || (!isTaskBulkAttachFlow && !selectedBulkFileField) || Boolean(busyAction) || loadingBulkFileFields || loadingBulkFilterPreview"
                      @click="runBulkFilterPreview"
                    />
                    <B24Button
                      v-else
                      :label="bulkAttachActionLabel"
                      color="air-primary"
                      size="lg"
                      :loading="busyAction === 'bulk-attach-run'"
                      :disabled="isBulkAttachActionDisabled"
                      @click="startBulkAttachSetup"
                    />
                  </div>
                </div>
              </div>

                <!-- Ошибка / успех на шаге 1 -->
                <div v-if="errorMessage" class="mb-4 flex items-start gap-3 rounded-[16px] border border-[#fecaca] bg-[#fff1f1] px-4 py-3 text-sm text-[#c24b53]">
                  <svg class="mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.4"/>
                    <path d="M8 5v3.5M8 10.5v.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                  </svg>
                  <span>{{ errorMessage }}</span>
                </div>
                <div v-else-if="successMessage" class="mb-4 flex items-start gap-3 rounded-[16px] border border-[#86efac] bg-[#f0fdf4] px-4 py-3 text-sm text-[#166534]">
                  <svg class="mt-0.5 shrink-0" width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.4"/>
                    <path d="M5 8l2 2 4-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span>{{ successMessage }}</span>
                </div>

                <!-- CRM подэкран -->
                <div v-if="selectedFamily === 'crm'">
                  <!-- Flavor selector -->
                  <div class="grid grid-cols-3 gap-3 mb-5">
                    <button
                      v-for="f in [
                        { key: 'direct', title: 'Прямой импорт',          blurb: 'В стандартные разделы CRM — сделки, контакты, компании.' },
                        { key: 'linked', title: 'Связанный импорт',        blurb: 'Одна строка создаёт несколько связанных сущностей.' },
                        { key: 'bulk',   title: 'Массовый импорт файлов',  blurb: 'Прикрепить файлы к полям существующих CRM-записей.' },
                      ]"
                      :key="f.key"
                      type="button"
                      class="text-left rounded-2xl p-4 transition-all"
                      :class="isBulkAttachScenarioLocked ? 'cursor-not-allowed' : ''"
                      :style="isBulkAttachScenarioLocked
                        ? { background: crmFlavor === f.key ? '#EEF2F6' : '#F7F9FC', border: '1.5px solid #DCE4EE', boxShadow: 'none', color: '#8EA0B2' }
                        : (crmFlavor === f.key
                          ? { background: domainAccent.bg, border: `1.5px solid ${domainAccent.ink}`, boxShadow: `0 4px 14px -8px ${domainAccent.ink}40` }
                          : { background: '#FFFFFF', border: '1.5px solid #ECEEF3' })"
                      :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction) || isBulkAttachScenarioLocked"
                      @click="selectCrmFlavor(f.key as 'direct' | 'linked' | 'bulk')"
                    >
                      <div class="flex items-center gap-2.5 mb-1.5">
                        <span
                          class="w-8 h-8 rounded-lg grid place-items-center shrink-0"
                          :style="isBulkAttachScenarioLocked
                            ? { background: '#FFFFFF', color: '#8EA0B2' }
                            : (crmFlavor === f.key
                              ? { background: '#FFFFFF', color: domainAccent.ink }
                              : { background: domainAccent.bg, color: domainAccent.ink })"
                        >
                          <svg v-if="f.key === 'direct'" width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <path d="M3 9h12M11 5l4 4-4 4" :stroke="domainAccent.ink" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                          </svg>
                          <svg v-else-if="f.key === 'linked'" width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <circle cx="5" cy="5" r="2.4" :stroke="domainAccent.ink" stroke-width="1.6" />
                            <circle cx="13" cy="13" r="2.4" :stroke="domainAccent.ink" stroke-width="1.6" />
                            <path d="M6.5 6.5l5 5" :stroke="domainAccent.ink" stroke-width="1.6" stroke-linecap="round" />
                          </svg>
                          <svg v-else width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <path d="M3 13V5a2 2 0 012-2h4l2 2h4a1 1 0 011 1v7a2 2 0 01-2 2H5a2 2 0 01-2-2z"
                              :stroke="domainAccent.ink" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                          </svg>
                        </span>
                        <span
                          class="text-[14px] font-semibold tracking-tight"
                          :style="{ color: isBulkAttachScenarioLocked ? '#7F8C99' : (crmFlavor === f.key ? domainAccent.ink : '#0F1115') }"
                        >
                          {{ f.title }}
                        </span>
                        <span
                          v-if="crmFlavor === f.key && !isBulkAttachScenarioLocked"
                          class="ml-auto w-5 h-5 rounded-full grid place-items-center shrink-0"
                          :style="{ background: domainAccent.ink }"
                        >
                          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                            <path d="M2.5 5.5l2 2 4-4" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                          </svg>
                        </span>
                      </div>
                      <p class="text-[12px] leading-snug text-[#5A5E6E]">{{ f.blurb }}</p>
                    </button>
                  </div>

                  <!-- Two-column body -->
                  <div
                    class="grid gap-5"
                    :style="{ gridTemplateColumns: '1fr 320px' }"
                  >
                    <!-- Left: form panel -->
                    <div class="rounded-2xl border border-[#ECEEF3] bg-white p-6 flex flex-col">
                      <div class="flex items-center justify-between mb-1">
                        <h3 class="text-[15px] font-semibold tracking-tight text-[#0F1115]">
                          {{ crmFlavor === 'direct' ? 'Прямой импорт' : crmFlavor === 'linked' ? 'Связанный импорт' : 'Массовый импорт файлов' }}
                        </h3>
                        <span class="text-[11px] text-[#5A5E6E]">Поля можно изменить на шаге «Соответствие»</span>
                      </div>
                      <p class="text-[12.5px] mb-5 text-[#5A5E6E]">
                        {{ crmFlavor === 'direct'
                          ? 'В стандартные разделы CRM — сделки, контакты, компании.'
                          : crmFlavor === 'linked'
                            ? 'Одна строка создаёт несколько связанных сущностей.'
                            : 'Прикрепить файлы к полям существующих CRM-записей.' }}
                      </p>

                      <!-- Direct fields -->
                      <div v-if="crmFlavor === 'direct'" class="space-y-4 max-w-[380px]">
                        <div>
                          <div class="text-[12px] mb-1.5 font-medium text-[#3A3D47]">CRM-сущность</div>
                          <B24Select
                            :model-value="selectedCrmEntityType"
                            :items="crmScenarioItems"
                            placeholder="Например, Сделки"
                            size="lg"
                            class="w-full"
                            :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                            @update:model-value="updateScenarioEntityType('crm', String($event || ''))"
                          />
                        </div>
                        <div v-if="selectedCrmEntityType === 'smart_process'">
                          <div class="text-[12px] mb-1.5 font-medium text-[#3A3D47]">Смарт-процесс</div>
                          <B24Select
                            :model-value="selectedSmartProcessId"
                            :items="smartProcessOptions"
                            placeholder="Например, Согласования"
                            size="lg"
                            class="w-full"
                            :disabled="loadingSmartProcesses || !importerPermissionState.canCreateSessions || Boolean(busyAction)"
                            @update:model-value="selectedSmartProcessId = String($event || '')"
                          />
                          <div class="mt-2 text-xs text-[#7f92a7]">
                            {{ loadingSmartProcesses
                              ? 'Загружаем список смарт-процессов...'
                              : smartProcessOptions.length
                                ? 'Выберите конкретный смарт-процесс.'
                                : 'Смарт-процессы не найдены.' }}
                          </div>
                        </div>
                      </div>

                      <!-- Linked fields -->
                      <div v-else-if="crmFlavor === 'linked'" class="grid grid-cols-2 gap-4">
                        <div>
                          <div class="text-[12px] mb-1.5 font-medium text-[#3A3D47]">Основная сущность</div>
                          <B24Select
                            :model-value="selectedLinkedPrimaryEntityType"
                            :items="linkedPrimaryEntityItems"
                            placeholder="Выберите основную сущность"
                            size="lg"
                            class="w-full"
                            :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                            @update:model-value="updateLinkedPrimaryEntityType(String($event || ''))"
                          />
                        </div>
                        <div>
                          <div class="text-[12px] mb-1.5 font-medium text-[#3A3D47]">Связанная сущность</div>
                          <B24Select
                            :model-value="selectedLinkedSecondaryEntityType"
                            :items="linkedSecondaryEntityItems"
                            :placeholder="selectedLinkedPrimaryEntityType
                              ? (linkedSecondaryEntityItems.length ? 'Выберите связанную сущность' : 'Для этой сущности нет связанных вариантов')
                              : 'Сначала выберите основную сущность'"
                            size="lg"
                            class="w-full"
                            :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                            @update:model-value="updateLinkedSecondaryEntityType(String($event || ''))"
                          />
                        </div>
                      </div>

                      <!-- Bulk fields -->
                      <div v-else class="space-y-5">
                        <div v-if="!bulkFilterPreview" class="space-y-5">
                          <div class="grid grid-cols-2 gap-4">
                            <div>
                              <div class="text-[12px] mb-1.5 font-medium text-[#3A3D47]">CRM-сущность</div>
                              <B24Select
                                :model-value="selectedFileAttachEntityType"
                                :items="fileAttachCrmEntityItems"
                                placeholder="Например, Сделки"
                                size="lg"
                                class="w-full"
                                :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                                @update:model-value="selectBulkFileAttachEntityType(String($event || ''))"
                              />
                            </div>
                            <div>
                              <div class="text-[12px] mb-1.5 font-medium text-[#3A3D47]">Поле для файлов</div>
                              <div
                                v-if="loadingBulkFileFields"
                                class="flex h-11 w-full items-center rounded-[14px] border border-[#D8E3EF] bg-white px-4 text-[14px] font-medium text-[#3A3D47]"
                              >
                                Загрузка...
                              </div>
                              <B24Select
                                v-else
                                :model-value="selectedBulkFileField"
                                :items="bulkFileFields"
                                :placeholder="selectedFileAttachEntityType
                                  ? (bulkFileFields.length ? 'Выберите поле' : 'У выбранной сущности нет полей типа «Файл»')
                                  : 'Сначала выберите CRM-сущность'"
                                size="lg"
                                class="w-full"
                                :disabled="Boolean(busyAction)"
                                @update:model-value="selectedBulkFileField = String($event || '')"
                              />
                            </div>
                          </div>

                          <div class="space-y-4">
                            <div class="text-[12px] font-medium text-[#5A5E6E]">Фильтр отбора:</div>

                            <div
                              v-for="condition in bulkFilterConditions"
                              :key="condition.fieldId"
                              class="rounded-[16px] border border-[#e5ebf2] bg-white px-4 py-4"
                            >
                              <div class="flex items-center justify-between gap-3">
                                <div class="text-sm font-semibold text-[#314256]">
                                  {{ resolveBulkFilterField(condition.fieldId)?.title || condition.fieldId }}
                                </div>
                                <button
                                  type="button"
                                  class="rounded-full border border-[#d9e5f1] bg-white px-3 py-1 text-xs font-medium text-[#6d8194] transition hover:border-[#f0b7b7] hover:text-[#c24b53]"
                                  @click="removeBulkFilterField(condition.fieldId)"
                                >
                                  Удалить
                                </button>
                              </div>

                              <B24SelectMenu
                                v-if="getBulkFilterValueOptions(condition.fieldId).length"
                                :model-value="condition.value"
                                class="mt-3 w-full"
                                placeholder="Выберите значение Bitrix24"
                                :items="getBulkFilterValueOptions(condition.fieldId)"
                                value-key="value"
                                :filter-fields="['label']"
                                :search-input="{ placeholder: 'Поиск значения Bitrix24' }"
                                @update:model-value="condition.value = String($event || '')"
                              />
                              <input
                                v-else
                                v-model="condition.value"
                                type="text"
                                :placeholder="`Введите значение для поля «${resolveBulkFilterField(condition.fieldId)?.title || condition.fieldId}»`"
                                class="mt-3 w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
                              />
                            </div>

                            <div v-if="isAddingBulkFilterField" class="rounded-[16px] border border-[#dce7f7] bg-[#f7fbff] px-4 py-4">
                              <B24SelectMenu
                                :model-value="pendingBulkFilterFieldId"
                                class="w-full"
                                placeholder="Выберите поле Bitrix24"
                                :items="bulkFilterFieldOptions"
                                value-key="value"
                                :filter-fields="['label']"
                                :search-input="{ placeholder: 'Поиск поля Bitrix24' }"
                                @update:model-value="addBulkFilterField(String($event || ''))"
                              />
                            </div>

                            <button
                              type="button"
                              class="inline-flex items-center rounded-full border border-dashed border-[#c6d7ee] bg-transparent px-4 py-2 text-sm font-medium text-[#53749b] transition hover:border-[#2e6bd9] hover:text-[#2e6bd9]"
                              :disabled="!selectedFileAttachEntityType"
                              @click="openAddBulkFilterField"
                            >
                              Добавить поле
                            </button>
                          </div>
                        </div>

                        <div v-else class="space-y-4">
                          <div class="rounded-2xl border border-[#ECEEF3] bg-white p-5">
                            <div class="flex items-center gap-3">
                              <div class="w-10 h-10 rounded-2xl grid place-items-center shrink-0" :style="{ background: domainAccent.bg }">
                                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                                  <circle cx="10" cy="10" r="7.5" :stroke="domainAccent.ink" stroke-width="1.6" />
                                  <path d="M10 6.5v4M10 12.5v.5" :stroke="domainAccent.ink" stroke-width="1.6" stroke-linecap="round" />
                                </svg>
                              </div>
                              <div>
                                <div class="text-[13px] font-semibold text-[#0F1115]">
                                  Найдено записей: <span :style="{ color: domainAccent.ink }">{{ bulkFilterPreview.total }}</span>
                                </div>
                                <div class="text-[11.5px] text-[#5A5E6E] mt-0.5">
                                  Файл будет прикреплён к каждой найденной записи
                                </div>
                              </div>
                            </div>
                          </div>

                          <div v-if="showBulkAttachExecutionState" class="rounded-2xl border border-[#ECEEF3] bg-[#fbfcfe] p-5">
                            <div class="flex items-center justify-between gap-3">
                              <div>
                                <div class="text-[13px] font-semibold text-[#0F1115]">Загрузка файла</div>
                                <div class="mt-0.5 text-[11.5px] text-[#5A5E6E]">
                                  <template v-if="busyAction === 'bulk-attach-run'">Подготавливаем файл и создаём сессию загрузки.</template>
                                  <template v-else-if="bulkAttachSessionStatus === 'running'">Файл уже загружается, статус обновляется автоматически.</template>
                                  <template v-else-if="bulkAttachSessionStatus === 'completed'">Загрузка завершена.</template>
                                  <template v-else-if="bulkAttachSessionStatus === 'failed'">Во время загрузки произошла ошибка.</template>
                                  <template v-else-if="bulkAttachSessionStatus === 'cancelled'">Загрузка была остановлена.</template>
                                </div>
                              </div>
                              <span
                                class="inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold"
                                :style="bulkAttachSessionStatus === 'completed'
                                  ? { background: '#E8F6EE', color: '#1E8A52' }
                                  : bulkAttachSessionStatus === 'failed'
                                    ? { background: '#FDECEC', color: '#C24B53' }
                                    : { background: domainAccent.bg, color: domainAccent.ink }"
                              >
                                {{ busyAction === 'bulk-attach-run' ? 'Подготовка' : bulkAttachActionLabel }}
                              </span>
                            </div>

                            <div class="mt-4 h-2 overflow-hidden rounded-full bg-[#E8EDF4]">
                              <div
                                class="h-full rounded-full transition-all"
                                :style="{ width: `${bulkAttachProgressPercent}%`, background: domainAccent.ink }"
                              />
                            </div>

                            <div class="mt-3 flex items-center justify-between text-[12px] text-[#5A5E6E]">
                              <span>Обработано: {{ bulkAttachProgressProcessed }} / {{ bulkAttachProgressTotal || bulkFilterPreview.total }}</span>
                              <span>{{ bulkAttachProgressPercent }}%</span>
                            </div>

                            <div
                              v-if="bulkAttachSessionStatus === 'completed' || bulkAttachSessionStatus === 'failed' || bulkAttachSessionStatus === 'cancelled'"
                              class="mt-4 grid grid-cols-3 gap-3"
                            >
                              <div class="rounded-[14px] border border-[#E5EBF2] bg-white px-4 py-3">
                                <div class="text-[11px] uppercase tracking-[0.08em] text-[#8EA0B2]">Всего</div>
                                <div class="mt-1 text-lg font-semibold text-[#0F1115]">{{ bulkAttachResultTotal }}</div>
                              </div>
                              <div class="rounded-[14px] border border-[#E5EBF2] bg-white px-4 py-3">
                                <div class="text-[11px] uppercase tracking-[0.08em] text-[#8EA0B2]">Успешно</div>
                                <div class="mt-1 text-lg font-semibold text-[#1E8A52]">{{ bulkAttachResultSuccessful }}</div>
                              </div>
                              <div class="rounded-[14px] border border-[#E5EBF2] bg-white px-4 py-3">
                                <div class="text-[11px] uppercase tracking-[0.08em] text-[#8EA0B2]">Ошибки</div>
                                <div class="mt-1 text-lg font-semibold text-[#C24B53]">{{ bulkAttachResultFailed }}</div>
                              </div>
                            </div>

                            <div class="mt-4 flex flex-wrap gap-3">
                              <B24Button
                                v-if="canCancelBulkAttach || busyAction === 'bulk-attach-cancel'"
                                label="Остановить"
                                color="air-tertiary"
                                size="lg"
                                :loading="busyAction === 'bulk-attach-cancel'"
                                :disabled="!canCancelBulkAttach"
                                @click="cancelBulkAttachExecution"
                              />
                              <B24Button
                                v-if="bulkAttachSessionStatus === 'completed' || bulkAttachSessionStatus === 'failed' || bulkAttachSessionStatus === 'cancelled'"
                                label="Завершить"
                                color="air-primary"
                                size="lg"
                                @click="finishInlineBulkAttachFlow"
                              />
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- Footer hint -->
                      <div v-if="crmFlavor !== 'bulk' || !bulkFilterPreview" class="mt-auto pt-5 flex items-center gap-2 text-[12px] text-[#5A5E6E]">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.2" />
                          <path d="M7 4.5v3M7 9.2v.3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
                        </svg>
                        <template v-if="crmFlavor === 'linked'">Свяжем строки по выбранному полю — без дублей.</template>
                        <template v-else-if="crmFlavor === 'bulk'">К каждой строке файла приложим один файл-вложение.</template>
                        <template v-else>Можно подключить шаблон сопоставления полей.</template>
                      </div>
                    </div>

                    <!-- Right column: dropzone + template -->
                    <div class="flex flex-col gap-4">
                      <!-- Dropzone -->
                      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                        Файл
                      </div>
                      <div
                        class="rounded-2xl p-5 flex-1 flex flex-col items-center justify-center text-center relative overflow-hidden transition-all"
                        :class="crmFlavor === 'bulk' && isBulkFilePickerLocked ? 'cursor-not-allowed' : 'cursor-pointer'"
                        :style="{
                          border: crmFlavor === 'bulk' && isBulkFilePickerLocked
                            ? '1.5px dashed #D8E1EB'
                            : (dropzoneDragOver ? `1.5px dashed ${domainAccent.ink}` : `1.5px dashed ${domainAccent.ink}55`),
                          background: crmFlavor === 'bulk' && isBulkFilePickerLocked
                            ? '#F8FAFC'
                            : (dropzoneDragOver ? domainAccent.bg : '#FFFFFF'),
                        }"
                        @dragover.prevent="!isBulkFilePickerLocked && (dropzoneDragOver = true)"
                        @dragleave.prevent="dropzoneDragOver = false"
                        @drop.prevent="handleDropFile($event)"
                        @click="openFilePicker"
                      >
                        <div
                          class="absolute inset-0 pointer-events-none opacity-50"
                          :style="{
                            backgroundImage: `radial-gradient(circle, ${domainAccent.ink}15 1px, transparent 1.5px)`,
                            backgroundSize: '18px 18px',
                            maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
                            WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
                          }"
                        />
                        <div
                          class="relative w-12 h-12 rounded-2xl grid place-items-center mb-3 transition-transform"
                          :style="crmFlavor === 'bulk' && isBulkFilePickerLocked
                            ? { background: '#FFFFFF', color: '#8EA0B2' }
                            : { background: dropzoneDragOver ? '#FFFFFF' : domainAccent.bg, color: domainAccent.ink }"
                        >
                          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                            <path d="M11 14V4M7 8l4-4 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                            <path d="M3 14v3a2 2 0 002 2h12a2 2 0 002-2v-3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                          </svg>
                        </div>
                        <div class="relative text-[14px] font-semibold tracking-tight text-[#0F1115]">
                          {{ crmFlavor === 'bulk' && isBulkFilePickerLocked
                            ? (isBulkAttachExecutionLocked
                                ? 'Загрузка уже выполняется'
                                : 'Сначала выберите CRM-сущность и поле для файлов')
                            : (dropzoneDragOver ? 'Отпустите для загрузки' : 'Перетащите файл сюда') }}
                        </div>
                        <p class="relative mt-1 text-[11.5px] text-[#5A5E6E]" :title="currentFilePickerHelperText">
                          {{ crmFlavor === 'bulk' && isBulkFilePickerLocked
                            ? (isBulkAttachExecutionLocked
                                ? 'Загрузка уже выполняется. Чтобы заменить файл, сначала остановите текущую сессию.'
                                : 'Правый блок станет активным после выбора поля назначения.')
                            : currentFileDropdownLimitText }}
                        </p>
                        <div v-if="fileName" class="relative mt-1 text-[11.5px] font-semibold" :style="{ color: domainAccent.ink }">
                          {{ fileName }}
                        </div>
                        <input ref="fileInputRef" type="file" :accept="isSpreadsheetUploadRequired ? '.xlsx,.xls,.csv' : undefined" class="hidden" @change="handleFileChange" />
                        <button
                          type="button"
                          class="relative mt-3 h-9 px-4 text-[12.5px] rounded-xl font-semibold text-white transition-opacity hover:opacity-85 active:opacity-70"
                          :style="crmFlavor === 'bulk' && isBulkFilePickerLocked
                            ? { background: '#C8D2DE' }
                            : { background: domainAccent.ink }"
                          :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction) || isBulkFilePickerLocked"
                          @click.stop="openFilePicker"
                        >
                          Выбрать файл
                        </button>
                      </div>

                      <!-- Template download -->
                      <div v-if="crmFlavor !== 'bulk'" class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                        Шаблон
                      </div>
                      <div v-if="crmFlavor !== 'bulk'" class="rounded-2xl p-4 flex items-center gap-3" :style="{ background: domainAccent.bg }">
                        <div
                          class="w-10 h-10 rounded-xl grid place-items-center shrink-0 bg-white"
                          :style="{ color: domainAccent.ink }"
                        >
                          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <rect x="3" y="3" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.6" />
                            <path d="M3 7h12M3 11h12M7 3v12M11 3v12" stroke="currentColor" stroke-width="1.2" opacity=".6" />
                          </svg>
                        </div>
                        <div class="min-w-0 flex-1">
                          <div class="text-[12.5px] font-semibold tracking-tight" :style="{ color: domainAccent.ink }">{{ exampleTemplateDownloadMeta.title }}</div>
                          <div class="text-[11px] mt-0.5 text-[#5A5E6E]">{{ exampleTemplateDownloadMeta.description }}</div>
                        </div>
                        <B24Button
                          label="Скачать"
                          color="air-secondary-accent-2"
                          size="sm"
                          :loading="busyAction === 'example-template'"
                          :disabled="!canDownloadExampleTemplate"
                          @click="downloadExampleTemplate"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Задачи подэкран -->
                <div v-else-if="selectedFamily === 'task'" class="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                  <div class="space-y-4">
                    <section class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                      <div class="text-sm font-semibold text-[#314256]">Импорт в задачи</div>
                      <div class="mt-1 text-sm text-[#6f8194]">Выберите, что импортировать в задачи.</div>
                      <B24FormField label="Выберите тип импорта" class="mt-4">
                        <B24Select
                          :model-value="selectedTaskEntityType"
                          :items="taskScenarioItems"
                          placeholder="Например, Чек-листы задач"
                          size="lg"
                          class="w-full"
                          :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                          @update:model-value="updateScenarioEntityType('task', String($event || ''))"
                        />
                      </B24FormField>
                    </section>

                    <section v-if="selectedTaskEntityType === 'task_attachment'" class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                      <div class="text-sm font-semibold text-[#314256]">Массовое добавление вложений</div>
                      <div class="mt-1 text-sm text-[#6f8194]">Найдём задачи по фильтру и прикрепим к каждой один и тот же файл.</div>

                      <div v-if="selectedTaskEntityType === 'task_attachment' && !bulkFilterPreview" class="mt-5 space-y-4">
                        <div class="text-[12px] font-medium text-[#5A5E6E]">Фильтр задач:</div>

                        <div
                          v-for="condition in bulkFilterConditions"
                          :key="condition.fieldId"
                          class="rounded-[16px] border border-[#e5ebf2] bg-white px-4 py-4"
                        >
                          <div class="flex items-center justify-between gap-3">
                            <div class="text-sm font-semibold text-[#314256]">
                              {{ resolveBulkFilterField(condition.fieldId)?.title || condition.fieldId }}
                            </div>
                            <button
                              type="button"
                              class="rounded-full border border-[#f3d3c2] bg-white px-3 py-1 text-xs font-medium text-[#8a4a28] transition hover:border-[#f0b7b7] hover:text-[#c24b53]"
                              @click="removeBulkFilterField(condition.fieldId)"
                            >
                              Удалить
                            </button>
                          </div>

                          <B24SelectMenu
                            v-if="getBulkFilterValueOptions(condition.fieldId).length"
                            :model-value="condition.value"
                            class="mt-3 w-full"
                            placeholder="Выберите значение Bitrix24"
                            :items="getBulkFilterValueOptions(condition.fieldId)"
                            value-key="value"
                            :filter-fields="['label']"
                            :search-input="{ placeholder: 'Поиск значения Bitrix24' }"
                            @update:model-value="condition.value = String($event || '')"
                          />
                          <input
                            v-else
                            v-model="condition.value"
                            type="text"
                            :placeholder="`Введите значение для поля «${resolveBulkFilterField(condition.fieldId)?.title || condition.fieldId}»`"
                            class="mt-3 w-full rounded-[10px] border border-[#f3d3c2] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#D8632A]"
                          />
                        </div>

                        <div v-if="isAddingBulkFilterField" class="rounded-[16px] border border-[#f3d3c2] bg-[#FFF8F3] px-4 py-4">
                          <B24SelectMenu
                            :model-value="pendingBulkFilterFieldId"
                            class="w-full"
                            placeholder="Выберите поле задачи"
                            :items="bulkFilterFieldOptions"
                            value-key="value"
                            :filter-fields="['label']"
                            :search-input="{ placeholder: 'Поиск поля Bitrix24' }"
                            @update:model-value="addBulkFilterField(String($event || ''))"
                          />
                        </div>

                        <button
                          type="button"
                          class="inline-flex items-center rounded-full border border-dashed border-[#f0c5ad] bg-transparent px-4 py-2 text-sm font-medium text-[#8a4a28] transition hover:border-[#D8632A] hover:text-[#D8632A]"
                          :disabled="Boolean(busyAction)"
                          @click="openAddBulkFilterField"
                        >
                          Добавить поле
                        </button>

                        <div class="rounded-[16px] border border-[#f3d3c2] bg-[#FFF8F3] px-4 py-3 text-[12px] text-[#8a4a28]">
                          Если фильтр не задан, будут выбраны все доступные задачи.
                        </div>
                      </div>

                      <div v-else-if="selectedTaskEntityType === 'task_attachment'" class="mt-5 space-y-4">
                        <div class="rounded-2xl border border-[#ECEEF3] bg-white p-5">
                          <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-2xl grid place-items-center shrink-0" :style="{ background: domainAccent.bg }">
                              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                                <circle cx="10" cy="10" r="7.5" :stroke="domainAccent.ink" stroke-width="1.6" />
                                <path d="M10 6.5v4M10 12.5v.5" :stroke="domainAccent.ink" stroke-width="1.6" stroke-linecap="round" />
                              </svg>
                            </div>
                            <div>
                              <div class="text-[13px] font-semibold text-[#0F1115]">
                                Найдено задач: <span :style="{ color: domainAccent.ink }">{{ bulkFilterPreview.total }}</span>
                              </div>
                              <div class="text-[11.5px] text-[#5A5E6E] mt-0.5">
                                Один файл будет прикреплён ко всем найденным задачам
                              </div>
                            </div>
                          </div>
                        </div>

                        <div v-if="showBulkAttachExecutionState" class="rounded-2xl border border-[#ECEEF3] bg-[#fbfcfe] p-5">
                          <div class="flex items-center justify-between gap-3">
                            <div>
                              <div class="text-[13px] font-semibold text-[#0F1115]">Загрузка вложения</div>
                              <div class="mt-0.5 text-[11.5px] text-[#5A5E6E]">
                                <template v-if="busyAction === 'bulk-attach-run'">Подготавливаем файл и создаём сессию загрузки.</template>
                                <template v-else-if="bulkAttachSessionStatus === 'running'">Файл уже прикрепляется, статус обновляется автоматически.</template>
                                <template v-else-if="bulkAttachSessionStatus === 'completed'">Загрузка завершена.</template>
                                <template v-else-if="bulkAttachSessionStatus === 'failed'">Во время загрузки произошла ошибка.</template>
                                <template v-else-if="bulkAttachSessionStatus === 'cancelled'">Загрузка была остановлена.</template>
                              </div>
                            </div>
                            <span
                              class="inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold"
                              :style="bulkAttachSessionStatus === 'completed'
                                ? { background: '#E8F6EE', color: '#1E8A52' }
                                : bulkAttachSessionStatus === 'failed'
                                  ? { background: '#FDECEC', color: '#C24B53' }
                                  : { background: domainAccent.bg, color: domainAccent.ink }"
                            >
                              {{ busyAction === 'bulk-attach-run' ? 'Подготовка' : bulkAttachActionLabel }}
                            </span>
                          </div>

                          <div class="mt-4 h-2 overflow-hidden rounded-full bg-[#E8EDF4]">
                            <div
                              class="h-full rounded-full transition-all"
                              :style="{ width: `${bulkAttachProgressPercent}%`, background: domainAccent.ink }"
                            />
                          </div>

                          <div class="mt-3 flex items-center justify-between text-[12px] text-[#5A5E6E]">
                            <span>Обработано: {{ bulkAttachProgressProcessed }} / {{ bulkAttachProgressTotal || bulkFilterPreview.total }}</span>
                            <span>{{ bulkAttachProgressPercent }}%</span>
                          </div>

                          <div
                            v-if="bulkAttachSessionStatus === 'completed' || bulkAttachSessionStatus === 'failed' || bulkAttachSessionStatus === 'cancelled'"
                            class="mt-4 grid grid-cols-3 gap-3"
                          >
                            <div class="rounded-[14px] border border-[#E5EBF2] bg-white px-4 py-3">
                              <div class="text-[11px] uppercase tracking-[0.08em] text-[#8EA0B2]">Всего</div>
                              <div class="mt-1 text-lg font-semibold text-[#0F1115]">{{ bulkAttachResultTotal }}</div>
                            </div>
                            <div class="rounded-[14px] border border-[#E5EBF2] bg-white px-4 py-3">
                              <div class="text-[11px] uppercase tracking-[0.08em] text-[#8EA0B2]">Успешно</div>
                              <div class="mt-1 text-lg font-semibold text-[#1E8A52]">{{ bulkAttachResultSuccessful }}</div>
                            </div>
                            <div class="rounded-[14px] border border-[#E5EBF2] bg-white px-4 py-3">
                              <div class="text-[11px] uppercase tracking-[0.08em] text-[#8EA0B2]">Ошибки</div>
                              <div class="mt-1 text-lg font-semibold text-[#C24B53]">{{ bulkAttachResultFailed }}</div>
                            </div>
                          </div>

                          <div class="mt-4 flex flex-wrap gap-3">
                            <B24Button
                              v-if="canCancelBulkAttach || busyAction === 'bulk-attach-cancel'"
                              label="Остановить"
                              color="air-tertiary"
                              size="lg"
                              :loading="busyAction === 'bulk-attach-cancel'"
                              :disabled="!canCancelBulkAttach"
                              @click="cancelBulkAttachExecution"
                            />
                            <B24Button
                              v-if="bulkAttachSessionStatus === 'completed' || bulkAttachSessionStatus === 'failed' || bulkAttachSessionStatus === 'cancelled'"
                              label="Завершить"
                              color="air-primary"
                              size="lg"
                              @click="finishInlineBulkAttachFlow"
                            />
                          </div>
                        </div>

                        <div v-else class="rounded-2xl border border-[#ECEEF3] bg-white p-5">
                          <div class="flex items-center justify-between gap-3">
                            <div>
                              <div class="text-[13px] font-semibold text-[#0F1115]">Показаны первые 5 задач</div>
                              <div class="mt-0.5 text-[11.5px] text-[#5A5E6E]">Проверьте выборку перед запуском прикрепления.</div>
                            </div>
                            <button
                              type="button"
                              class="rounded-full border border-[#f0c5ad] bg-white px-3 py-1 text-xs font-medium text-[#8a4a28] transition hover:border-[#D8632A] hover:text-[#D8632A]"
                              @click="goBackFromBulkPreview"
                            >
                              Изменить фильтр
                            </button>
                          </div>

                          <div class="mt-4 space-y-3">
                            <div
                              v-for="sample in bulkFilterPreview.sample"
                              :key="sample.id"
                              class="rounded-[14px] border border-[#f4e0d4] bg-[#fffaf7] px-4 py-3"
                            >
                              <div class="text-sm font-semibold text-[#314256]">#{{ sample.id }}</div>
                              <div class="mt-1 text-[12.5px] text-[#5A5E6E]">{{ sample.title || 'Без названия' }}</div>
                            </div>
                            <div v-if="!bulkFilterPreview.sample.length" class="rounded-[14px] border border-dashed border-[#f0c5ad] bg-[#fffaf7] px-4 py-4 text-[12px] text-[#8a4a28]">
                              Превью пустое. Проверьте фильтр или загрузите файл и запустите прикрепление для всей выборки.
                            </div>
                          </div>
                        </div>
                      </div>
                    </section>
                  </div>
                  <div class="flex flex-col gap-4">
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Файл</div>
                    <div
                      class="rounded-2xl p-5 flex-1 flex flex-col items-center justify-center text-center relative overflow-hidden transition-all"
                      :class="isBulkAttachFlow && isBulkFilePickerLocked ? 'cursor-not-allowed' : 'cursor-pointer'"
                      :style="{
                        border: isBulkAttachFlow && isBulkFilePickerLocked
                          ? '1.5px dashed #D8E1EB'
                          : (dropzoneDragOver ? `1.5px dashed ${domainAccent.ink}` : `1.5px dashed ${domainAccent.ink}55`),
                        background: isBulkAttachFlow && isBulkFilePickerLocked
                          ? '#F8FAFC'
                          : (dropzoneDragOver ? domainAccent.bg : '#FFFFFF'),
                      }"
                      @dragover.prevent="!isBulkFilePickerLocked && (dropzoneDragOver = true)"
                      @dragleave.prevent="dropzoneDragOver = false"
                      @drop.prevent="handleDropFile($event)"
                      @click="openFilePicker"
                    >
                      <div
                        class="absolute inset-0 pointer-events-none opacity-50"
                        :style="{
                          backgroundImage: `radial-gradient(circle, ${domainAccent.ink}15 1px, transparent 1.5px)`,
                          backgroundSize: '18px 18px',
                          maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
                          WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
                        }"
                      />
                      <div
                        class="relative w-12 h-12 rounded-2xl grid place-items-center mb-3 transition-transform"
                        :style="{ background: dropzoneDragOver ? '#FFFFFF' : domainAccent.bg, color: domainAccent.ink }"
                      >
                        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                          <path d="M11 14V4M7 8l4-4 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                          <path d="M3 14v3a2 2 0 002 2h12a2 2 0 002-2v-3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                        </svg>
                      </div>
                      <div class="relative text-[14px] font-semibold tracking-tight text-[#0F1115]">
                        {{ isBulkAttachFlow && isBulkFilePickerLocked
                          ? (isBulkAttachExecutionLocked
                              ? 'Загрузка уже выполняется'
                              : 'Сначала настройте выборку задач')
                          : (dropzoneDragOver ? 'Отпустите для загрузки' : 'Перетащите файл сюда') }}
                      </div>
                      <p class="relative mt-1 text-[11.5px] text-[#5A5E6E]" :title="currentFilePickerHelperText">
                        {{ isBulkAttachFlow && isBulkFilePickerLocked
                          ? (isBulkAttachExecutionLocked
                              ? 'Загрузка уже выполняется. Чтобы заменить файл, сначала остановите текущую сессию.'
                              : 'Правый блок станет активным после проверки выборки задач.')
                          : currentFileDropdownLimitText }}
                      </p>
                      <div v-if="fileName" class="relative mt-1 text-[11.5px] font-semibold" :style="{ color: domainAccent.ink }">
                        {{ fileName }}
                      </div>
                      <input ref="fileInputRef" type="file" :accept="isSpreadsheetUploadRequired ? '.xlsx,.xls,.csv' : undefined" class="hidden" @change="handleFileChange" />
                      <button
                        type="button"
                        class="relative mt-3 h-9 px-4 text-[12.5px] rounded-xl font-semibold text-white transition-opacity hover:opacity-85 active:opacity-70"
                        :style="isBulkAttachFlow && isBulkFilePickerLocked
                          ? { background: '#C8D2DE' }
                          : { background: domainAccent.ink }"
                        :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction) || isBulkFilePickerLocked"
                        @click.stop="openFilePicker"
                      >
                        Выбрать файл
                      </button>
                    </div>
                    <template v-if="selectedTaskEntityType === 'task_attachment'">
                      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Режим</div>
                      <div class="rounded-2xl p-4 flex items-center gap-3" :style="{ background: domainAccent.bg }">
                        <div class="w-10 h-10 rounded-xl grid place-items-center shrink-0 bg-white" :style="{ color: domainAccent.ink }">
                          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <path d="M6 5.5h6a2 2 0 0 1 0 4H7.5a2.5 2.5 0 0 0 0 5H11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                            <path d="M9.5 7.5h1.5a2 2 0 1 1 0 4H8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".55" />
                          </svg>
                        </div>
                        <div class="min-w-0 flex-1">
                          <div class="text-[12.5px] font-semibold tracking-tight" :style="{ color: domainAccent.ink }">Excel-шаблон здесь не нужен</div>
                          <div class="text-[11px] mt-0.5 text-[#5A5E6E]">Настройте фильтр задач, загрузите один файл и запустите прикрепление ко всем найденным задачам.</div>
                        </div>
                      </div>
                    </template>
                    <template v-else>
                      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаблон</div>
                      <div class="rounded-2xl p-4 flex items-center gap-3" :style="{ background: domainAccent.bg }">
                        <div class="w-10 h-10 rounded-xl grid place-items-center shrink-0 bg-white" :style="{ color: domainAccent.ink }">
                          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <rect x="3" y="3" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.6" />
                            <path d="M3 7h12M3 11h12M7 3v12M11 3v12" stroke="currentColor" stroke-width="1.2" opacity=".6" />
                          </svg>
                        </div>
                        <div class="min-w-0 flex-1">
                          <div class="text-[12.5px] font-semibold tracking-tight" :style="{ color: domainAccent.ink }">{{ exampleTemplateDownloadMeta.title }}</div>
                          <div class="text-[11px] mt-0.5 text-[#5A5E6E]">{{ exampleTemplateDownloadMeta.description }}</div>
                        </div>
                        <B24Button
                          label="Скачать"
                          color="air-secondary-accent-2"
                          size="sm"
                          :loading="busyAction === 'example-template'"
                          :disabled="!canDownloadExampleTemplate"
                          @click="downloadExampleTemplate"
                        />
                      </div>
                    </template>
                  </div>
                </div>

                <!-- HR подэкран -->
                <div v-else-if="selectedFamily === 'hr'" class="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                  <div class="space-y-4">
                    <section class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                      <div class="text-sm font-semibold text-[#314256]">Пользователи и отделы</div>
                      <div class="mt-1 text-sm text-[#6f8194]">Импорт пользователей и структуры компании.</div>
                      <B24FormField label="Выберите тип импорта" class="mt-4">
                        <B24Select
                          :model-value="selectedHrEntityType"
                          :items="hrScenarioItems"
                          placeholder="Например, Пользователи"
                          size="lg"
                          class="w-full"
                          :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                          @update:model-value="updateScenarioEntityType('hr', String($event || ''))"
                        />
                      </B24FormField>
                    </section>

                    <section class="rounded-[18px] border border-[#dce7f7] bg-[#f4f9ff] p-4">
                      <div class="text-sm font-semibold text-[#2e5ba8]">ID отделов</div>
                      <div class="mt-1 text-sm text-[#4a6d9c]">
                        Для привязки к отделу укажите числовой ID в колонке «Отдел (ID)».
                        Посмотрите список отделов вашего портала с их ID.
                      </div>
                      <B24Button
                        class="mt-3"
                        :label="departmentsExpanded ? 'Скрыть список' : 'Показать отделы'"
                        color="air-primary"
                        size="sm"
                        :loading="loadingDepartments"
                        @click="toggleDepartments"
                      />
                      <div v-if="departmentsExpanded" class="mt-4">
                        <div v-if="departments.length > 0" class="overflow-x-auto rounded-[10px] border border-[#dce7f7]">
                          <table class="w-full text-sm">
                            <thead class="bg-[#eaf3ff]">
                              <tr>
                                <th class="px-3 py-2 text-left font-semibold text-[#2e5ba8]">ID</th>
                                <th class="px-3 py-2 text-left font-semibold text-[#2e5ba8]">Название</th>
                                <th class="px-3 py-2 text-left font-semibold text-[#2e5ba8]">ID родителя</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr
                                v-for="dept in departments"
                                :key="dept.id"
                                class="border-t border-[#dce7f7] hover:bg-[#f4f9ff]"
                              >
                                <td class="px-3 py-2 font-mono font-semibold text-[#2e5ba8]">{{ dept.id }}</td>
                                <td class="px-3 py-2 text-[#314256]">{{ dept.name }}</td>
                                <td class="px-3 py-2 text-[#7f8d9c]">{{ dept.parent_id || '—' }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <div v-else-if="!loadingDepartments" class="mt-2 text-sm text-[#7f8d9c]">
                          Отделы не найдены
                        </div>
                      </div>
                    </section>
                  </div>

                  <div class="flex flex-col gap-4">
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Файл</div>
                    <div
                      class="rounded-2xl p-5 flex-1 flex flex-col items-center justify-center text-center relative overflow-hidden transition-all cursor-pointer"
                      :style="{
                        border: dropzoneDragOver ? `1.5px dashed ${domainAccent.ink}` : `1.5px dashed ${domainAccent.ink}55`,
                        background: dropzoneDragOver ? domainAccent.bg : '#FFFFFF',
                      }"
                      @dragover.prevent="dropzoneDragOver = true"
                      @dragleave.prevent="dropzoneDragOver = false"
                      @drop.prevent="handleDropFile($event)"
                      @click="openFilePicker"
                    >
                      <div
                        class="absolute inset-0 pointer-events-none opacity-50"
                        :style="{
                          backgroundImage: `radial-gradient(circle, ${domainAccent.ink}15 1px, transparent 1.5px)`,
                          backgroundSize: '18px 18px',
                          maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
                          WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
                        }"
                      />
                      <div
                        class="relative w-12 h-12 rounded-2xl grid place-items-center mb-3 transition-transform"
                        :style="{ background: dropzoneDragOver ? '#FFFFFF' : domainAccent.bg, color: domainAccent.ink }"
                      >
                        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                          <path d="M11 14V4M7 8l4-4 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                          <path d="M3 14v3a2 2 0 002 2h12a2 2 0 002-2v-3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
                        </svg>
                      </div>
                      <div class="relative text-[14px] font-semibold tracking-tight text-[#0F1115]">
                        {{ dropzoneDragOver ? 'Отпустите для загрузки' : 'Перетащите файл сюда' }}
                      </div>
                      <p class="relative mt-1 text-[11.5px] text-[#5A5E6E]" :title="IMPORT_FILE_PICKER_HELPER_TEXT">{{ IMPORT_FILE_DROPDOWN_LIMIT_TEXT }}</p>
                      <div v-if="fileName" class="relative mt-1 text-[11.5px] font-semibold" :style="{ color: domainAccent.ink }">
                        {{ fileName }}
                      </div>
                      <input ref="fileInputRef" type="file" accept=".xlsx,.xls,.csv" class="hidden" @change="handleFileChange" />
                      <button
                        type="button"
                        class="relative mt-3 h-9 px-4 text-[12.5px] rounded-xl font-semibold text-white transition-opacity hover:opacity-85 active:opacity-70"
                        :style="{ background: domainAccent.ink }"
                        :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                        @click.stop="openFilePicker"
                      >
                        Выбрать файл
                      </button>
                    </div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаблон</div>
                    <div class="rounded-2xl p-4 flex items-center gap-3" :style="{ background: domainAccent.bg }">
                      <div class="w-10 h-10 rounded-xl grid place-items-center shrink-0 bg-white" :style="{ color: domainAccent.ink }">
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                          <rect x="3" y="3" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.6" />
                          <path d="M3 7h12M3 11h12M7 3v12M11 3v12" stroke="currentColor" stroke-width="1.2" opacity=".6" />
                        </svg>
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="text-[12.5px] font-semibold tracking-tight" :style="{ color: domainAccent.ink }">{{ exampleTemplateDownloadMeta.title }}</div>
                        <div class="text-[11px] mt-0.5 text-[#5A5E6E]">{{ exampleTemplateDownloadMeta.description }}</div>
                      </div>
                      <B24Button
                        label="Скачать"
                        color="air-secondary-accent-2"
                        size="sm"
                        :loading="busyAction === 'example-template'"
                        :disabled="!canDownloadExampleTemplate"
                        @click="downloadExampleTemplate"
                      />
                    </div>
                  </div>
                </div>
            </div>
            </Transition>
          </div>

          <section v-if="currentStep === 2" class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
            <div class="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 2</div>
                <h2 class="mt-1 text-xl font-semibold text-[#314256]">Параметры чтения файла</h2>
              </div>

              <div class="flex flex-wrap gap-3">
                <B24Button
                  label="Назад"
                  color="air-primary"
                  size="lg"
                  :disabled="!canGoBack"
                  @click="goBack"
                />
                <B24Button
                  label="Применить и продолжить"
                  color="air-primary"
                  size="lg"
                  :loading="busyAction === 'structure'"
                  :disabled="!canApplyStructure"
                  @click="applyStructure"
                />
              </div>
            </div>

            <div class="grid gap-5 lg:grid-cols-[minmax(0,220px)_minmax(0,220px)_minmax(0,1fr)]">
              <div class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                <B24FormField label="Строка заголовков" class="w-full">
                  <B24InputNumber
                    v-model="headerRowInput"
                    class="w-full"
                    size="lg"
                    :min="1"
                  />
                </B24FormField>
              </div>

              <div class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                <B24FormField label="Строка начала данных" class="w-full">
                  <B24InputNumber
                    v-model="dataStartRowInput"
                    class="w-full"
                    size="lg"
                    :min="1"
                  />
                </B24FormField>
              </div>

              <div class="grid gap-3 sm:grid-cols-3">
                <div class="rounded-[18px] border border-[#e5ebf2] bg-white px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Колонки</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ previewColumnsSource.length || 0 }}</div>
                </div>
                <div class="rounded-[18px] border border-[#e5ebf2] bg-white px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Строки данных</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ previewTotalRows || 0 }}</div>
                </div>
                <div class="rounded-[18px] border border-[#e5ebf2] bg-white px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Лист</div>
                  <div class="mt-1 truncate text-lg font-semibold text-[#314256]">{{ preview?.selected_sheet_name || '—' }}</div>
                </div>
              </div>
            </div>

            <div
              v-if="previewRowLimitExceeded"
              class="mt-5 rounded-[18px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-4 text-[#8f5b18]"
            >
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#c77d2b]">Лимит строк на импорт</div>
              <div class="mt-2 text-sm font-semibold">{{ previewRowLimitError }}</div>
              <div class="mt-2 text-sm text-[#9c6a2a]">
                Измените файл или разбейте импорт на несколько частей. Максимум для одного запуска: {{ preview?.max_import_rows || '—' }} строк.
              </div>
            </div>

          </section>

          <section v-if="currentStep === 3" class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
            <div class="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 3</div>
                <h2 class="mt-1 text-xl font-semibold text-[#314256]">Пример файла</h2>
              </div>

              <div class="flex flex-wrap items-center gap-3">
                <div class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium text-[#2e6bd9]">
                  {{ previewTableRows.length }} строк в предпросмотре
                </div>
                <B24Button
                  label="Назад"
                  color="air-primary"
                  size="lg"
                  :disabled="!canGoBack"
                  @click="goBack"
                />
                <B24Button
                  :label="nextStepLabel"
                  color="air-primary"
                  size="lg"
                  :disabled="!canGoNext"
                  @click="goNext"
                />
              </div>
            </div>

            <div
              v-if="previewRowLimitExceeded"
              class="mb-5 rounded-[18px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-4 text-[#8f5b18]"
            >
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#c77d2b]">Лимит строк на импорт</div>
              <div class="mt-2 text-sm font-semibold">{{ previewRowLimitError }}</div>
              <div class="mt-2 text-sm text-[#9c6a2a]">
                В предпросмотре показаны только первые строки. Всего данных: {{ previewTotalRows }}.
              </div>
            </div>

            <div class="overflow-hidden rounded-[20px] border border-[#dfe5eb] bg-white">
              <B24Table
                class="w-full"
                :loading="busyAction === 'start' || busyAction === 'structure'"
                loading-color="air-primary"
                loading-animation="loading"
                :columns="previewTableColumns"
                :data="previewTableRows"
                empty="После загрузки файла здесь появится пример первых строк."
              />
            </div>

          </section>

          <section v-if="currentStep === 4" class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
            <div class="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 4</div>
                <h2 class="mt-1 text-xl font-semibold text-[#314256]">Соответствие полей</h2>
              </div>

              <div class="flex flex-wrap gap-3">
                <B24Button
                  label="Назад"
                  color="air-primary"
                  size="lg"
                  :disabled="!canGoBack"
                  @click="goBack"
                />
                <B24Button
                  label="Заполнить автоматически"
                  color="air-secondary-accent-2"
                  size="lg"
                  :disabled="!mappingData"
                  @click="applyCandidateMapping"
                />
                <B24Button
                  label="Сохранить соответствие"
                  color="air-primary"
                  size="lg"
                  :loading="busyAction === 'mapping'"
                  :disabled="!canSaveMapping"
                  @click="saveMapping"
                />
                <B24Button
                  v-if="!hasPendingMappingChanges"
                  :label="nextStepLabel"
                  color="air-primary"
                  size="lg"
                  :disabled="!canGoNextFromMapping"
                  @click="goNext"
                />
              </div>
            </div>
            <div
              v-if="hasPendingMappingChanges"
              class="mb-5 rounded-[16px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3 text-sm text-[#5f7285]"
            >
              Сохраните соответствие и выбранные значения по умолчанию, чтобы перейти к следующему шагу.
            </div>

            <section
              class="mb-5 rounded-[18px] border px-4 py-3 text-sm"
              :class="requiredFieldSummary.hasMissingRequired
                ? 'border-[#ffe1c7] bg-[#fff7ef]'
                : 'border-[#d7e7ff] bg-[#f4f9ff]'"
            >
              <div class="flex flex-wrap items-center gap-3">
                <span
                  class="font-semibold"
                  :class="requiredFieldSummary.hasMissingRequired ? 'text-[#a96017]' : 'text-[#2e6bd9]'"
                >
                  {{ requiredFieldSummary.hasRequiredFields
                    ? (requiredFieldSummary.hasMissingRequired
                      ? `Минимум без ошибки: ${requiredFieldSummary.mappedRequired} из ${requiredFieldSummary.totalRequired}`
                      : `Обязательные поля сопоставлены: ${requiredFieldSummary.totalRequired} из ${requiredFieldSummary.totalRequired}`)
                    : 'Обязательных полей нет' }}
                </span>
                <span class="text-[#6f8194]">
                  {{ requiredFieldSummary.hasRequiredFields
                    ? 'На проверке и импорте эти поля нужны в первую очередь.'
                    : 'Можно продолжать без обязательного минимума.' }}
                </span>
              </div>

              <div
                v-if="requiredFieldSummary.hasRequiredFields"
                class="mt-3 flex flex-wrap gap-2"
              >
                <span
                  v-for="field in requiredFieldSummary.requiredFields"
                  :key="field.id"
                  class="rounded-full border px-3 py-1.5 text-xs font-medium"
                  :class="requiredFieldMissingIds.has(field.id)
                    ? 'border-[#f2d1ac] bg-white text-[#8a5a24]'
                    : 'border-[#d7e7ff] bg-white text-[#2e6bd9]'"
                >
                  {{ requiredFieldMissingIds.has(field.id) ? `Нужно: ${field.title}` : `Готово: ${field.title}` }}
                </span>
              </div>
            </section>

            <section
              v-if="showsTaskDefaultResponsible"
              class="mb-5 rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4"
            >
              <div class="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Исполнитель по умолчанию</div>
              <div class="mb-3 text-sm text-[#5f7285]">
                Если в файле нет колонки `RESPONSIBLE_ID` или в строке значение пустое, для задачи будет использован выбранный пользователь Bitrix24.
              </div>
              <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr),auto]">
                <B24Select
                  :model-value="taskDefaultResponsibleId"
                  class="w-full"
                  size="lg"
                  placeholder="Выберите исполнителя по умолчанию"
                  :items="taskDefaultUserOptions"
                  @update:model-value="taskDefaultResponsibleId = String($event || '')"
                />
                <div class="rounded-[14px] border border-white/70 bg-white/85 px-4 py-3 text-sm text-[#5f7285]">
                  {{ taskDefaultResponsibleId
                    ? 'Default executor выбран и может заменить пустое значение в строке.'
                    : 'Если не хотите маппить RESPONSIBLE_ID из файла, выберите исполнителя здесь.' }}
                </div>
              </div>
            </section>

            <section
              v-if="showsTaskDefaultCreator"
              class="mb-5 rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4"
            >
              <div class="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Постановщик по умолчанию</div>
              <div class="mb-3 text-sm text-[#5f7285]">
                Если в файле нет колонки `CREATED_BY` или в строке значение пустое, для задачи будет использован выбранный постановщик Bitrix24.
              </div>
              <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr),auto]">
                <B24Select
                  :model-value="taskDefaultCreatorId"
                  class="w-full"
                  size="lg"
                  placeholder="Выберите постановщика по умолчанию"
                  :items="taskDefaultUserOptions"
                  @update:model-value="taskDefaultCreatorId = String($event || '')"
                />
                <div class="rounded-[14px] border border-white/70 bg-white/85 px-4 py-3 text-sm text-[#5f7285]">
                  {{ taskDefaultCreatorId
                    ? 'Постановщик по умолчанию выбран и может заменить пустое значение в строке.'
                    : 'Если не хотите маппить CREATED_BY из файла, выберите постановщика здесь.' }}
                </div>
              </div>
            </section>

            <section
              v-if="showsTaskCommentDefaultAuthor"
              class="mb-5 rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4"
            >
              <div class="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Пользователь по умолчанию</div>
              <div class="mb-3 text-sm text-[#5f7285]">
                Если в файле нет колонки `AUTHOR_ID` или в строке значение пустое, комментарий будет отправлен от выбранного пользователя Bitrix24.
              </div>
              <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr),auto]">
                <B24Select
                  :model-value="taskDefaultCommentAuthorId"
                  class="w-full"
                  size="lg"
                  placeholder="Выберите пользователя по умолчанию"
                  :items="taskDefaultUserOptions"
                  @update:model-value="taskDefaultCommentAuthorId = String($event || '')"
                />
                <div class="rounded-[14px] border border-white/70 bg-white/85 px-4 py-3 text-sm text-[#5f7285]">
                  {{ taskDefaultCommentAuthorId
                    ? 'Пользователь по умолчанию выбран и подставится, если AUTHOR_ID пустой.'
                    : 'Если не хотите маппить AUTHOR_ID из файла, выберите пользователя здесь.' }}
                </div>
              </div>
            </section>

            <div
              class="mb-5 grid gap-4"
              :class="showsAdvancedImportTools ? 'xl:grid-cols-2' : 'xl:grid-cols-1'"
            >
              <section
                v-if="showsAdvancedImportTools"
                class="rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4"
              >
                <div class="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Правила сопоставления</div>
                    <div class="mt-1 text-sm text-[#5f7285]">
                      Сохраняйте удачные соответствия заголовков, чтобы автоподбор в следующих импортах срабатывал точнее.
                    </div>
                  </div>
                  <div class="rounded-full border border-[#d7e7ff] bg-white px-3 py-1 text-xs font-semibold text-[#2e6bd9]">
                    {{ importAliasRules.length }}
                  </div>
                </div>

                <div v-if="importAliasRules.length" class="flex flex-wrap gap-2">
                  <div
                    v-for="rule in importAliasRules"
                    :key="String(rule.id || `${rule.source_label}:${rule.target_field_id}`)"
                    class="rounded-full border border-[#d7e7ff] bg-white px-3 py-1.5 text-xs font-medium text-[#314256]"
                  >
                    {{ String(rule.source_label || '—') }} → {{ String(rule.target_field_title || rule.target_field_id || '—') }}
                  </div>
                </div>
                <div v-else class="rounded-[14px] border border-dashed border-[#d7e7ff] bg-white/80 px-4 py-3 text-sm text-[#6f8194]">
                  Пока нет сохранённых правил. Используйте кнопку «Запомнить правило» у нужной строки.
                </div>
              </section>

              <section
                class="rounded-[20px] border p-4"
                :class="hasBlockingPreflightIssues
                  ? 'border-[#ffc89a] bg-[#fff8ef]'
                  : (mappingPreflightIssues.length
                    ? 'border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)]'
                    : 'border-[#dcefe1] bg-[#f4fbf6]')"
              >
                <div class="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Проверка перед запуском</div>
                    <div class="mt-1 text-sm text-[#5f7285]">
                      Здесь видно, что остановит проверку данных и какие места стоит уточнить заранее.
                    </div>
                  </div>
                  <div class="flex flex-wrap gap-2 text-xs font-semibold">
                    <span
                      class="rounded-full px-2.5 py-1"
                      :class="hasBlockingPreflightIssues ? 'bg-[#fff0e0] text-[#a96017]' : 'bg-white text-[#6f8194]'"
                    >
                      Ошибки: {{ Number(mappingPreflight.blocking_issue_count || 0) }}
                    </span>
                    <span class="rounded-full bg-white px-2.5 py-1 text-[#2e6bd9]">
                      Предупреждения: {{ Number(mappingPreflight.warning_count || 0) }}
                    </span>
                  </div>
                </div>

                <div v-if="mappingPreflightIssues.length" class="space-y-2">
                  <div
                    v-for="(issue, issueIndex) in mappingPreflightIssues"
                    :key="`${String(issue.code || 'issue')}:${issueIndex}`"
                    class="rounded-[14px] border bg-white/85 px-4 py-3"
                    :class="String(issue.severity || '').trim().toLowerCase() === 'error'
                      ? 'border-[#f2d1ac]'
                      : 'border-[#d7e7ff]'"
                  >
                    <div class="mb-1 flex items-center gap-2">
                      <span
                        class="rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em]"
                        :class="String(issue.severity || '').trim().toLowerCase() === 'error'
                          ? 'bg-[#fff0e0] text-[#a96017]'
                          : 'bg-[#edf5ff] text-[#2e6bd9]'"
                      >
                        {{ buildPreflightSeverityLabel(String(issue.severity || '')) }}
                      </span>
                      <span class="text-xs text-[#8ea0b2]">{{ buildPreflightIssueMeta(issue) }}</span>
                    </div>
                    <div class="whitespace-pre-wrap break-words text-sm text-[#314256]">
                      {{ getTextBlockDisplayValue(makeCollapsibleKey('preflight-issue', `${String(issue.code || 'issue')}:${issueIndex}`), buildPreflightIssueDescription(issue)) }}
                    </div>
                    <button
                      v-if="isTextCollapsible(buildPreflightIssueDescription(issue))"
                      type="button"
                      class="mt-2 text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                      @click="toggleTextBlock(makeCollapsibleKey('preflight-issue', `${String(issue.code || 'issue')}:${issueIndex}`))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('preflight-issue', `${String(issue.code || 'issue')}:${issueIndex}`)) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                </div>
                <div v-else class="rounded-[14px] border border-[#dcefe1] bg-white/85 px-4 py-3 text-sm text-[#2d7a4b]">
                  Блокирующих проблем и предупреждений на текущем сопоставлении не найдено.
                </div>
              </section>
            </div>

            <div v-if="showsAdvancedImportTools" class="mb-5 grid gap-4 xl:grid-cols-2">
              <section class="rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4">
                <div class="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Сохранить шаблон</div>
                <div class="flex flex-col gap-3 lg:flex-row">
                  <B24Input
                    v-model="templateNameInput"
                    class="w-full"
                    size="lg"
                    placeholder="Например, Контакты из Excel"
                  />
                  <B24Button
                    label="Сохранить шаблон"
                    color="air-primary"
                    size="lg"
                    :loading="busyAction === 'template-save'"
                    :disabled="!canSaveTemplate"
                    @click="saveTemplate"
                  />
                </div>
              </section>

              <section class="rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4">
                <div class="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Применить шаблон</div>
                <div class="flex flex-col gap-3 lg:flex-row">
                  <B24Select
                    :model-value="selectedTemplateId"
                    class="w-full"
                    size="lg"
                    placeholder="Выберите шаблон"
                    :items="templateItems"
                    @update:model-value="selectedTemplateId = String($event || '')"
                  />
                  <B24Button
                    label="Применить"
                    color="air-secondary-accent-2"
                    size="lg"
                    :loading="busyAction === 'template-apply'"
                    :disabled="!canApplyTemplate"
                    @click="applyTemplate"
                  />
                </div>
              </section>
            </div>

            <section
              v-if="valueMappingRows.length"
              class="mb-5 rounded-[20px] border bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4"
              :class="valueMappingStatus.hasUnmappedValues ? 'border-[#ffc89a]' : 'border-[#dce7f7]'"
            >
              <!-- Заголовок-кнопка -->
              <button
                class="flex w-full items-center justify-between gap-3 text-left"
                @click="valueMappingExpanded = !valueMappingExpanded"
              >
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-sm font-semibold text-[#314256]">Сопоставление значений</span>
                  <span
                    class="rounded-full px-2.5 py-0.5 text-xs font-medium"
                    :class="valueMappingStatus.hasUnmappedValues
                      ? 'bg-[#fff0e0] text-[#a96017]'
                      : 'bg-[#e6f4ea] text-[#2d7a3a]'"
                  >
                    {{ valueMappingStatus.hasUnmappedValues
                      ? `${valueMappingStatus.unmappedValues} из ${valueMappingStatus.totalValues} не выбрано`
                      : `Всё готово · ${valueMappingStatus.totalValues} значений` }}
                  </span>
                </div>
                <svg
                  class="shrink-0 text-[#8ea0b2] transition-transform duration-200"
                  :class="valueMappingExpanded ? 'rotate-180' : ''"
                  width="18" height="18" viewBox="0 0 20 20" fill="none"
                >
                  <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>

              <!-- Подсказка (всегда видна) -->
              <p class="mt-2 text-xs text-[#6f8194]">
                {{ valueMappingStatus.hasUnmappedValues
                  ? 'Система нашла значения из вашего файла, которые нужно привязать к вариантам Bitrix24. Для каждого — выберите соответствующий вариант из списка справа.'
                  : 'Все значения из файла успешно сопоставлены с вариантами Bitrix24. Можно продолжить.' }}
              </p>

              <!-- Сворачиваемый список -->
              <div v-if="valueMappingExpanded" class="mt-4 space-y-3">
                <div
                  v-for="row in valueMappingRows"
                  :key="row.key"
                  class="grid gap-3 rounded-[16px] border border-white/70 bg-white/85 px-4 py-4 lg:grid-cols-[minmax(180px,1fr),minmax(220px,1fr),minmax(260px,1.2fr)]"
                  :class="!row.selectedTargetValue ? 'border-l-2 border-l-[#ffa05a]' : ''"
                >
                  <div>
                    <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Поле Bitrix24</div>
                    <div class="mt-1 font-medium text-[#314256]">{{ row.targetFieldTitle }}</div>
                    <div class="mt-0.5 text-xs text-[#9aa9b8]">{{ row.targetFieldId }}</div>
                  </div>

                  <div>
                    <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Значение из файла</div>
                    <div class="mt-1 font-mono text-sm font-medium text-[#314256]">{{ row.sourceValue }}</div>
                    <div v-if="!row.selectedTargetValue" class="mt-0.5 text-xs text-[#c07020]">Не сопоставлено — выберите вариант →</div>
                    <div v-else class="mt-0.5 text-xs text-[#3a8a48]">Сопоставлено</div>
                  </div>

                  <div>
                    <div class="mb-2 text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Вариант в Bitrix24</div>
                    <B24Select
                      :model-value="row.selectedTargetValue || '__none__'"
                      class="w-full"
                      size="md"
                      placeholder="Выберите вариант..."
                      :items="[{ value: '__none__', label: '— Не выбрано —' }, ...row.options]"
                      @update:model-value="updateValueMappingSelection(row.targetFieldId, row.sourceValue, $event === '__none__' ? '' : String($event || ''))"
                    />
                  </div>
                </div>
              </div>
            </section>

            <div class="overflow-hidden rounded-[20px] border border-[#dfe5eb] bg-white">
              <!-- Пустое состояние -->
              <div
                v-if="!mappingRows.length && !(busyAction === 'start' || busyAction === 'structure' || busyAction === 'mapping' || busyAction === 'template-apply')"
                class="px-6 py-10 text-center text-sm text-[#8ea0b2]"
              >
                После загрузки файла здесь появится список колонок для сопоставления.
              </div>

              <!-- Загрузка -->
              <div
                v-else-if="busyAction === 'start' || busyAction === 'structure' || busyAction === 'mapping' || busyAction === 'template-apply'"
                class="px-6 py-10 text-center text-sm text-[#8ea0b2]"
              >
                Загрузка...
              </div>

              <!-- Таблица с drag-and-drop -->
              <table
                v-else
                class="w-full border-collapse text-sm"
              >
                <thead>
                  <tr class="border-b border-[#dfe5eb] bg-[#f8fafc]">
                    <th class="w-8 px-3 py-3" />
                    <th class="w-[100px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[#8ea0b2]">
                      Колонка
                    </th>
                    <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[#8ea0b2]">
                      Колонка файла
                    </th>
                    <th class="min-w-[300px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[#8ea0b2]">
                      Поле Bitrix24
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, index) in mappingRows"
                    :key="row.key"
                    draggable="true"
                    class="border-b border-[#f0f4f8] transition-colors last:border-0"
                    :class="{
                      'bg-[#f0f7ff] border-l-2 border-l-[#3b82f6]': mappingDragOverIndex === index && mappingDragSourceIndex !== index,
                      'opacity-40': mappingDragSourceIndex === index,
                      'bg-white hover:bg-[#fafcff]': mappingDragOverIndex !== index && mappingDragSourceIndex !== index,
                    }"
                    @dragstart="onMappingDragStart(index, $event)"
                    @dragover="onMappingDragOver(index, $event)"
                    @dragleave="onMappingDragLeave"
                    @drop="onMappingDrop(index, $event)"
                    @dragend="onMappingDragEnd"
                  >
                    <!-- Drag handle -->
                    <td class="w-8 cursor-grab px-3 py-3 text-[#c0ccd8] active:cursor-grabbing">
                      <svg width="12" height="18" viewBox="0 0 12 18" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="3" cy="3" r="1.5" />
                        <circle cx="9" cy="3" r="1.5" />
                        <circle cx="3" cy="9" r="1.5" />
                        <circle cx="9" cy="9" r="1.5" />
                        <circle cx="3" cy="15" r="1.5" />
                        <circle cx="9" cy="15" r="1.5" />
                      </svg>
                    </td>
                    <!-- Буква колонки -->
                    <td class="px-4 py-3 font-medium text-[#8ea0b2]">
                      {{ row.column }}
                    </td>
                    <!-- Название колонки из файла -->
                    <td class="px-4 py-3 text-[#314256]">
                      {{ row.sourceHeader || '—' }}
                    </td>
                    <!-- Поле Bitrix24 (select + badges) -->
                    <td class="px-4 py-3">
                      <div class="min-w-[260px]">
                        <B24SelectMenu
                          :model-value="resolveMappingSelectValue(row.targetFieldId)"
                          class="w-full"
                          size="md"
                          placeholder="Не импортировать"
                          :items="mappingFieldItems"
                          value-key="value"
                          :filter-fields="['label', 'description']"
                          :search-input="{ placeholder: 'Поиск полей...' }"
                          @update:model-value="updateMappingFieldSelection(row, String($event || ''))"
                        />

                        <!-- Тип данных колонки (override) -->
                        <div v-if="row.targetFieldId && showsAdvancedImportTools" class="mt-2">
                          <B24Select
                            :model-value="row.columnType || 'auto'"
                            size="xs"
                            :items="[
                              { value: 'auto', label: 'Авто (по полю Bitrix24)' },
                              { value: 'string', label: 'Текст' },
                              { value: 'integer', label: 'Число (целое)' },
                              { value: 'double', label: 'Число (дробное)' },
                              { value: 'date', label: 'Дата' },
                              { value: 'datetime', label: 'Дата и время' },
                              { value: 'boolean', label: 'Логическое (Да/Нет)' },
                            ]"
                            @update:model-value="row.columnType = $event === 'auto' ? '' : String($event || '')"
                          />
                        </div>

                        <div
                          v-if="row.targetFieldId"
                          class="mt-2 flex flex-wrap gap-2"
                        >
                          <span
                            v-if="showsAdvancedImportTools && row.autoMatchType"
                            class="rounded-full border border-[#d9e6f5] bg-[#f6f9fd] px-2.5 py-1 text-xs font-medium text-[#58708b]"
                          >
                            {{ row.autoMatchLabel || 'Автоподбор' }}
                          </span>
                          <span class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-2.5 py-1 text-xs font-medium text-[#2e6bd9]">
                            {{ row.targetFieldTypeLabel || 'Поле' }}
                          </span>
                          <span
                            v-if="row.targetFieldRequired"
                            class="rounded-full border border-[#f2d1ac] bg-[#fff8ef] px-2.5 py-1 text-xs font-medium text-[#9a6432]"
                          >
                            Обязательное
                          </span>
                          <span
                            v-if="row.targetFieldIsCustom"
                            class="rounded-full border border-[#dcefe1] bg-[#f1fbf4] px-2.5 py-1 text-xs font-medium text-[#2d7a4b]"
                          >
                            Кастомное
                          </span>
                          <span
                            v-if="row.targetFieldIsMultiple"
                            class="rounded-full border border-[#efe3cf] bg-[#fff8ef] px-2.5 py-1 text-xs font-medium text-[#9a6432]"
                          >
                            Множественное
                          </span>
                          <span
                            v-if="showsAdvancedImportTools && row.autoMatchReasonLabel"
                            class="rounded-full border border-[#d7e7ff] bg-white px-2.5 py-1 text-xs font-medium text-[#58708b]"
                          >
                            {{ row.autoMatchReasonLabel }}
                          </span>
                        </div>

                        <div
                          v-if="showsAdvancedImportTools && row.targetFieldGuidanceHints?.length"
                          class="mt-2 space-y-1 text-xs text-[#6f8194]"
                        >
                          <div
                            v-for="hint in row.targetFieldGuidanceHints"
                            :key="hint"
                          >
                            {{ hint }}
                          </div>
                        </div>

                        <div
                          v-if="showsAdvancedImportTools && row.candidateSuggestions?.length"
                          class="mt-3 rounded-[14px] border border-[#dce7f7] bg-white/85 px-3 py-3"
                        >
                          <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8ea0b2]">
                            Возможные поля
                          </div>
                          <div class="flex flex-wrap gap-2">
                            <button
                              v-for="suggestion in row.candidateSuggestions"
                              :key="`${row.key}:${suggestion.targetFieldId}`"
                              type="button"
                              class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                              :class="row.targetFieldId === suggestion.targetFieldId
                                ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                                : 'border-[#d7e7ff] bg-white text-[#58708b] hover:border-[#2e6bd9] hover:text-[#2e6bd9]'"
                              @click="applyCandidateSuggestion(row, suggestion)"
                            >
                              {{ suggestion.targetFieldTitle }}
                              <span v-if="suggestion.matchReasonLabel || suggestion.matchLabel">
                                · {{ suggestion.matchReasonLabel || suggestion.matchLabel }}
                              </span>
                            </button>
                          </div>
                        </div>

                        <div
                          v-if="showsAdvancedImportTools && row.targetFieldId && row.sourceHeader && importerPermissionState.canManageTemplates"
                          class="mt-3 flex flex-wrap items-center gap-2"
                        >
                          <B24Button
                            :label="hasImportAliasRule(row) ? 'Правило сохранено' : 'Запомнить правило'"
                            color="air-secondary-accent-2"
                            size="sm"
                            :loading="busyAction === 'alias-rule'"
                            :disabled="busyAction === 'alias-rule' || hasImportAliasRule(row)"
                            @click="saveImportAliasRule(row)"
                          />
                          <span v-if="hasImportAliasRule(row)" class="text-xs text-[#6f8194]">
                            Это соответствие уже будет учитываться при следующем автоподборе.
                          </span>
                        </div>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-if="currentStep === 5" class="space-y-6">
            <section class="rounded-[24px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-5">
              <div class="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 5</div>
                  <h2 class="mt-1 text-xl font-semibold text-[#314256]">Обработка дублей</h2>
                </div>

                <div class="flex flex-wrap gap-3">
                  <B24Button
                    label="Назад"
                    color="air-primary"
                    size="lg"
                    :disabled="!canGoBack"
                    @click="goBack"
                  />
                  <B24Button
                    v-if="isDedupApplicable"
                    label="Пропустить шаг"
                    color="air-tertiary"
                    size="lg"
                    :disabled="['dedup', 'validation'].includes(String(busyAction || ''))"
                    @click="skipDedupStep"
                  />
                  <B24Button
                    v-if="isDedupApplicable"
                    label="Сохранить правила дублей"
                    color="air-secondary-accent-2"
                    size="lg"
                    :loading="busyAction === 'dedup'"
                    :disabled="!canSaveDedup"
                    @click="saveDedupSettings"
                  />
                  <B24Button
                    v-else
                    label="Проверить данные"
                    color="air-primary"
                    size="lg"
                    :loading="busyAction === 'validation'"
                    :disabled="!canRunValidation"
                    @click="runValidation"
                  />
                </div>
              </div>

              <div
                v-if="['dedup', 'validation'].includes(String(busyAction || ''))"
                class="mb-5 rounded-[18px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-4"
              >
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold text-[#2e6bd9]">{{ dedupProgressTitle }}</div>
                    <div class="mt-1 text-sm text-[#5f7285]">{{ dedupProgressDescription }}</div>
                  </div>
                  <div class="shrink-0 rounded-full border border-[#d7e7ff] bg-white px-3 py-1 text-xs font-semibold text-[#2e6bd9]">
                    {{ preview?.total_rows || session?.total_rows || 0 }} строк
                  </div>
                </div>
                <div class="mt-3 h-2 w-full overflow-hidden rounded-full bg-[#dde8f8]">
                  <div class="h-2 w-1/3 rounded-full bg-[#2e6bd9] animate-pulse" />
                </div>
              </div>

              <!-- Дедупликация не применима для задач и файлового импорта -->
              <div v-if="!isDedupApplicable" class="rounded-[16px] border border-[#e5ebf2] bg-white px-5 py-5">
                <div class="flex items-start gap-3">
                  <div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#f0f4fa] text-[#8ea0b2]">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  </div>
                  <div>
                    <div class="text-sm font-semibold text-[#314256]">Дедупликация не применяется</div>
                    <div class="mt-1 text-sm text-[#6f8194]">
                      Для данного типа импорта ({{ currentScenarioSummary.selectedLabel }}) поиск дублей не поддерживается — каждая строка файла обрабатывается независимо. Нажмите «Проверить данные», чтобы перейти дальше.
                    </div>
                  </div>
                </div>
              </div>

              <!-- Стандартный блок дедупликации для CRM и HR -->
              <template v-if="isDedupApplicable">
                <div
                  v-if="unmappedValueSummary.hasUnmappedValues"
                  class="mb-5 rounded-[16px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-3 text-sm text-[#8f5b18]"
                >
                  <div class="font-semibold text-[#a96017]">
                    Перед проверкой нужно сопоставить значений: {{ unmappedValueSummary.totalValues }}
                  </div>
                  <div class="mt-1 text-xs text-[#a9783d]">
                    Пока это не сделано, шаг проверки недоступен.
                  </div>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <span
                      v-for="group in unmappedValueSummary.groups"
                      :key="group.fieldId"
                      class="rounded-full border border-[#f2d1ac] bg-white px-3 py-1.5 text-xs font-medium text-[#8a5a24]"
                    >
                      {{ `${group.fieldTitle}: ${group.count}` }}
                    </span>
                  </div>
                </div>

                <div v-if="isLinkedImportEntityType(entityType)" class="space-y-4">
                  <div class="text-sm text-[#5f7285]">
                    Для связанного импорта правила дублей настраиваются отдельно по каждой сущности. Например, компанию можно обновлять по названию, а контакт создавать заново или спрашивать решение отдельно.
                  </div>

                  <div
                    v-for="group in linkedDedupEntityGroups"
                    :key="group.id"
                    class="rounded-[18px] border border-[#e5ebf2] bg-white px-4 py-4"
                  >
                    <div class="mb-3">
                      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Правила для сущности</div>
                      <div class="mt-1 text-base font-semibold text-[#314256]">{{ group.label }}</div>
                    </div>

                    <div class="grid gap-4 lg:grid-cols-[280px,1fr]">
                      <B24Select
                        :model-value="linkedDedupSettings[group.id]?.strategy || 'create'"
                        class="w-full"
                        size="lg"
                        :items="dedupStrategyItems"
                        @update:model-value="updateLinkedDedupStrategySelection(group.id, String($event || 'create'))"
                      />

                      <div class="rounded-[16px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                        <div class="font-medium text-[#314256]">Ключи поиска дубля</div>
                        <div class="mt-1 text-xs text-[#7f92a7]">
                          Используются только поля {{ group.label.toLowerCase() }} из текущего маппинга.
                        </div>

                        <div v-if="(linkedDedupFieldOptions[group.id] || []).length" class="mt-3 flex flex-wrap gap-3">
                          <button
                            v-for="item in linkedDedupFieldOptions[group.id] || []"
                            :key="`${group.id}:${item.id}`"
                            type="button"
                            class="rounded-full border px-3 py-2 text-sm font-medium transition"
                            :class="(linkedDedupSettings[group.id]?.fields || []).includes(item.id) && (linkedDedupSettings[group.id]?.strategy || 'create') !== 'create'
                              ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                              : 'border-[#d9e2ec] bg-white text-[#516478]'"
                            :disabled="(linkedDedupSettings[group.id]?.strategy || 'create') === 'create'"
                            @click="toggleLinkedDedupField(group.id, item.id)"
                          >
                            {{ item.label }}
                          </button>
                        </div>

                        <div v-else class="mt-3 text-sm text-[#7f92a7]">
                          Сначала сопоставьте поля {{ group.label.toLowerCase() }} на шаге маппинга.
                        </div>

                        <div
                          v-if="(linkedDedupSettings[group.id]?.strategy || 'create') !== 'create' && (linkedDedupSettings[group.id]?.fields || []).length >= 2"
                          class="mt-4 flex items-center gap-3"
                        >
                          <span class="text-xs text-[#7f92a7]">Режим совпадения:</span>
                          <div class="flex gap-1 rounded-[10px] border border-[#e5ebf2] bg-[#f4f7fa] p-1">
                            <button
                              type="button"
                              class="rounded-[8px] px-3 py-1 text-xs font-medium transition"
                              :class="(linkedDedupSettings[group.id]?.condition || 'any') === 'any' ? 'bg-white text-[#2e6bd9] shadow-sm' : 'text-[#7f92a7] hover:text-[#314256]'"
                              @click="updateLinkedDedupCondition(group.id, 'any')"
                            >
                              Любое поле (OR)
                            </button>
                            <button
                              type="button"
                              class="rounded-[8px] px-3 py-1 text-xs font-medium transition"
                              :class="(linkedDedupSettings[group.id]?.condition || 'any') === 'all' ? 'bg-white text-[#2e6bd9] shadow-sm' : 'text-[#7f92a7] hover:text-[#314256]'"
                              @click="updateLinkedDedupCondition(group.id, 'all')"
                            >
                              Все поля (AND)
                            </button>
                          </div>
                        </div>

                        <div
                          v-if="(linkedDedupSettings[group.id]?.strategy || 'create') !== 'create' && (linkedDedupFieldOptions[group.id] || []).length && !(linkedDedupSettings[group.id]?.fields || []).length"
                          class="mt-3 rounded-[10px] border border-[#ffd5b3] bg-[#fff7ef] px-3 py-2 text-xs text-[#9a5a10]"
                        >
                          Выберите хотя бы один ключ поиска для сущности «{{ group.label }}».
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-else-if="isSimpleImportMode" class="space-y-4">
                  <div class="text-sm text-[#5f7285]">
                    В простом режиме дубли настраиваются без дополнительных опций: выбираете действие, а ключи поиска берутся автоматически из уже сопоставленных полей.
                  </div>

                  <div class="grid gap-4 lg:grid-cols-[280px,1fr]">
                    <B24Select
                      :model-value="dedupStrategy"
                      class="w-full"
                      size="lg"
                      :items="dedupStrategyItems"
                      @update:model-value="updateDedupStrategySelection(String($event || 'create'))"
                    />

                    <div class="rounded-[16px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                      <div class="font-medium text-[#314256]">Проверка дублей</div>
                      <div class="mt-1 text-xs text-[#7f92a7]">
                        Простая проверка использует только базовые поля из маппинга: Email, Телефон и Название.
                      </div>

                      <div
                        v-if="dedupStrategy !== 'create' && simpleDedupFieldLabels.length"
                        class="mt-3 flex flex-wrap gap-2"
                      >
                        <span
                          v-for="label in simpleDedupFieldLabels"
                          :key="label"
                          class="rounded-full border border-[#d7e7ff] bg-[#edf5ff] px-3 py-1.5 text-xs font-medium text-[#2e6bd9]"
                        >
                          {{ label }}
                        </span>
                      </div>

                      <div
                        v-else-if="simpleDedupPreset.available"
                        class="mt-3 rounded-[10px] border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-2 text-xs text-[#5c7592]"
                      >
                        Если хотите искать дубли, выберите действие «Обновлять» или «Пропускать дубль».
                      </div>

                      <div
                        v-else
                        class="mt-3 rounded-[10px] border border-[#ffd5b3] bg-[#fff7ef] px-3 py-2 text-xs text-[#9a5a10]"
                      >
                        Чтобы искать дубли в простом режиме, сопоставьте хотя бы одно поле EMAIL, PHONE или TITLE.
                      </div>

                      <div
                        v-if="dedupStrategy !== 'create' && simpleDedupFieldLabels.length"
                        class="mt-3 text-xs text-[#7f92a7]"
                      >
                        Совпадение ищется по любому из этих ключей. Для сложных сценариев переключитесь в расширенный режим.
                      </div>
                    </div>
                  </div>
                </div>

                <template v-else>
                  <div class="mb-5 text-sm text-[#5f7285]">
                    Отдельно задайте, как искать совпадения и что делать с найденными дублями, чтобы шаг соответствия полей оставался чистым и понятным.
                  </div>

                  <div class="grid gap-4 lg:grid-cols-[280px,1fr]">
                    <B24Select
                      :model-value="dedupStrategy"
                      class="w-full"
                      size="lg"
                      :items="dedupStrategyItems"
                      @update:model-value="updateDedupStrategySelection(String($event || 'create'))"
                    />

                    <div class="rounded-[16px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                      <div class="font-medium text-[#314256]">Ключи поиска дубля</div>
                      <div class="mt-1 text-xs text-[#7f92a7]">
                        Используются сопоставленные поля текущего импорта. Если выбрано несколько ключей, дубль ищется по их совместному совпадению.
                      </div>

                      <div v-if="dedupFieldOptions.length" class="mt-3 flex flex-wrap gap-3">
                        <button
                          v-for="item in dedupFieldOptions"
                          :key="item.id"
                          type="button"
                          class="rounded-full border px-3 py-2 text-sm font-medium transition"
                          :class="dedupFields.includes(item.id) && dedupStrategy !== 'create'
                            ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                            : 'border-[#d9e2ec] bg-white text-[#516478]'"
                          :disabled="dedupStrategy === 'create'"
                          @click="toggleDedupField(item.id)"
                        >
                          {{ item.label }}
                        </button>
                      </div>

                      <div v-else class="mt-3 text-sm text-[#7f92a7]">
                        Сначала сопоставьте одно из полей EMAIL, PHONE или TITLE на шаге маппинга.
                      </div>

                      <div
                        v-if="dedupStrategy !== 'create' && dedupFields.length >= 2"
                        class="mt-4 flex items-center gap-3"
                      >
                        <span class="text-xs text-[#7f92a7]">Режим совпадения:</span>
                        <div class="flex gap-1 rounded-[10px] border border-[#e5ebf2] bg-[#f4f7fa] p-1">
                          <button
                            type="button"
                            class="rounded-[8px] px-3 py-1 text-xs font-medium transition"
                            :class="dedupCondition === 'any' ? 'bg-white text-[#2e6bd9] shadow-sm' : 'text-[#7f92a7] hover:text-[#314256]'"
                            @click="dedupCondition = 'any'"
                          >
                            Любое поле (OR)
                          </button>
                          <button
                            type="button"
                            class="rounded-[8px] px-3 py-1 text-xs font-medium transition"
                            :class="dedupCondition === 'all' ? 'bg-white text-[#2e6bd9] shadow-sm' : 'text-[#7f92a7] hover:text-[#314256]'"
                            @click="dedupCondition = 'all'"
                          >
                            Все поля (AND)
                          </button>
                        </div>
                        <span class="text-xs text-[#7f92a7]">
                          {{ dedupCondition === 'all' ? 'Дубль найден только если совпали все выбранные поля' : 'Дубль найден если совпало хотя бы одно поле' }}
                        </span>
                      </div>

                      <div
                        v-if="dedupStrategy !== 'create' && dedupFieldOptions.length && dedupFields.length === 0"
                        class="mt-3 rounded-[10px] border border-[#ffd5b3] bg-[#fff7ef] px-3 py-2 text-xs text-[#9a5a10]"
                      >
                        Выберите хотя бы один ключ поиска — без него дубли не будут найдены и все строки будут созданы заново.
                      </div>
                    </div>
                  </div>
                </template>

              </template>
            </section>
          </section>

          <section v-if="currentStep === 6" class="space-y-6">
            <section class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-4 md:p-5">
              <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 6</div>
                  <h2 class="mt-1 text-lg font-semibold text-[#314256]">Тестовый импорт и запуск</h2>
                </div>

                <div class="flex flex-wrap gap-3">
                  <B24Button
                    label="Назад"
                    color="air-primary"
                    size="lg"
                    :disabled="!canGoBack"
                    @click="goBack"
                  />
                  <B24Button
                    label="Тестовый импорт"
                    color="air-secondary-accent-2"
                    size="lg"
                    :loading="busyAction === 'sample-preview'"
                    :disabled="!canRunValidation || busyAction === 'sample-preview'"
                    @click="runSamplePreview"
                  />
                  <B24Button
                    label="Запустить импорт"
                    color="air-primary"
                    size="lg"
                    :loading="busyAction === 'run'"
                    :disabled="!canRunImport || busyAction === 'sample-preview' || hasUnresolvedPendingDedupDecisions"
                    @click="runImport"
                  />
                  <B24Button
                    v-if="busyAction === 'sample-preview' || cancelRequested"
                    label="Остановить тестовый импорт"
                    color="air-tertiary"
                    size="lg"
                    :loading="cancelRequested"
                    :disabled="!canCancelActiveImport"
                    @click="cancelActiveImport"
                  />
                  <B24Button
                    v-if="busyAction === 'run' || cancelRequested"
                    label="Остановить импорт"
                    color="air-tertiary"
                    size="lg"
                    :loading="cancelRequested"
                    :disabled="!canCancelActiveImport"
                    @click="cancelActiveImport"
                  />
                </div>
              </div>

              <div
                v-if="showsDedupProgress || showsSessionProgress || importExecutionStage === 'duplicate-decisions'"
                class="mb-4 rounded-[18px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-4"
              >
                <div class="mb-2 flex items-center justify-between text-sm">
                  <span class="font-semibold text-[#2e6bd9]">
                    {{ executionProgressTitle }}
                  </span>
                  <span class="text-[#6f8194]">
                    {{ executionProgressCounterLabel }}
                  </span>
                </div>
                <div class="mb-3 h-2 w-full overflow-hidden rounded-full bg-[#dde8f8]">
                  <div
                    class="h-2 rounded-full bg-[#2e6bd9] transition-all duration-500"
                    :style="{ width: executionProgressPercent + '%' }"
                  />
                </div>
                <div class="flex flex-wrap gap-4 text-sm text-[#5f7285]">
                  <span>Обработано: <strong class="text-[#314256]">{{ session?.processed_rows ?? 0 }}</strong></span>
                  <span>{{ showsSessionProgress ? 'Успешно' : 'К записи' }}: <strong class="text-[#1a7a4a]">{{ session?.successful_rows ?? 0 }}</strong></span>
                  <span>{{ showsSessionProgress ? 'Ошибки' : 'Пропущено' }}: <strong class="text-[#c24b53]">{{ session?.failed_rows ?? 0 }}</strong></span>
                </div>
                <div v-if="showsSessionProgress" class="mt-4 grid gap-3 md:grid-cols-2">
                  <div
                    v-for="phase in importExecutionPhaseCards"
                    :key="phase.id"
                    class="rounded-[16px] border px-4 py-3 text-sm"
                    :class="phase.status === 'completed'
                      ? 'border-[#cfe5d8] bg-white text-[#1a7a4a]'
                      : phase.status === 'current'
                        ? 'border-[#d7e7ff] bg-white text-[#2e6bd9]'
                        : 'border-[#e5ebf2] bg-white text-[#6f8194]'"
                  >
                    <div class="font-semibold">{{ phase.label }}</div>
                    <div class="mt-1 text-xs opacity-80">{{ phase.description }}</div>
                  </div>
                </div>
                <div
                  v-if="showsSessionProgress && session?.summary?.import_progress?.pause_info"
                  class="mt-3 flex items-start gap-3 rounded-[12px] border border-[#ffe9b0] bg-[#fffbef] px-4 py-3 text-sm text-[#8a6a00]"
                >
                  <span class="mt-0.5 text-base">⏸</span>
                  <div>
                    <div class="font-semibold">Пауза: ожидаем сброса лимита Bitrix24</div>
                    <div class="mt-0.5 text-[#b38a00]">
                      Импорт автоматически продолжится через ~{{ session.summary.import_progress.pause_info.wait_seconds }} сек.
                    </div>
                  </div>
                </div>
              </div>

              <div class="mb-4 flex flex-wrap items-center gap-3">
                <div
                  class="rounded-full px-4 py-2 text-sm font-semibold"
                  :class="dryRunData
                    ? (dryRunSkippedRows > 0 ? 'border border-[#ffe1c7] bg-[#fff7ef] text-[#c77d2b]' : 'border border-[#d7e7ff] bg-[#f4f9ff] text-[#2e6bd9]')
                    : (validationIssueCount > 0 ? 'border border-[#ffd4d4] bg-[#fff5f5] text-[#c24b53]' : 'border border-[#d7e7ff] bg-[#f4f9ff] text-[#2e6bd9]')"
                >
                  {{ stepSixStatusLabel }}
                </div>
                <div class="text-sm text-[#6f8194]">
                  {{ importExecutionStage === 'duplicate-decisions' ? 'Решения по дублям перед импортом' : (dryRunData ? 'Тестовый импорт' : 'Проверка данных') }}
                </div>
              </div>

              <div class="mb-4 grid gap-4 md:grid-cols-3">
                <div
                  v-for="card in stepSixMetricCards"
                  :key="card.label"
                  class="rounded-[18px] border border-[#e5ebf2] bg-white px-4 py-3 text-sm text-[#5f7285]"
                >
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">{{ card.label }}</div>
                  <div class="mt-1 text-base font-semibold text-[#314256]">{{ card.value }}</div>
                </div>
              </div>

              <div
                v-if="dryRunData && importExecutionStage !== 'duplicate-decisions'"
                class="mb-4 rounded-[18px] border border-[#d7e7ff] bg-[#f8fbff] px-4 py-4 text-sm text-[#5f7285]"
              >
                <div class="font-semibold text-[#314256]">Тестовый импорт проверяет весь файл</div>
                <div class="mt-1">
                  После проверки можно выбрать решения по дублям и отдельно запустить реальный импорт.
                </div>
              </div>

              <div
                v-if="importExecutionStage === 'duplicate-decisions' && requiresPerRowDedupDecision && dryRunData && pendingDecisionRows.length && !busyAction"
                class="mb-4 rounded-[20px] border border-[#dce7f7] bg-white p-4"
              >
                <div class="mb-3 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Решения перед импортом</div>
                    <div class="mt-1 text-sm text-[#5f7285]">
                      Тестовый импорт завершён. Выберите действие для каждого найденного дубля перед реальным импортом.
                    </div>
                    <div
                      v-if="hasUnresolvedPendingDedupDecisions"
                      class="mt-2 text-xs font-semibold text-[#c24b53]"
                    >
                      Импорт не начнётся, пока решение не выбрано для всех найденных дублей.
                    </div>
                    <div
                      v-else
                      class="mt-2 text-xs font-semibold text-[#1a7f3c]"
                    >
                      Все решения выбраны. Теперь можно запускать импорт.
                    </div>
                  </div>
                  <div class="flex flex-wrap gap-2 text-xs">
                    <button
                      type="button"
                      class="rounded-full border border-[#d7e7ff] bg-white px-3 py-1.5 font-medium text-[#2e6bd9] transition hover:bg-[#edf5ff]"
                      @click="applyBulkPerRowDedupDecision('create')"
                    >
                      Всё создать
                    </button>
                    <button
                      type="button"
                      class="rounded-full border border-[#d4edda] bg-white px-3 py-1.5 font-medium text-[#1a7f3c] transition hover:bg-[#edf7f0]"
                      @click="applyBulkPerRowDedupDecision('update')"
                    >
                      Всё обновить
                    </button>
                    <button
                      type="button"
                      class="rounded-full border border-[#e5e7eb] bg-white px-3 py-1.5 font-medium text-[#6b7280] transition hover:bg-[#f3f4f6]"
                      @click="applyBulkPerRowDedupDecision('skip')"
                      >
                        Всё пропустить
                      </button>
                  </div>
                </div>

                <div class="overflow-hidden rounded-[16px] border border-[#dce7f7] bg-white">
                  <table class="w-full text-sm">
                    <thead>
                      <tr class="border-b border-[#e8eef5] bg-[#f5f8fc]">
                        <th class="px-4 py-2.5 text-left font-semibold text-[#5f7285]">Строка</th>
                        <th class="px-4 py-2.5 text-left font-semibold text-[#5f7285]">ID дубля</th>
                        <th class="px-4 py-2.5 text-left font-semibold text-[#5f7285]">Совпадение по</th>
                        <th class="px-4 py-2.5 text-left font-semibold text-[#5f7285]">Действие</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="row in pendingDecisionRows"
                        :key="row.row_number"
                        class="border-b border-[#eef3f8] last:border-b-0"
                      >
                        <td class="px-4 py-3 font-medium text-[#314256]">#{{ row.row_number }}</td>
                        <td class="px-4 py-3 text-[#516478]">{{ row.record_id || '—' }}</td>
                        <td class="px-4 py-3 text-[#516478]">
                          {{ getPendingDecisionMatchFieldsLabel(row) }}
                        </td>
                        <td class="px-4 py-3">
                          <div v-if="!isLinkedImportEntityType(entityType)" class="flex flex-wrap gap-2">
                            <button
                              type="button"
                              class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                              :class="perRowDedupDecisions[String(row.row_number)] === 'create'
                                ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                                : 'border-[#d9e2ec] bg-white text-[#516478]'"
                              @click="perRowDedupDecisions[String(row.row_number)] = 'create'"
                            >
                              Создать
                            </button>
                            <button
                              type="button"
                              class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                              :class="perRowDedupDecisions[String(row.row_number)] === 'update'
                                ? 'border-[#1a7f3c] bg-[#edf7f0] text-[#1a7f3c]'
                                : 'border-[#d9e2ec] bg-white text-[#516478]'"
                              @click="perRowDedupDecisions[String(row.row_number)] = 'update'"
                            >
                              Обновить
                            </button>
                            <button
                              type="button"
                              class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                              :class="perRowDedupDecisions[String(row.row_number)] === 'skip'
                                ? 'border-[#9aa9b8] bg-[#f4f7fa] text-[#516478]'
                                : 'border-[#d9e2ec] bg-white text-[#516478]'"
                              @click="perRowDedupDecisions[String(row.row_number)] = 'skip'"
                            >
                              Пропустить
                            </button>
                          </div>
                          <div v-else class="space-y-3">
                            <div
                              v-for="entityId in getPendingDecisionLinkedEntityIds(row)"
                              :key="`${row.row_number}:${entityId}`"
                              class="rounded-[14px] border border-[#e6edf6] bg-[#fafcff] px-3 py-3"
                            >
                              <div class="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-[#7f92a7]">
                                {{ linkedDedupEntityGroups.find((item) => item.id === entityId)?.label || entityId }}
                              </div>
                              <div class="mb-2 text-xs text-[#6f8194]">
                                {{ getPendingDecisionMatchFieldsLabel(row, entityId) }}
                              </div>
                              <div class="flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                                  :class="getPerRowDedupDecision(String(row.row_number), entityId) === 'create'
                                    ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                                    : 'border-[#d9e2ec] bg-white text-[#516478]'"
                                  @click="setPerRowDedupDecision(String(row.row_number), entityId, 'create')"
                                >
                                  Создать
                                </button>
                                <button
                                  type="button"
                                  class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                                  :class="getPerRowDedupDecision(String(row.row_number), entityId) === 'update'
                                    ? 'border-[#1a7f3c] bg-[#edf7f0] text-[#1a7f3c]'
                                    : 'border-[#d9e2ec] bg-white text-[#516478]'"
                                  @click="setPerRowDedupDecision(String(row.row_number), entityId, 'update')"
                                >
                                  Обновить
                                </button>
                                <button
                                  type="button"
                                  class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
                                  :class="getPerRowDedupDecision(String(row.row_number), entityId) === 'skip'
                                    ? 'border-[#9aa9b8] bg-[#f4f7fa] text-[#516478]'
                                    : 'border-[#d9e2ec] bg-white text-[#516478]'"
                                  @click="setPerRowDedupDecision(String(row.row_number), entityId, 'skip')"
                                >
                                  Пропустить
                                </button>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div
                v-if="dryRunDedupWeakeningNotice.hasWarnings"
                class="mb-4 rounded-[18px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-4 text-[#8f5b18]"
              >
                <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#c77d2b]">Неполный поиск дублей</div>
                    <div class="mt-1 text-sm font-semibold">{{ dryRunDedupWeakeningNotice.title }}</div>
                    <div class="mt-1 whitespace-pre-wrap break-words text-sm text-[#9c6a2a]">
                      {{ getTextBlockDisplayValue(makeCollapsibleKey('dry-run-dedup', 'description'), dryRunDedupWeakeningNotice.description) }}
                    </div>
                    <button
                      v-if="isTextCollapsible(dryRunDedupWeakeningNotice.description)"
                      type="button"
                      class="mt-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('dry-run-dedup', 'description'))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('dry-run-dedup', 'description')) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                  <div class="rounded-full border border-[#f3c995] bg-white px-3 py-1 text-sm font-semibold text-[#a96017]">
                    {{ dryRunDedupWeakeningNotice.count }}
                  </div>
                </div>
                <div class="mt-3 grid gap-2 text-sm text-[#8f5b18] md:grid-cols-2">
                  <div class="min-w-0">
                    <span>Поля не заполнены: </span>
                    <span class="whitespace-pre-wrap break-words">{{ getTextBlockDisplayValue(makeCollapsibleKey('dry-run-dedup', 'fields'), dryRunDedupWeakeningNotice.fieldsLabel) }}</span>
                    <button
                      v-if="isTextCollapsible(dryRunDedupWeakeningNotice.fieldsLabel)"
                      type="button"
                      class="ml-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('dry-run-dedup', 'fields'))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('dry-run-dedup', 'fields')) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                  <div class="min-w-0">
                    <span>Строки риска: </span>
                    <span class="whitespace-pre-wrap break-words">{{ getTextBlockDisplayValue(makeCollapsibleKey('dry-run-dedup', 'rows'), dryRunDedupWeakeningNotice.rowsLabel) }}</span>
                    <button
                      v-if="isTextCollapsible(dryRunDedupWeakeningNotice.rowsLabel)"
                      type="button"
                      class="ml-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('dry-run-dedup', 'rows'))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('dry-run-dedup', 'rows')) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                </div>
                <div class="mt-3">
                  <button
                    type="button"
                    class="inline-flex items-center rounded-full border border-[#f2d1ac] bg-white px-3 py-2 text-sm font-medium text-[#8a5a24] transition hover:border-[#e8bc86] hover:bg-[#fffaf4]"
                    @click="toggleDryRunDedupRiskOnly"
                  >
                    {{ activeDryRunDedupRiskOnly ? 'Сбросить фильтр' : 'Показать только строки риска' }}
                  </button>
                </div>
              </div>

              <div class="overflow-hidden rounded-[20px] border border-[#dfe5eb] bg-white">
                <B24Table
                  v-if="dryRunData"
                  class="w-full"
                  :loading="busyAction === 'sample-preview'"
                  loading-color="air-primary"
                  loading-animation="loading"
                  :columns="dryRunTableColumns"
                  :data="paginatedDryRunRows"
                  :empty="activeDryRunDedupRiskOnly
                    ? 'Строки с риском неполного поиска дублей не найдены.'
                    : 'После тестового импорта здесь появится предварительный отчет по строкам.'"
                >
                  <template #rowNumber-cell="{ row }">
                    <div class="py-1 font-medium text-[#314256]">
                      {{ getRowNumberDisplayValue(row.original) }}
                    </div>
                  </template>
                  <template #details-cell="{ row }">
                    <div v-if="hasLinkedEntityTree(row.original)" class="py-1">
                      <div class="space-y-2">
                        <div class="rounded-[18px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-3 transition-all hover:border-[#c2d4f0] hover:bg-white hover:shadow-[0_2px_12px_rgba(46,107,217,0.06)]">
                          <div class="flex flex-wrap items-center justify-between gap-3">
                            <div class="min-w-0">
                              <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                                {{ row.original.entityTree?.primary.entityLabel }}
                              </div>
                              <div class="mt-1 truncate text-sm font-semibold text-[#2f4254]">
                                {{ row.original.entityTree?.primary.title }}
                              </div>
                            </div>
                            <div
                              class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                              :class="getLinkedEntityTreeStatusClass(row.original.entityTree?.primary.status || '')"
                            >
                              {{ row.original.entityTree?.primary.statusLabel }}
                            </div>
                          </div>
                        </div>

                        <div
                          v-if="row.original.entityTree?.linkedItems?.length"
                          class="ml-4 space-y-2 border-l-2 border-[#d7e7ff] pl-4"
                        >
                          <div
                            v-for="item in row.original.entityTree?.linkedItems || []"
                            :key="item.key"
                            class="rounded-[14px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3"
                          >
                            <div class="flex flex-wrap items-center justify-between gap-3">
                              <div class="min-w-0">
                                <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                                  {{ item.entityLabel }}
                                </div>
                                <div class="mt-1 truncate text-sm font-medium text-[#2f4254]">
                                  {{ item.title }}
                                </div>
                              </div>
                              <div
                                class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                                :class="getLinkedEntityTreeStatusClass(item.status)"
                              >
                                {{ item.statusLabel }}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-else class="py-1">
                      <div class="rounded-[16px] border border-[#e6edf6] bg-[#fbfcfe] px-4 py-3">
                        <div class="flex flex-wrap items-start justify-between gap-3">
                          <div class="min-w-0 flex-1">
                            <div v-if="hasExecutionRowHeading(row.original)" class="mb-2">
                              <div class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                                {{ row.original.entityLabel || 'Запись' }}
                              </div>
                              <div class="mt-1 truncate text-sm font-semibold text-[#314256]">
                                {{ row.original.title || 'Без названия' }}
                              </div>
                            </div>
                            <div class="whitespace-pre-wrap break-words text-sm text-[#314256]">
                              {{ getTextBlockDisplayValue(makeCollapsibleKey('dry-run-row', row.original.key), row.original.details) }}
                            </div>
                            <button
                              v-if="isTextCollapsible(row.original.details)"
                              type="button"
                              class="mt-2 text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                              @click="toggleTextBlock(makeCollapsibleKey('dry-run-row', row.original.key))"
                            >
                              {{ isTextBlockExpanded(makeCollapsibleKey('dry-run-row', row.original.key)) ? 'Скрыть' : 'Показать полностью' }}
                            </button>
                          </div>
                          <div
                            class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                            :class="getLinkedEntityTreeStatusClass(row.original.status || '')"
                          >
                            {{ row.original.statusLabel }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </template>
                </B24Table>
                <div
                  v-if="dryRunData && dryRunPageCount > 1"
                  class="border-t border-[#e8eef5] bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)] px-4 py-4"
                >
                  <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div class="text-sm text-[#5f7285]">
                      Показаны строки <span class="font-semibold text-[#314256]">{{ dryRunPageRangeStart }}-{{ dryRunPageRangeEnd }}</span>
                      из <span class="font-semibold text-[#314256]">{{ filteredDryRunRows.length }}</span>.
                    </div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                      Страница {{ dryRunPage }} из {{ dryRunPageCount }}
                    </div>
                  </div>

                  <div class="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      class="rounded-full border border-[#d9e2ec] bg-white px-3 py-2 text-sm font-medium text-[#516478] transition hover:border-[#b8cae1] hover:text-[#2e6bd9] disabled:cursor-not-allowed disabled:opacity-45"
                      :disabled="dryRunPage <= 1"
                      @click="setDryRunPage(dryRunPage - 1)"
                    >
                      Назад
                    </button>

                    <button
                      v-for="pageItem in buildVisibleDryRunPageItems()"
                      :key="String(pageItem)"
                      type="button"
                      class="min-w-10 rounded-full border px-3 py-2 text-sm font-semibold transition"
                      :class="pageItem === dryRunPage
                        ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                        : pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis'
                          ? 'cursor-default border-transparent bg-transparent text-[#9aa9b8]'
                          : 'border-[#d9e2ec] bg-white text-[#516478] hover:border-[#b8cae1] hover:text-[#2e6bd9]'"
                      :disabled="pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis'"
                      @click="typeof pageItem === 'number' && setDryRunPage(pageItem)"
                    >
                      {{ pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis' ? '…' : pageItem }}
                    </button>

                    <button
                      type="button"
                      class="rounded-full border border-[#d9e2ec] bg-white px-3 py-2 text-sm font-medium text-[#516478] transition hover:border-[#b8cae1] hover:text-[#2e6bd9] disabled:cursor-not-allowed disabled:opacity-45"
                      :disabled="dryRunPage >= dryRunPageCount"
                      @click="setDryRunPage(dryRunPage + 1)"
                    >
                      Далее
                    </button>
                  </div>
                </div>
                <B24Table
                  v-else
                  class="w-full"
                  :loading="busyAction === 'validation' || busyAction === 'sample-preview'"
                  loading-color="air-primary"
                  loading-animation="loading"
                  :columns="validationTableColumns"
                  :data="validationIssueRows"
                  empty="Ошибок не найдено. Можно запускать тестовый импорт."
                >
                  <template #message-cell="{ row }">
                    <div class="py-1">
                      <div class="whitespace-pre-wrap break-words text-sm text-[#314256]">
                        {{ getTextBlockDisplayValue(makeCollapsibleKey('validation-message', row.original.key), row.original.message) }}
                      </div>
                      <button
                        v-if="isTextCollapsible(row.original.message)"
                        type="button"
                        class="mt-2 text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                        @click="toggleTextBlock(makeCollapsibleKey('validation-message', row.original.key))"
                      >
                        {{ isTextBlockExpanded(makeCollapsibleKey('validation-message', row.original.key)) ? 'Скрыть' : 'Показать полностью' }}
                      </button>
                    </div>
                  </template>
                  <template #value-cell="{ row }">
                    <div class="py-1">
                      <div class="whitespace-pre-wrap break-words text-sm text-[#314256]">
                        {{ getTextBlockDisplayValue(makeCollapsibleKey('validation-value', row.original.key), row.original.value) }}
                      </div>
                      <button
                        v-if="isTextCollapsible(row.original.value)"
                        type="button"
                        class="mt-2 text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                        @click="toggleTextBlock(makeCollapsibleKey('validation-value', row.original.key))"
                      >
                        {{ isTextBlockExpanded(makeCollapsibleKey('validation-value', row.original.key)) ? 'Скрыть' : 'Показать полностью' }}
                      </button>
                    </div>
                  </template>
                </B24Table>
              </div>
            </section>
          </section>

          <section v-if="currentStep === 7" class="space-y-6">
            <section class="rounded-[24px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-5">
              <div class="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 7</div>
                  <h2 class="mt-1 text-xl font-semibold text-[#314256]">Результат импорта</h2>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                  <B24Button
                    label="Назад"
                    color="air-primary"
                    size="lg"
                    :disabled="!canGoBack"
                    @click="goBack"
                  />
                  <B24Button
                    v-if="busyAction === 'run' || busyAction === 'retry' || cancelRequested"
                    label="Остановить импорт"
                    color="air-tertiary"
                    size="lg"
                    :loading="cancelRequested"
                    :disabled="!canCancelActiveImport"
                    @click="cancelActiveImport"
                  />
                  <B24Button
                    v-if="!busyAction"
                    label="Завершить"
                    color="air-secondary"
                    size="lg"
                    @click="finishToEntitySelection"
                  />
                  <div
                    v-if="!busyAction || (busyAction !== 'run' && busyAction !== 'retry')"
                    class="rounded-full px-4 py-2 text-sm font-semibold"
                    :class="importRunFailedRows > 0 ? 'border border-[#ffe1c7] bg-[#fff7ef] text-[#c77d2b]' : 'border border-[#d7e7ff] bg-[#f4f9ff] text-[#2e6bd9]'"
                  >
                    {{ importRunFailedRows > 0 ? `Есть ошибки: ${importRunFailedRows}` : 'Импорт завершен без ошибок' }}
                  </div>
                </div>
              </div>

              <div class="grid gap-4 md:grid-cols-5">
                <div class="rounded-[18px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Проверено</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ importRunCheckedRows }}</div>
                </div>
                <div class="rounded-[18px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Создано</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ importRunCreatedRows }}</div>
                </div>
                <div class="rounded-[18px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Обновлено</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ importRunUpdatedRows }}</div>
                </div>
                <div class="rounded-[18px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Ошибки</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ importRunFailedRows }}</div>
                </div>
                <div class="rounded-[18px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Пропущено</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ importRunSkippedRows }}</div>
                </div>
              </div>
            </section>

            <section
              v-if="busyAction === 'run'"
              class="rounded-[24px] border border-[#d7e7ff] bg-[#f4f9ff] p-5"
            >
              <div class="mb-4 flex items-center gap-3">
                <div class="h-5 w-5 animate-spin rounded-full border-2 border-[#b8d4f8] border-t-[#2e6bd9]" />
                <div class="text-base font-semibold text-[#2e6bd9]">
                  Импорт в процессе…
                </div>
              </div>
              <div class="mb-2 flex items-center justify-between text-sm">
                <span class="text-[#5f7285]">Прогресс</span>
                <span class="font-medium text-[#314256]">
                  {{ session?.processed_rows ?? 0 }} из {{ session?.total_rows || '…' }} строк
                </span>
              </div>
              <div class="mb-4 h-2 w-full overflow-hidden rounded-full bg-[#dde8f8]">
                <div
                  class="h-2 rounded-full bg-[#2e6bd9] transition-all duration-500"
                  :style="{ width: sessionProgressPercent + '%' }"
                />
              </div>
              <div class="flex flex-wrap gap-5 text-sm text-[#5f7285]">
                <span>Обработано: <strong class="text-[#314256]">{{ session?.processed_rows ?? 0 }}</strong></span>
                <span>Успешно: <strong class="text-[#1a7a4a]">{{ session?.successful_rows ?? 0 }}</strong></span>
                <span>Ошибки: <strong class="text-[#c24b53]">{{ session?.failed_rows ?? 0 }}</strong></span>
              </div>
              <div
                v-if="session?.summary?.import_progress?.pause_info"
                class="mt-4 flex items-start gap-3 rounded-[12px] border border-[#ffe9b0] bg-[#fffbef] px-4 py-3 text-sm text-[#8a6a00]"
              >
                <span class="mt-0.5 text-base">⏸</span>
                <div>
                  <div class="font-semibold">Пауза: ожидаем сброса лимита Bitrix24</div>
                  <div class="mt-0.5 text-[#b38a00]">
                    Импорт автоматически продолжится через ~{{ session.summary.import_progress.pause_info.wait_seconds }} сек.
                  </div>
                </div>
              </div>
            </section>

            <section
              v-if="busyAction === 'retry'"
              class="rounded-[24px] border border-[#d7e7ff] bg-[#f4f9ff] p-5"
            >
              <div class="mb-4 flex items-center gap-3">
                <div class="h-5 w-5 animate-spin rounded-full border-2 border-[#b8d4f8] border-t-[#2e6bd9]" />
                <div class="text-base font-semibold text-[#2e6bd9]">
                  Повтор импорта в процессе…
                </div>
              </div>
              <div class="mb-2 flex items-center justify-between text-sm">
                <span class="text-[#5f7285]">Прогресс</span>
                <span class="font-medium text-[#314256]">
                  {{ session?.processed_rows ?? 0 }} из {{ retryTotalRows || '…' }} строк
                </span>
              </div>
              <div class="mb-4 h-2 w-full overflow-hidden rounded-full bg-[#dde8f8]">
                <div
                  class="h-2 rounded-full bg-[#2e6bd9] transition-all duration-500"
                  :style="{ width: (retryTotalRows ? Math.min(100, Math.round(((session?.processed_rows ?? 0) / retryTotalRows) * 100)) : 0) + '%' }"
                />
              </div>
              <div class="flex flex-wrap gap-5 text-sm text-[#5f7285]">
                <span>Обработано: <strong class="text-[#314256]">{{ session?.processed_rows ?? 0 }}</strong></span>
                <span>Успешно: <strong class="text-[#1a7a4a]">{{ session?.successful_rows ?? 0 }}</strong></span>
                <span>Ошибки: <strong class="text-[#c24b53]">{{ session?.failed_rows ?? 0 }}</strong></span>
              </div>
              <div
                v-if="session?.summary?.import_progress?.pause_info"
                class="mt-4 flex items-start gap-3 rounded-[12px] border border-[#ffe9b0] bg-[#fffbef] px-4 py-3 text-sm text-[#8a6a00]"
              >
                <span class="mt-0.5 text-base">⏸</span>
                <div>
                  <div class="font-semibold">Пауза: ожидаем сброса лимита Bitrix24</div>
                  <div class="mt-0.5 text-[#b38a00]">
                    Импорт автоматически продолжится через ~{{ session.summary.import_progress.pause_info.wait_seconds }} сек.
                  </div>
                </div>
              </div>
            </section>

            <section
              v-if="isLinkedEntityImport && linkedImportRunSummary.hasSummary"
              class="overflow-hidden rounded-[30px] border border-[#dfe5eb] bg-white shadow-[0_8px_32px_rgba(23,54,110,0.07)]"
            >
              <div class="border-b border-[#e5ebf1] bg-[linear-gradient(180deg,#ffffff_0%,#f4f8fe_100%)] px-6 py-5">
                <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">Итог</div>
                    <h3 class="mt-1.5 text-[17px] font-semibold text-[#2f4254]">Что создано по связанному импорту</h3>
                  </div>
                  <div
                    v-if="linkedImportRunSummary.hasOverflow"
                    class="rounded-[16px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-3 text-sm text-[#a96c25]"
                  >
                    {{ linkedImportRunSummary.overflowMessage }}
                  </div>
                </div>
              </div>

              <div class="grid gap-4 p-6 xl:grid-cols-2">
                <div
                  v-for="section in linkedImportRunSummary.sections"
                  :key="section.id"
                  class="flex flex-col rounded-[22px] border border-[#e5ebf2] bg-[#fbfcfe] p-5 transition-all duration-200 hover:border-[#c2d4f0] hover:bg-white hover:shadow-[0_4px_20px_rgba(46,107,217,0.06)]"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">Сущность</div>
                      <div class="mt-1.5 text-[15px] font-semibold text-[#2f4254]">{{ section.title }}</div>
                      <div class="mt-1 text-sm leading-relaxed text-[#6c8093]">Всего: {{ section.total }}</div>
                    </div>
                  </div>

                  <div class="mt-4 space-y-2">
                    <div
                      v-for="item in buildVisibleLinkedSummaryItems(section)"
                      :key="item.key"
                      class="flex items-start justify-between gap-3 rounded-[14px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3"
                    >
                      <div class="min-w-0">
                        <div class="truncate text-sm font-medium text-[#2f4254]">{{ item.title }}</div>
                        <div class="mt-0.5 text-[12px] leading-relaxed text-[#5c7592]">ID {{ item.recordId }}</div>
                      </div>
                      <div class="shrink-0 rounded-full border border-[#d7e7ff] bg-white px-3 py-1 text-xs font-semibold text-[#2e6bd9]">
                        {{ item.statusLabel }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="linkedSummaryPageCount > 1"
                class="flex flex-wrap items-center justify-center gap-2 border-t border-[#e5ebf1] px-6 py-4"
              >
                <button
                  v-for="page in buildLinkedSummaryPages()"
                  :key="page"
                  type="button"
                  class="inline-flex min-w-10 items-center justify-center rounded-full border px-3 py-2 text-sm font-semibold transition"
                  :class="linkedSummaryPage === page
                    ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                    : 'border-[#d9e2ec] bg-white text-[#516478]'"
                  @click="setLinkedSummaryPage(page)"
                >
                  {{ page }}
                </button>
              </div>

              <div class="flex flex-wrap gap-3 border-t border-[#e5ebf1] px-6 py-5">
                <B24Button
                  v-if="busyAction === 'retry' || cancelRequested"
                  label="Остановить импорт"
                  color="air-tertiary"
                  size="lg"
                  :loading="cancelRequested"
                  :disabled="!canCancelActiveImport"
                  @click="cancelActiveImport"
                />
                <B24Button
                  label="Скачать CSV-отчет"
                  color="air-secondary-accent-2"
                  size="lg"
                  :loading="busyAction === 'report'"
                  :disabled="!canDownloadImportReport"
                  @click="downloadImportReport"
                />
                <B24Button
                  label="Повторить неуспешные строки"
                  color="air-primary"
                  size="lg"
                  :loading="busyAction === 'retry'"
                  :disabled="!canRetryFailedRows"
                  @click="retryFailedRows"
                />
              </div>
            </section>

            <section
              v-if="dryRunData"
              class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5"
            >
              <button
                type="button"
                class="flex w-full flex-col gap-3 text-left md:flex-row md:items-center md:justify-between"
                @click="isStepSevenDryRunExpanded = !isStepSevenDryRunExpanded"
              >
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Тестовый импорт</div>
                  <h3 class="mt-1 text-xl font-semibold text-[#314256]">Результат тестового импорта</h3>
                </div>
                <div class="inline-flex items-center rounded-full border border-[#d9e2ec] bg-white px-4 py-2 text-sm font-semibold text-[#516478]">
                  {{ isStepSevenDryRunExpanded ? 'Свернуть' : 'Развернуть' }}
                </div>
              </button>

              <div v-if="isStepSevenDryRunExpanded" class="mt-5">
                <div class="overflow-hidden rounded-[20px] border border-[#dfe5eb] bg-white">
                  <B24Table
                    class="w-full"
                    :columns="dryRunTableColumns"
                    :data="paginatedDryRunRows"
                    empty="После тестового импорта здесь появится предварительный отчет по строкам."
                  >
                    <template #rowNumber-cell="{ row }">
                      <div class="py-1 font-medium text-[#314256]">
                        {{ getRowNumberDisplayValue(row.original) }}
                      </div>
                    </template>
                    <template #details-cell="{ row }">
                      <div v-if="hasLinkedEntityTree(row.original)" class="py-1">
                        <div class="space-y-2">
                          <div class="rounded-[18px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-3 transition-all hover:border-[#c2d4f0] hover:bg-white hover:shadow-[0_2px_12px_rgba(46,107,217,0.06)]">
                            <div class="flex flex-wrap items-center justify-between gap-3">
                              <div class="min-w-0">
                                <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                                  {{ row.original.entityTree?.primary.entityLabel }}
                                </div>
                                <div class="mt-1 truncate text-sm font-semibold text-[#2f4254]">
                                  {{ row.original.entityTree?.primary.title }}
                                </div>
                              </div>
                              <div
                                class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                                :class="getLinkedEntityTreeStatusClass(row.original.entityTree?.primary.status || '')"
                              >
                                {{ row.original.entityTree?.primary.statusLabel }}
                              </div>
                            </div>
                          </div>

                          <div
                            v-if="row.original.entityTree?.linkedItems?.length"
                            class="ml-4 space-y-2 border-l-2 border-[#d7e7ff] pl-4"
                          >
                            <div
                              v-for="item in row.original.entityTree?.linkedItems || []"
                              :key="item.key"
                              class="rounded-[14px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3"
                            >
                              <div class="flex flex-wrap items-center justify-between gap-3">
                                <div class="min-w-0">
                                  <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                                    {{ item.entityLabel }}
                                  </div>
                                  <div class="mt-1 truncate text-sm font-medium text-[#2f4254]">
                                    {{ item.title }}
                                  </div>
                                </div>
                                <div
                                  class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                                  :class="getLinkedEntityTreeStatusClass(item.status)"
                                >
                                  {{ item.statusLabel }}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div v-else class="py-1">
                        <div class="rounded-[16px] border border-[#e6edf6] bg-[#fbfcfe] px-4 py-3">
                          <div class="flex flex-wrap items-start justify-between gap-3">
                            <div class="min-w-0 flex-1">
                              <div v-if="hasExecutionRowHeading(row.original)" class="mb-2">
                                <div class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                                  {{ row.original.entityLabel || 'Запись' }}
                                </div>
                                <div class="mt-1 truncate text-sm font-semibold text-[#314256]">
                                  {{ row.original.title || 'Без названия' }}
                                </div>
                              </div>
                              <div class="whitespace-pre-wrap break-words text-sm text-[#314256]">
                                {{ getTextBlockDisplayValue(makeCollapsibleKey('step-seven-dry-run-row', row.original.key), row.original.details) }}
                              </div>
                              <button
                                v-if="isTextCollapsible(row.original.details)"
                                type="button"
                                class="mt-2 text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                                @click="toggleTextBlock(makeCollapsibleKey('step-seven-dry-run-row', row.original.key))"
                              >
                                {{ isTextBlockExpanded(makeCollapsibleKey('step-seven-dry-run-row', row.original.key)) ? 'Скрыть' : 'Показать полностью' }}
                              </button>
                            </div>
                            <div
                              class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                              :class="getLinkedEntityTreeStatusClass(row.original.status || '')"
                            >
                              {{ row.original.statusLabel }}
                            </div>
                          </div>
                        </div>
                      </div>
                    </template>
                  </B24Table>
                  <div
                    v-if="dryRunData && dryRunPageCount > 1"
                    class="border-t border-[#e8eef5] bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)] px-4 py-4"
                  >
                    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div class="text-sm text-[#5f7285]">
                        Показаны строки <span class="font-semibold text-[#314256]">{{ dryRunPageRangeStart }}-{{ dryRunPageRangeEnd }}</span>
                        из <span class="font-semibold text-[#314256]">{{ filteredDryRunRows.length }}</span>.
                      </div>
                      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                        Страница {{ dryRunPage }} из {{ dryRunPageCount }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
              <div class="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Детали</div>
                  <h3 class="mt-1 text-xl font-semibold text-[#314256]">Результат по строкам</h3>
                </div>

                <div class="flex flex-wrap gap-3">
                  <B24Button
                    v-if="busyAction === 'retry' || cancelRequested"
                    label="Остановить импорт"
                    color="air-tertiary"
                    size="lg"
                    :loading="cancelRequested"
                    :disabled="!canCancelActiveImport"
                    @click="cancelActiveImport"
                  />
                  <B24Button
                    label="Скачать CSV-отчет"
                    color="air-secondary-accent-2"
                    size="lg"
                    :loading="busyAction === 'report'"
                    :disabled="!canDownloadImportReport"
                    @click="downloadImportReport"
                  />
                  <B24Button
                    label="Повторить неуспешные строки"
                    color="air-primary"
                    size="lg"
                    :loading="busyAction === 'retry'"
                    :disabled="!canRetryFailedRows"
                    @click="retryFailedRows"
                  />
                </div>
              </div>

              <div
                v-if="importRunProblemGroups.length"
                class="mb-5 grid gap-3 lg:grid-cols-3"
              >
                <div
                  v-for="group in importRunProblemGroups"
                  :key="group.key"
                  class="rounded-[18px] border border-[#ffe2d1] bg-[linear-gradient(180deg,#fffaf6_0%,#fff3eb_100%)] px-4 py-4"
                >
                  <div class="flex items-center justify-between gap-3">
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#c77d2b]">{{ group.label }}</div>
                    <div class="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#8c5c24]">{{ group.count }}</div>
                  </div>
                  <div class="mt-2 whitespace-pre-wrap break-words text-sm font-medium text-[#314256]">
                    {{ getTextBlockDisplayValue(makeCollapsibleKey('import-group-reason', group.key), group.reason) }}
                  </div>
                  <button
                    v-if="isTextCollapsible(group.reason)"
                    type="button"
                    class="mt-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                    @click="toggleTextBlock(makeCollapsibleKey('import-group-reason', group.key))"
                  >
                    {{ isTextBlockExpanded(makeCollapsibleKey('import-group-reason', group.key)) ? 'Скрыть' : 'Показать полностью' }}
                  </button>
                  <div class="mt-3 text-xs text-[#8a6c4a]">
                    <span>Строки: </span>
                    <span class="whitespace-pre-wrap break-words">{{ getTextBlockDisplayValue(makeCollapsibleKey('import-group-rows', group.key), group.rowNumbers.join(', ')) }}</span>
                    <button
                      v-if="isTextCollapsible(group.rowNumbers.join(', '))"
                      type="button"
                      class="ml-2 text-[11px] font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('import-group-rows', group.key))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('import-group-rows', group.key)) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                </div>
              </div>

              <div class="mb-5 flex flex-wrap gap-2">
                <button
                  v-for="filterItem in importRunStatusFilters"
                  :key="filterItem.id"
                  type="button"
                  class="rounded-full border px-3 py-2 text-sm font-medium transition"
                  :class="activeImportRunFilter === filterItem.id
                    ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                    : 'border-[#d9e2ec] bg-white text-[#516478]'"
                  @click="selectImportRunFilter(filterItem.id)"
                >
                  {{ filterItem.label }} · {{ filterItem.count }}
                </button>
              </div>

              <div
                v-if="importRunDedupWeakeningNotice.hasWarnings"
                class="mb-5 rounded-[18px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-4 text-[#8f5b18]"
              >
                <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#c77d2b]">Неполный поиск дублей</div>
                    <div class="mt-1 text-sm font-semibold">{{ importRunDedupWeakeningNotice.title }}</div>
                    <div class="mt-1 whitespace-pre-wrap break-words text-sm text-[#9c6a2a]">
                      {{ getTextBlockDisplayValue(makeCollapsibleKey('import-dedup', 'description'), importRunDedupWeakeningNotice.description) }}
                    </div>
                    <button
                      v-if="isTextCollapsible(importRunDedupWeakeningNotice.description)"
                      type="button"
                      class="mt-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('import-dedup', 'description'))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('import-dedup', 'description')) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                  <div class="rounded-full border border-[#f3c995] bg-white px-3 py-1 text-sm font-semibold text-[#a96017]">
                    {{ importRunDedupWeakeningNotice.count }}
                  </div>
                </div>
                <div class="mt-3 grid gap-2 text-sm text-[#8f5b18] md:grid-cols-2">
                  <div class="min-w-0">
                    <span>Поля не заполнены: </span>
                    <span class="whitespace-pre-wrap break-words">{{ getTextBlockDisplayValue(makeCollapsibleKey('import-dedup', 'fields'), importRunDedupWeakeningNotice.fieldsLabel) }}</span>
                    <button
                      v-if="isTextCollapsible(importRunDedupWeakeningNotice.fieldsLabel)"
                      type="button"
                      class="ml-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('import-dedup', 'fields'))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('import-dedup', 'fields')) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                  <div class="min-w-0">
                    <span>Строки риска: </span>
                    <span class="whitespace-pre-wrap break-words">{{ getTextBlockDisplayValue(makeCollapsibleKey('import-dedup', 'rows'), importRunDedupWeakeningNotice.rowsLabel) }}</span>
                    <button
                      v-if="isTextCollapsible(importRunDedupWeakeningNotice.rowsLabel)"
                      type="button"
                      class="ml-2 text-xs font-semibold text-[#a96017] transition hover:text-[#8f4d12]"
                      @click="toggleTextBlock(makeCollapsibleKey('import-dedup', 'rows'))"
                    >
                      {{ isTextBlockExpanded(makeCollapsibleKey('import-dedup', 'rows')) ? 'Скрыть' : 'Показать полностью' }}
                    </button>
                  </div>
                </div>
                <div class="mt-3">
                  <button
                    type="button"
                    class="inline-flex items-center rounded-full border border-[#f2d1ac] bg-white px-3 py-2 text-sm font-medium text-[#8a5a24] transition hover:border-[#e8bc86] hover:bg-[#fffaf4]"
                    @click="selectImportRunFilter(activeImportRunFilter === 'dedup_risk' ? 'all' : 'dedup_risk')"
                  >
                    {{ activeImportRunFilter === 'dedup_risk' ? 'Сбросить фильтр' : 'Показать только строки риска' }}
                  </button>
                </div>
              </div>

              <div class="overflow-hidden rounded-[20px] border border-[#dfe5eb] bg-white">
                <B24Table
                  class="w-full"
                  :loading="busyAction === 'run' || busyAction === 'retry'"
                  loading-color="air-primary"
                  loading-animation="loading"
                  :columns="importRunTableColumns"
                  :data="paginatedImportRunRows"
                  :empty="activeImportRunFilter === 'all'
                    ? 'После запуска импорта здесь появится итог по строкам.'
                    : 'Для выбранного фильтра строк не найдено.'"
                >
                  <template #rowNumber-cell="{ row }">
                    <div class="py-1 font-medium text-[#314256]">
                      {{ getRowNumberDisplayValue(row.original) }}
                    </div>
                  </template>
                  <template #details-cell="{ row }">
                    <div v-if="hasLinkedEntityTree(row.original)" class="py-1">
                      <div class="space-y-2">
                        <div class="rounded-[18px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-3 transition-all hover:border-[#c2d4f0] hover:bg-white hover:shadow-[0_2px_12px_rgba(46,107,217,0.06)]">
                          <div class="flex flex-wrap items-center justify-between gap-3">
                            <div class="min-w-0">
                              <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                                {{ row.original.entityTree?.primary.entityLabel }}
                              </div>
                              <div class="mt-1 truncate text-sm font-semibold text-[#2f4254]">
                                {{ row.original.entityTree?.primary.title }}
                              </div>
                            </div>
                            <div
                              class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                              :class="getLinkedEntityTreeStatusClass(row.original.entityTree?.primary.status || '')"
                            >
                              {{ row.original.entityTree?.primary.statusLabel }}
                            </div>
                          </div>
                        </div>

                        <div
                          v-if="row.original.entityTree?.linkedItems?.length"
                          class="ml-4 space-y-2 border-l-2 border-[#d7e7ff] pl-4"
                        >
                          <div
                            v-for="item in row.original.entityTree?.linkedItems || []"
                            :key="item.key"
                            class="rounded-[14px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3"
                          >
                            <div class="flex flex-wrap items-center justify-between gap-3">
                              <div class="min-w-0">
                                <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                                  {{ item.entityLabel }}
                                </div>
                                <div class="mt-1 truncate text-sm font-medium text-[#2f4254]">
                                  {{ item.title }}
                                </div>
                              </div>
                              <div
                                class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                                :class="getLinkedEntityTreeStatusClass(item.status)"
                              >
                                {{ item.statusLabel }}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-else class="py-1">
                      <div class="rounded-[16px] border border-[#e6edf6] bg-[#fbfcfe] px-4 py-3">
                        <div class="flex flex-wrap items-start justify-between gap-3">
                          <div class="min-w-0 flex-1">
                            <div v-if="hasExecutionRowHeading(row.original)" class="mb-2">
                              <div class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                                {{ row.original.entityLabel || 'Запись' }}
                              </div>
                              <div class="mt-1 truncate text-sm font-semibold text-[#314256]">
                                {{ row.original.title || 'Без названия' }}
                              </div>
                            </div>
                            <div class="whitespace-pre-wrap break-words text-sm text-[#314256]">
                              {{ getTextBlockDisplayValue(makeCollapsibleKey('import-run-row', row.original.key), row.original.details) }}
                            </div>
                            <button
                              v-if="isTextCollapsible(row.original.details)"
                              type="button"
                              class="mt-2 text-xs font-semibold text-[#2e6bd9] transition hover:text-[#1f56b2]"
                              @click="toggleTextBlock(makeCollapsibleKey('import-run-row', row.original.key))"
                            >
                              {{ isTextBlockExpanded(makeCollapsibleKey('import-run-row', row.original.key)) ? 'Скрыть' : 'Показать полностью' }}
                            </button>
                          </div>
                          <div
                            class="shrink-0 rounded-full border px-3 py-1 text-xs font-semibold"
                            :class="getLinkedEntityTreeStatusClass(row.original.status || '')"
                          >
                            {{ row.original.statusLabel }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </template>
                </B24Table>
                <div
                  v-if="importRunData && importRunPageCount > 1"
                  class="border-t border-[#e8eef5] bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)] px-4 py-4"
                >
                  <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div class="text-sm text-[#5f7285]">
                      Показаны строки <span class="font-semibold text-[#314256]">{{ importRunPageRangeStart }}-{{ importRunPageRangeEnd }}</span>
                      из <span class="font-semibold text-[#314256]">{{ filteredImportRunRows.length }}</span>.
                    </div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                      Страница {{ importRunPage }} из {{ importRunPageCount }}
                    </div>
                  </div>

                  <div class="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      class="rounded-full border border-[#d9e2ec] bg-white px-3 py-2 text-sm font-medium text-[#516478] transition hover:border-[#b8cae1] hover:text-[#2e6bd9] disabled:cursor-not-allowed disabled:opacity-45"
                      :disabled="importRunPage <= 1"
                      @click="setImportRunPage(importRunPage - 1)"
                    >
                      Назад
                    </button>

                    <button
                      v-for="pageItem in buildVisibleImportRunPageItems()"
                      :key="String(pageItem)"
                      type="button"
                      class="min-w-10 rounded-full border px-3 py-2 text-sm font-semibold transition"
                      :class="pageItem === importRunPage
                        ? 'border-[#2e6bd9] bg-[#edf5ff] text-[#2e6bd9]'
                        : pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis'
                          ? 'cursor-default border-transparent bg-transparent text-[#9aa9b8]'
                          : 'border-[#d9e2ec] bg-white text-[#516478] hover:border-[#b8cae1] hover:text-[#2e6bd9]'"
                      :disabled="pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis'"
                      @click="typeof pageItem === 'number' && setImportRunPage(pageItem)"
                    >
                      {{ pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis' ? '…' : pageItem }}
                    </button>

                    <button
                      type="button"
                      class="rounded-full border border-[#d9e2ec] bg-white px-3 py-2 text-sm font-medium text-[#516478] transition hover:border-[#b8cae1] hover:text-[#2e6bd9] disabled:cursor-not-allowed disabled:opacity-45"
                      :disabled="importRunPage >= importRunPageCount"
                      @click="setImportRunPage(importRunPage + 1)"
                    >
                      Далее
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </section>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.history-restore-fade-enter-active,
.history-restore-fade-leave-active {
  transition: opacity 0.18s ease;
}
.history-restore-fade-enter-from,
.history-restore-fade-leave-to {
  opacity: 0;
}

.step1-fade-enter-active {
  transition: opacity 0.38s ease, transform 0.38s ease;
}
.step1-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.step1-fade-enter-from {
  opacity: 0;
  transform: translateY(14px);
}
.step1-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
