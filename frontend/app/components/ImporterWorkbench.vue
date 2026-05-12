<script setup lang="ts">
import {
  buildExampleTemplateDownloadMeta,
  buildImporterPermissionState,
  buildImportScenarioSections,
  buildScenarioSelectionSummary,
  buildMigrationStatusBadge,
  buildDedupPayload,
  buildDedupWeakeningNotice,
  EMPTY_MAPPING_SELECT_VALUE,
  buildDryRunRows,
  buildFieldGuidanceHints,
  buildFieldTypeLabel,
  buildImportRunProblemGroups,
  buildImportRunRows,
  buildLinkedImportRunSummary,
  buildImportRunStatusFilters,
  buildImportRunRetryState,
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
  getWizardAdvanceMode,
  getWizardNextLabel,
  normalizeMappingSelectValue,
  resolveMappingSelectValue,
  shouldRenderInlineWizardFooter,
  buildSessionHistoryRows,
} from '~/utils/importer-ui'

type MappingRow = {
  key: string
  column: string
  sourceHeader: string
  targetFieldId: string
  targetFieldTitle: string
  autoMatchType?: string
  autoMatchLabel?: string
  targetFieldType?: string
  targetFieldTypeLabel?: string
  targetFieldRequired?: boolean
  targetFieldIsCustom?: boolean
  targetFieldIsMultiple?: boolean
  targetFieldGuidanceHints?: string[]
  valueMapping?: Record<string, string>
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
  status: string
  statusLabel: string
  recordId: string
  details: string
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
  status: string
  statusLabel: string
  details: string
}

type ImportTemplateItem = {
  id: string
  name: string
}

type StepState = 'done' | 'current' | 'upcoming'

const apiStore = useApiStore()
const userStore = useUserStore()

const entityType = ref('')
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const session = ref<Record<string, any> | null>(null)
const preview = ref<Record<string, any> | null>(null)
const mappingData = ref<Record<string, any> | null>(null)
const mappingRows = ref<MappingRow[]>([])
const taskDefaultResponsibleId = ref('')
const taskDefaultCommentAuthorId = ref('')
const dedupStrategy = ref('create')
const dedupFields = ref<string[]>([])
const validationData = ref<Record<string, any> | null>(null)
const dryRunData = ref<Record<string, any> | null>(null)
const importRunData = ref<Record<string, any> | null>(null)
const importTemplates = ref<ImportTemplateItem[]>([])
const selectedTemplateId = ref('')
const templateNameInput = ref('')
const headerRowInput = ref(1)
const dataStartRowInput = ref(2)
const currentStep = ref(1)
const activeImportRunFilter = ref('all')
const activeDryRunDedupRiskOnly = ref(false)
const linkedSummaryPage = ref(1)
const busyAction = ref('')
const cancelRequested = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const recentSessions = ref<Record<string, any>[]>([])
const currentView = ref<'wizard' | 'history'>('wizard')
const importerPermissionState = computed(() => buildImporterPermissionState({
  role: userStore.importerRole,
  permissions: userStore.importerPermissions,
  isPortalAdmin: userStore.importerIsPortalAdmin,
}))

const historyRows = computed(() => buildSessionHistoryRows(recentSessions.value))
const fileName = computed(() => selectedFile.value?.name || '')
const sourceFormat = computed(() => detectSourceFormat(fileName.value))
const scenarioSections = computed(() => buildImportScenarioSections())
const crmScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'crm')?.items || [])
const taskScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'task')?.items || [])
const linkedScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'linked')?.items || [])
const hrScenarioItems = computed(() => scenarioSections.value.find((section) => section.id === 'hr')?.items || [])
const currentScenarioSummary = computed(() => buildScenarioSelectionSummary(entityType.value))
const isTaskEntityImport = computed(() => entityType.value === 'task')
const exampleTemplateDownloadMeta = computed(() => buildExampleTemplateDownloadMeta(entityType.value))
const currentImportTitle = computed(() => 'Excel Migration')
const selectedFamily = ref('')
const selectedCrmEntityType = ref('')
const selectedTaskEntityType = ref('')
const selectedLinkedEntityType = ref('')
const selectedHrEntityType = ref('')
const departments = ref<{ id: string, name: string, parent_id: string | null }[]>([])
const loadingDepartments = ref(false)
const departmentsExpanded = ref(false)
const fieldOptions = computed(() => Array.isArray(mappingData.value?.fields) ? mappingData.value.fields : [])
const fieldOptionsIndex = computed(() => new Map(
  fieldOptions.value
    .filter((field: Record<string, any>) => String(field?.id || '').trim().length > 0)
    .map((field: Record<string, any>) => [String(field.id || ''), field]),
))
const previewRows = computed(() => Array.isArray(preview.value?.preview_rows) ? preview.value.preview_rows : [])
const previewColumnsSource = computed(() => Array.isArray(preview.value?.columns) ? preview.value.columns : [])
const mappingSavedCount = computed(() => (
  mappingData.value?.saved_mapping && typeof mappingData.value.saved_mapping === 'object'
    ? Object.keys(mappingData.value.saved_mapping).length
    : 0
))
const requiredFieldSummary = computed(() => buildRequiredFieldSummary({
  fields: mappingData.value?.fields,
  mappingRows: mappingRows.value,
  defaultFieldIds: [
    ...(taskDefaultResponsibleId.value ? ['RESPONSIBLE_ID'] : []),
    ...(taskDefaultCommentAuthorId.value ? ['AUTHOR_ID'] : []),
  ],
  ignoreFieldIds: entityType.value === 'contact' ? ['SECOND_NAME'] : [],
}))
const requiredFieldMissingIds = computed(() => new Set(
  requiredFieldSummary.value.missingRequired.map((field) => field.id),
))
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
const dryRunCheckedRows = computed(() => Number(dryRunData.value?.checked_rows || 0))
const dryRunReadyRows = computed(() => Number(dryRunData.value?.ready_rows || 0))
const dryRunSkippedRows = computed(() => Number(dryRunData.value?.skipped_rows || 0))
const importRunCheckedRows = computed(() => Number(importRunData.value?.checked_rows || 0))
const importRunCreatedRows = computed(() => Number(importRunData.value?.created_rows || 0))
const importRunUpdatedRows = computed(() => Number(importRunData.value?.updated_rows || 0))
const importRunFailedRows = computed(() => Number(importRunData.value?.failed_rows || 0))
const importRunSkippedRows = computed(() => Number(importRunData.value?.skipped_rows || 0))
const importRunRetryState = computed(() => buildImportRunRetryState(importRunData.value))
const canStart = computed(() => (
  importerPermissionState.value.canCreateSessions
  && Boolean(entityType.value)
  && Boolean(selectedFile.value)
  && Boolean(sourceFormat.value)
  && !busyAction.value
))
const canDownloadExampleTemplate = computed(() => (
  importerPermissionState.value.canCreateSessions
  && Boolean(entityType.value)
  && !busyAction.value
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
const canRunValidation = computed(() => (
  importerPermissionState.value.canRunSessions
  && Boolean(session.value?.id)
  && mappingSavedCount.value > 0
  && !unmappedValueSummary.value.hasUnmappedValues
  && !busyAction.value
))
const canRunDryRun = computed(() => (
  importerPermissionState.value.canRunSessions
  && Boolean(session.value?.id)
  && Boolean(validationData.value)
  && !busyAction.value
))
const canRunImport = computed(() => (
  importerPermissionState.value.canRunSessions
  && Boolean(session.value?.id)
  && Boolean(validationData.value)
  && !busyAction.value
))
const canCancelActiveImport = computed(() => (
  importerPermissionState.value.canCancelSessions
  && Boolean(session.value?.id)
  && !cancelRequested.value
  && ['run', 'retry'].includes(String(busyAction.value || '').trim())
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

  if (validationData.value) {
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
const progressPercent = computed(() => Math.round((currentStep.value / 7) * 100))
const footerStatusLabel = computed(() => {
  if (cancelRequested.value) {
    return 'Останавливаем импорт'
  }

  if (busyAction.value === 'start') {
    return 'Загружаем файл'
  }

  if (busyAction.value === 'structure') {
    return 'Обновляем структуру'
  }

  if (busyAction.value === 'mapping') {
    return 'Сохраняем соответствие'
  }

  if (busyAction.value === 'template-save') {
    return 'Сохраняем шаблон'
  }

  if (busyAction.value === 'template-apply') {
    return 'Применяем шаблон'
  }

  if (busyAction.value === 'dedup') {
    return 'Сохраняем правила дублей'
  }

  if (busyAction.value === 'validation') {
    return 'Проверяем данные'
  }

  if (busyAction.value === 'dry-run') {
    return 'Готовим тестовый импорт'
  }

  if (busyAction.value === 'run') {
    return 'Запускаем импорт'
  }

  if (busyAction.value === 'retry') {
    return 'Повторяем неуспешные строки'
  }

  if (busyAction.value === 'report') {
    return 'Готовим CSV-отчет'
  }

  if (busyAction.value === 'example-template') {
    return 'Готовим Excel-шаблон'
  }

  if (importRunData.value?.cancelled) {
    return `Остановлено. Не запущено строк: ${Number(importRunData.value?.remaining_rows || 0)}`
  }

  if (importRunData.value) {
    return importRunFailedRows.value > 0
      ? `Неуспешных строк: ${importRunFailedRows.value}`
      : importRunUpdatedRows.value > 0
        ? `Создано: ${importRunCreatedRows.value}, обновлено: ${importRunUpdatedRows.value}`
        : `Создано строк: ${importRunCreatedRows.value}`
  }

  if (validationData.value) {
    return validationIssueCount.value > 0
      ? `Найдено ошибок: ${validationIssueCount.value}`
      : 'Проверка завершена'
  }

  if (mappingSavedCount.value > 0) {
    if (unmappedValueSummary.value.hasUnmappedValues) {
      return `Нужно сопоставить значений: ${unmappedValueSummary.value.totalValues}`
    }

    return `Сохранено полей: ${mappingSavedCount.value}`
  }

  return `Этап ${currentStep.value} из 7`
})
const currentStepMeta = computed(() => {
  const items: Record<number, { eyebrow: string, title: string }> = {
    1: {
      eyebrow: 'Шаг 1 · Настройки',
      title: 'Файл и назначение',
    },
    2: {
      eyebrow: 'Шаг 2 · Структура',
      title: 'Параметры чтения файла',
    },
    3: {
      eyebrow: 'Шаг 3 · Предпросмотр',
      title: 'Пример файла',
    },
    4: {
      eyebrow: 'Шаг 4 · Соответствие',
      title: 'Соответствие полей',
    },
    5: {
      eyebrow: 'Шаг 5 · Дубли',
      title: 'Обработка дублей',
    },
    6: {
      eyebrow: 'Шаг 6 · Проверка',
      title: 'Проверка данных',
    },
    7: {
      eyebrow: 'Шаг 7 · Результат',
      title: 'Результат импорта',
    },
  }

  return items[currentStep.value] || items[1]
})
const canGoBack = computed(() => currentStep.value > 1)
const wizardAdvanceMode = computed(() => getWizardAdvanceMode(currentStep.value, maxAvailableStep.value))
const canGoNext = computed(() => canAdvanceWizard(currentStep.value, maxAvailableStep.value, {
  hasMissingRequiredFields: requiredFieldSummary.value.hasMissingRequired,
}))
const showInlineWizardFooter = computed(() => shouldRenderInlineWizardFooter(currentStep.value))
const nextStepLabel = computed(() => getWizardNextLabel(currentStep.value))
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
      title: 'Проверка',
      description: 'Проверка и тест',
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
const sidebarFacts = computed(() => {
  return [
    { label: currentScenarioSummary.value.family === 'task' ? 'Сценарий' : 'Назначение', value: currentScenarioSummary.value.selectedLabel },
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
const dedupStrategyItems = [
  { value: 'create', label: 'Всегда создавать' },
  { value: 'update', label: 'Обновлять найденный дубль' },
  { value: 'skip', label: 'Пропускать дубль' },
]
const dedupFieldOptions = computed(() => {
  const labels: Record<string, string> = {
    EMAIL: 'Email',
    PHONE: 'Телефон',
    TITLE: 'Название / заголовок',
  }
  const supportedFields = new Set(['EMAIL', 'PHONE', 'TITLE'])
  const selectedFields = new Set(
    mappingRows.value
      .map((row) => normalizeMappingSelectValue(row.targetFieldId))
      .filter((fieldId) => supportedFields.has(fieldId)),
  )

  return Array.from(selectedFields).map((fieldId) => ({
    id: fieldId,
    label: labels[fieldId] || fieldId,
  }))
})
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
  savedMapping: mappingData.value?.saved_mapping,
}))
const valueMappingStatus = computed(() => buildValueMappingStatus(valueMappingRows.value))
const validationIssueRows = computed<ValidationIssueRow[]>(() => buildValidationIssueRows(validationData.value))
const dryRunRows = computed<DryRunRow[]>(() => buildDryRunRows(dryRunData.value))
const importRunRows = computed<ImportRunRow[]>(() => buildImportRunRows(importRunData.value))
const linkedImportRunSummary = computed(() => buildLinkedImportRunSummary(importRunData.value))
const linkedSummaryPageCount = computed(() => (
  linkedImportRunSummary.value.sections.reduce((maxPageCount, section) => Math.max(maxPageCount, section.pageCount || 1), 1)
))
const dryRunDedupWeakeningNotice = computed(() => buildDedupWeakeningNotice(dryRunData.value))
const importRunDedupWeakeningNotice = computed(() => buildDedupWeakeningNotice(importRunData.value))
const filteredDryRunRows = computed<DryRunRow[]>(() => (
  activeDryRunDedupRiskOnly.value
    ? dryRunRows.value.filter((row) => dryRunDedupWeakeningNotice.value.rowNumbers.includes(row.rowNumber))
    : dryRunRows.value
))
const importRunStatusFilters = computed<ImportRunFilterItem[]>(() => (
  buildImportRunStatusFilters(importRunData.value).filter((item) => item.count > 0)
))
const importRunProblemGroups = computed<ImportRunProblemGroup[]>(() => buildImportRunProblemGroups(importRunData.value))
const filteredImportRunRows = computed<ImportRunRow[]>(() => (
  filterImportRunRows(importRunRows.value, activeImportRunFilter.value)
))
const isLinkedCompanyContactImport = computed(() => entityType.value === 'linked_company_contact')
const stepSixStatusLabel = computed(() => {
  if (dryRunData.value) {
    return dryRunSkippedRows.value > 0
      ? `Пропусков: ${dryRunSkippedRows.value}`
      : `Готово строк: ${dryRunReadyRows.value}`
  }

  return validationIssueCount.value > 0
    ? `Ошибок: ${validationIssueCount.value}`
    : 'Ошибок не найдено'
})
const stepSixMetricCards = computed(() => {
  if (dryRunData.value) {
    return [
      { label: 'Проверено', value: dryRunCheckedRows.value },
      { label: 'К записи', value: dryRunReadyRows.value },
      { label: 'Пропущено', value: dryRunSkippedRows.value },
    ]
  }

  return [
    { label: 'Проверено', value: validationCheckedRows.value },
    { label: 'Без ошибок', value: validationValidRows.value },
    { label: 'С ошибками', value: validationInvalidRows.value },
  ]
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
const importRunTableColumns = computed(() => [
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
    accessorKey: 'statusLabel',
    header: 'Статус',
    meta: {
      class: {
        th: 'w-[140px]',
      },
    },
  },
  {
    accessorKey: 'recordId',
    header: 'ID в Bitrix24',
    meta: {
      class: {
        th: 'w-[140px]',
      },
    },
  },
  {
    accessorKey: 'details',
    header: 'Детали',
    meta: {
      class: {
        th: 'min-w-[320px]',
      },
    },
  },
])
const dryRunTableColumns = computed(() => [
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
    accessorKey: 'statusLabel',
    header: 'Статус',
    meta: {
      class: {
        th: 'w-[140px]',
      },
    },
  },
  {
    accessorKey: 'details',
    header: 'Что уйдет в Bitrix24',
    meta: {
      class: {
        th: 'min-w-[360px]',
      },
    },
  },
])

watch(maxAvailableStep, (value) => {
  if (currentStep.value > value) {
    currentStep.value = value
  }
})

watch(importRunData, (value) => {
  activeImportRunFilter.value = resolveImportRunFilterId(value, activeImportRunFilter.value)
}, { immediate: true })

watch(dryRunData, (value) => {
  if (!buildDedupWeakeningNotice(value).hasWarnings) {
    activeDryRunDedupRiskOnly.value = false
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

function resetFlowState() {
  session.value = null
  preview.value = null
  mappingData.value = null
  mappingRows.value = []
  dedupStrategy.value = 'create'
  dedupFields.value = []
  validationData.value = null
  dryRunData.value = null
  importRunData.value = null
  importTemplates.value = []
  selectedTemplateId.value = ''
  templateNameInput.value = ''
  headerRowInput.value = 1
  dataStartRowInput.value = 2
  activeImportRunFilter.value = 'all'
  linkedSummaryPage.value = 1
  cancelRequested.value = false
}

function finishImporterFlow() {
  resetFlowState()
  selectedFile.value = null
  currentStep.value = 1

  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }

  setSuccess('Импорт завершен. Можно начать новый импорт.')
  loadHistory()
}

function syncDedupSettings() {
  const payload = buildDedupPayload(mappingData.value?.saved_dedup || {})
  dedupStrategy.value = payload.strategy
  dedupFields.value = payload.fields
}

function syncMappingRows() {
  if (!mappingData.value) {
    mappingRows.value = []
    taskDefaultResponsibleId.value = ''
    taskDefaultCommentAuthorId.value = ''
    dedupStrategy.value = 'create'
    dedupFields.value = []
    return
  }

  mappingRows.value = buildMappingRows({
    headers: mappingData.value.headers,
    columns: mappingData.value.columns,
    fields: mappingData.value.fields,
    candidateMapping: mappingData.value.candidate_mapping,
    savedMapping: mappingData.value.saved_mapping,
  })
  taskDefaultResponsibleId.value = String(mappingData.value?.task_defaults?.default_responsible_id || '')
  taskDefaultCommentAuthorId.value = String(mappingData.value?.task_defaults?.default_comment_author_id || '')
  syncDedupSettings()
}

watch(dedupStrategy, (value) => {
  if (value === 'create') {
    dedupFields.value = []
  }
})

watch(entityType, (value) => {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) {
    return
  }

  if (crmScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedCrmEntityType.value = normalizedValue
    selectedTaskEntityType.value = ''
    selectedLinkedEntityType.value = ''
    selectedHrEntityType.value = ''
  }

  if (taskScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedTaskEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedLinkedEntityType.value = ''
    selectedHrEntityType.value = ''
  }

  if (linkedScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedLinkedEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedHrEntityType.value = ''
  }

  if (hrScenarioItems.value.some((item) => item.value === normalizedValue)) {
    selectedHrEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedLinkedEntityType.value = ''
  }
}, { immediate: true })

watch(dedupFieldOptions, (options) => {
  const allowed = new Set(options.map((option) => option.id))
  dedupFields.value = dedupFields.value.filter((field) => allowed.has(field))
})

watch(linkedImportRunSummary, () => {
  linkedSummaryPage.value = 1
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

function buildVisibleLinkedSummaryItems(section: LinkedImportSummarySection): LinkedImportSummaryItem[] {
  const page = Math.min(linkedSummaryPage.value, Math.max(1, section.pageCount || 1))
  const startIndex = (page - 1) * section.pageSize
  return section.items.slice(startIndex, startIndex + section.pageSize)
}

function selectFamily(family: string) {
  selectedFamily.value = family
  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedLinkedEntityType.value = ''
  selectedHrEntityType.value = ''
  entityType.value = ''
  departmentsExpanded.value = false
  resetMessages()
}

function goBackToFamilySelection() {
  selectedFamily.value = ''
  selectedCrmEntityType.value = ''
  selectedTaskEntityType.value = ''
  selectedLinkedEntityType.value = ''
  selectedHrEntityType.value = ''
  entityType.value = ''
  departmentsExpanded.value = false
  resetMessages()
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

function updateScenarioEntityType(family: 'crm' | 'task' | 'linked' | 'hr', value: string) {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) {
    return
  }

  if (family === 'crm') {
    selectedCrmEntityType.value = normalizedValue
    selectedTaskEntityType.value = ''
    selectedLinkedEntityType.value = ''
    selectedHrEntityType.value = ''
  } else if (family === 'task') {
    selectedTaskEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedLinkedEntityType.value = ''
    selectedHrEntityType.value = ''
  } else if (family === 'linked') {
    selectedLinkedEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedHrEntityType.value = ''
  } else {
    selectedHrEntityType.value = normalizedValue
    selectedCrmEntityType.value = ''
    selectedTaskEntityType.value = ''
    selectedLinkedEntityType.value = ''
  }

  selectedFamily.value = family === 'linked' ? 'crm' : family
  entityType.value = normalizedValue
  resetMessages()
}

async function refreshMapping() {
  if (!session.value?.id) {
    return
  }

  const response = await apiStore.getImportMapping(String(session.value.id))
  mappingData.value = response.item
  validationData.value = null
  dryRunData.value = null
  importRunData.value = null
  syncMappingRows()
  await refreshTemplates()
}

async function refreshTemplates() {
  const response = await apiStore.getImportTemplates(entityType.value)
  importTemplates.value = (Array.isArray(response.items) ? response.items : []).map((item: Record<string, any>) => ({
    id: String(item.id || ''),
    name: String(item.name || ''),
  })).filter((item) => item.id && item.name)

  if (selectedTemplateId.value && !importTemplates.value.find((item) => item.id === selectedTemplateId.value)) {
    selectedTemplateId.value = ''
  }
}

function openFilePicker() {
  if (!importerPermissionState.value.canCreateSessions || busyAction.value) {
    return
  }

  fileInputRef.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0] || null
  resetMessages()
  dryRunData.value = null
  importRunData.value = null
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

  if (!sourceFormat.value) {
    setError('Можно загрузить только файлы .xlsx, .xls или .csv.')
    return
  }

  busyAction.value = 'start'
  resetFlowState()
  currentStep.value = 1

  try {
    const createResponse = await apiStore.createImportSession({
      entity_type: entityType.value,
      source_format: sourceFormat.value,
      original_filename: selectedFile.value.name,
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
  importRunData.value = null
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
      buildDedupPayload({
        strategy: dedupStrategy.value,
        fields: dedupFields.value,
      }),
      {
        default_responsible_id: taskDefaultResponsibleId.value,
        default_comment_author_id: taskDefaultCommentAuthorId.value,
      },
    )
    mappingData.value = response.item
    validationData.value = null
    dryRunData.value = null
    importRunData.value = null
    syncMappingRows()
    setSuccess(
      Number(response.item?.unmapped_value_count || 0) > 0
        ? `Соответствие полей сохранено. Осталось сопоставить значений: ${Number(response.item?.unmapped_value_count || 0)}.`
        : 'Соответствие полей сохранено.',
    )
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
    const response = await apiStore.saveImportMapping(
      String(session.value.id),
      buildMappingPayload(mappingRows.value),
      buildDedupPayload({
        strategy: dedupStrategy.value,
        fields: dedupFields.value,
      }),
      {
        default_responsible_id: taskDefaultResponsibleId.value,
        default_comment_author_id: taskDefaultCommentAuthorId.value,
      },
    )
    mappingData.value = response.item
    dryRunData.value = null
    importRunData.value = null
    syncMappingRows()
    setSuccess('Правила обработки дублей сохранены.')
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
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
      buildDedupPayload({
        strategy: dedupStrategy.value,
        fields: dedupFields.value,
      }),
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

async function runValidation() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  if (unmappedValueSummary.value.hasUnmappedValues) {
    setError('Сначала сопоставьте все значения статусов и списков.')
    return
  }
  busyAction.value = 'validation'

  try {
    const response = await apiStore.validateImportSession(String(session.value.id))
    validationData.value = response.item
    dryRunData.value = null
    activeDryRunDedupRiskOnly.value = false
    importRunData.value = null
    currentStep.value = 6
    setSuccess(
      validationIssueCount.value > 0
        ? 'Проверка завершена. Исправьте строки с ошибками перед следующим этапом.'
        : 'Проверка завершена. Критичных ошибок не найдено.',
    )
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function runDryRun() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  busyAction.value = 'dry-run'

  try {
    const response = await apiStore.dryRunImportSession(String(session.value.id))
    dryRunData.value = response.item
    activeDryRunDedupRiskOnly.value = false
    importRunData.value = null
    currentStep.value = 6
    setSuccess(
      dryRunSkippedRows.value > 0
        ? 'Тестовый импорт завершен. Часть строк будет пропущена.'
        : 'Тестовый импорт завершен. Можно запускать импорт.',
    )
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    busyAction.value = ''
  }
}

async function runImport() {
  if (!session.value?.id) {
    return
  }

  resetMessages()
  cancelRequested.value = false
  busyAction.value = 'run'
  session.value = session.value ? { ...session.value, status: 'running' } : session.value

  try {
    const response = await apiStore.runImportSession(String(session.value.id))
    importRunData.value = response.item
    session.value = session.value ? { ...session.value, status: response.item.status } : session.value
    currentStep.value = 7
    setSuccess(
      response.item?.status === 'cancelled'
        ? `Импорт остановлен. Не запущено строк: ${Number(response.item?.remaining_rows || 0)}.`
        : importRunFailedRows.value > 0
        ? 'Импорт завершен. Часть строк требует внимания.'
        : 'Импорт завершен. Все строки обработаны.',
    )
  } catch (error) {
    setError(error instanceof Error ? error.message : String(error))
  } finally {
    cancelRequested.value = false
    busyAction.value = ''
  }
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
    importRunData.value = response.item
    session.value = session.value ? { ...session.value, status: response.item.status } : session.value
    currentStep.value = 7
    setSuccess(
      response.item?.status === 'cancelled'
        ? `Повтор остановлен. Не запущено строк: ${Number(response.item?.remaining_rows || 0)}.`
        : Number(response.item?.failed_rows || 0) > 0
        ? `Повтор выполнен. Осталось неуспешных строк: ${Number(response.item?.failed_rows || 0)}.`
        : `Повтор выполнен. Обработано строк: ${Number(response.item?.retried_rows || 0)}.`,
    )
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
    setSuccess('Остановка запрошена. Текущая строка завершится, после чего импорт остановится.')
  } catch (error) {
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
    const { blob, filename } = await apiStore.downloadImportExampleTemplateXlsx(entityType.value)
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
  try {
    const response = await apiStore.listImportSessions()
    recentSessions.value = Array.isArray(response?.items) ? response.items : []
  } catch {
    // silently ignore history load failures
  }
}

onMounted(loadHistory)

</script>

<template>
  <section class="w-full min-w-0">
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
          v-if="historyRows.length === 0"
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
            class="rounded-[20px] border border-[#e3e9f0] bg-[#fbfcfe] px-5 py-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="truncate text-sm font-semibold text-[#2f4254]">
                  {{ row.fileName }}
                </div>
                <div class="mt-1 text-xs text-[#8ea0b2]">
                  {{ row.entityType }}
                </div>
              </div>
              <span
                class="shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold"
                :class="{
                  'bg-[#eefaf3] text-[#2b7a4b]': row.resultTone === 'success',
                  'bg-[#fff1f1] text-[#c24b53]': row.resultTone === 'danger',
                  'bg-[#fff8ec] text-[#a0610a]': row.resultTone === 'warning',
                  'bg-[#eef6ff] text-[#2e6bd9]': row.resultTone === 'info',
                  'bg-[#f2f5f9] text-[#6e8193]': row.resultTone === 'neutral',
                }"
              >{{ row.resultLabel }}</span>
            </div>
            <div class="mt-3 flex flex-wrap items-center gap-4">
              <div class="rounded-[12px] border border-[#e5ebf2] bg-white px-3 py-2">
                <div class="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#9aa9b8]">
                  Статус
                </div>
                <div class="mt-0.5 text-sm font-medium text-[#314256]">
                  {{ row.statusLabel }}
                </div>
              </div>
              <div class="rounded-[12px] border border-[#e5ebf2] bg-white px-3 py-2">
                <div class="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#9aa9b8]">
                  Результат
                </div>
                <div class="mt-0.5 text-sm font-medium text-[#314256]">
                  {{ row.counters }}
                </div>
              </div>
              <div class="rounded-[12px] border border-[#e5ebf2] bg-white px-3 py-2">
                <div class="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#9aa9b8]">
                  Обновлено
                </div>
                <div class="mt-0.5 text-sm font-medium text-[#314256]">
                  {{ row.updatedAtLabel }}
                </div>
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
          <div class="space-y-4">
            <div class="px-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
              Этапы
            </div>

            <div class="space-y-3">
              <button
                v-for="(step, index) in importSteps"
                :key="step.id"
                type="button"
                class="relative flex w-full gap-3 rounded-[18px] px-3 py-3 text-left transition duration-150"
                :class="{
                  'bg-white shadow-[0_10px_26px_rgba(30,80,150,0.08)]': step.state === 'current',
                  'bg-[#eff6ff]': step.state === 'done',
                  'bg-transparent hover:bg-white hover:shadow-[0_10px_26px_rgba(30,80,150,0.08)]': step.state === 'upcoming' && step.enabled,
                  'opacity-60': !step.enabled,
                }"
                :disabled="!step.enabled"
                @click="goToStep(step.id)"
              >
                <div
                  v-if="index < importSteps.length - 1"
                  class="absolute left-[32px] top-[44px] h-[34px] w-[2px] -translate-x-1/2 rounded-full"
                  :class="step.state === 'done' ? 'bg-[#8fd0a1]' : 'bg-[#dbe4ed]'"
                />

                <div
                  class="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
                  :class="{
                    'bg-[#2e6bd9] text-white shadow-[0_0_0_6px_rgba(46,107,217,0.12)]': step.state === 'current',
                    'bg-[#dff3e5] text-[#2e8b57]': step.state === 'done',
                    'bg-white text-[#93a1af] border border-[#dde5ee]': step.state === 'upcoming',
                  }"
                >
                  {{ step.id }}
                </div>

                <div class="min-w-0 pt-1">
                  <div
                    class="text-sm font-semibold"
                    :class="{
                      'text-[#2f4254]': step.state !== 'upcoming',
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
        <div class="border-b border-[#e5ebf1] bg-[linear-gradient(180deg,#ffffff_0%,#f9fbfe_100%)] px-6 py-5 sm:px-8">
          <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="min-w-0">
              <div class="text-xs font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">
                {{ currentStepMeta.eyebrow }}
              </div>
              <h1 class="mt-2 text-[30px] font-semibold leading-[1.08] text-[#2f4254]">
                {{ currentImportTitle }}
              </h1>
              <div class="mt-3 flex flex-wrap items-center gap-3 text-sm text-[#6c8093]">
                <span class="font-medium text-[#506476]">Текущий статус</span>
                <span
                  class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold"
                  :class="{
                    'bg-[#f2f5f9] text-[#6e8193]': migrationStatusBadge.tone === 'idle',
                    'bg-[#eef6ff] text-[#2e6bd9]': migrationStatusBadge.tone === 'busy',
                    'bg-[#eefaf3] text-[#2b7a4b]': migrationStatusBadge.tone === 'ok',
                    'bg-[#fff1f1] text-[#c24b53]': migrationStatusBadge.tone === 'error',
                  }"
                >
                  {{ migrationStatusBadge.label }}
                </span>
              </div>
              <div
                v-if="headerNotice"
                class="mt-3 flex flex-wrap items-center gap-3 text-sm"
              >
                <span
                  class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold"
                  :class="headerNotice.tone === 'error'
                    ? 'bg-[#fff1f1] text-[#c24b53]'
                    : 'bg-[#eefaf3] text-[#2b7a4b]'"
                >
                  {{ headerNotice.label }}
                </span>
                <span class="text-[#667b8f]">
                  {{ headerNotice.message }}
                </span>
              </div>
            </div>

            <div class="flex shrink-0 flex-col items-end gap-3">
              <B24Button
                label="История"
                color="air-primary"
                size="lg"
                @click="currentView = 'history'"
              />
              <div class="flex flex-wrap justify-end gap-2">
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
            v-if="currentStep === 1"
            class="space-y-6"
          >
            <div class="space-y-6">
              <section class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
                <div class="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 1</div>
                    <h2 class="mt-1 text-xl font-semibold text-[#314256]">
                      {{ selectedFamily ? 'Источник и назначение' : 'Выберите тип импорта' }}
                    </h2>
                  </div>
                  <div class="flex items-center gap-2">
                    <B24Button
                      v-if="selectedFamily"
                      label="← Назад"
                      color="air-tertiary"
                      size="lg"
                      :disabled="Boolean(busyAction)"
                      @click="goBackToFamilySelection"
                    />
                    <B24Button
                      v-if="selectedFamily"
                      label="Загрузить файл"
                      color="air-primary"
                      size="lg"
                      :loading="busyAction === 'start'"
                      :disabled="!canStart"
                      @click="startImporterSetup"
                    />
                  </div>
                </div>

                <!-- Выбор категории -->
                <div v-if="!selectedFamily" class="grid gap-4 sm:grid-cols-3">
                  <button
                    type="button"
                    class="flex flex-col gap-3 rounded-[18px] border border-[#e5ebf2] bg-white p-5 text-left transition hover:border-[#c2d4f0] hover:bg-[#f4f9ff]"
                    :disabled="!importerPermissionState.canCreateSessions"
                    @click="selectFamily('crm')"
                  >
                    <div class="text-base font-semibold text-[#2f4254]">CRM-сущности</div>
                    <div class="text-sm text-[#6c8093]">Лиды, контакты, компании, сделки и связанный импорт.</div>
                  </button>
                  <button
                    type="button"
                    class="flex flex-col gap-3 rounded-[18px] border border-[#e5ebf2] bg-white p-5 text-left transition hover:border-[#c2d4f0] hover:bg-[#f4f9ff]"
                    :disabled="!importerPermissionState.canCreateSessions"
                    @click="selectFamily('task')"
                  >
                    <div class="text-base font-semibold text-[#2f4254]">Задачи</div>
                    <div class="text-sm text-[#6c8093]">Задачи, подзадачи, комментарии, чек-листы и вложения.</div>
                  </button>
                  <button
                    type="button"
                    class="flex flex-col gap-3 rounded-[18px] border border-[#e5ebf2] bg-white p-5 text-left transition hover:border-[#c2d4f0] hover:bg-[#f4f9ff]"
                    :disabled="!importerPermissionState.canCreateSessions"
                    @click="selectFamily('hr')"
                  >
                    <div class="text-base font-semibold text-[#2f4254]">Пользователи и отделы</div>
                    <div class="text-sm text-[#6c8093]">Сотрудники портала и структура компании.</div>
                  </button>
                </div>

                <!-- CRM подэкран -->
                <div v-else-if="selectedFamily === 'crm'" class="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                  <div class="space-y-4">
                    <section class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                      <div class="text-sm font-semibold text-[#314256]">CRM-сущности</div>
                      <div class="mt-1 text-sm text-[#6f8194]">Прямой импорт в стандартные CRM-разделы.</div>
                      <B24FormField label="Выберите CRM-сущность" class="mt-4">
                        <B24Select
                          :model-value="selectedCrmEntityType"
                          :items="crmScenarioItems"
                          placeholder="Например, Сделки"
                          size="lg"
                          class="w-full"
                          :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                          @update:model-value="updateScenarioEntityType('crm', String($event || ''))"
                        />
                      </B24FormField>
                    </section>
                    <section class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                      <div class="text-sm font-semibold text-[#314256]">Связанный импорт</div>
                      <div class="mt-1 text-sm text-[#6f8194]">Одна строка Excel создаёт и связывает несколько сущностей.</div>
                      <B24FormField label="Выберите связанный сценарий" class="mt-4">
                        <B24Select
                          :model-value="selectedLinkedEntityType"
                          :items="linkedScenarioItems"
                          placeholder="Например, Компания + Контакт"
                          size="lg"
                          class="w-full"
                          :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)"
                          @update:model-value="updateScenarioEntityType('linked', String($event || ''))"
                        />
                      </B24FormField>
                    </section>
                  </div>
                  <div class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                    <B24FormField label="Файл для импорта" class="w-full">
                      <input ref="fileInputRef" type="file" accept=".xlsx,.xls,.csv" class="hidden" @change="handleFileChange">
                      <div class="space-y-4">
                        <div class="rounded-[16px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-4">
                          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Файл</div>
                          <div class="truncate text-sm font-medium text-[#314256]">{{ fileName || 'Файл еще не выбран' }}</div>
                          <div class="mt-1 text-sm text-[#7f8d9c]">Поддерживаются форматы Excel и CSV</div>
                        </div>
                        <B24Button label="Выбрать файл" color="air-primary" size="lg" class="w-full" :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)" @click="openFilePicker" />
                        <div class="rounded-[16px] border border-[#dce7f7] bg-[#f7fbff] px-4 py-4">
                          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаблон</div>
                          <div class="mt-2 text-sm font-medium text-[#314256]">{{ exampleTemplateDownloadMeta.title }}</div>
                          <div class="mt-1 text-xs text-[#7f92a7]">{{ exampleTemplateDownloadMeta.description }}</div>
                        </div>
                        <B24Button label="Скачать шаблон Excel" color="air-secondary-accent-2" size="lg" class="w-full" :loading="busyAction === 'example-template'" :disabled="!canDownloadExampleTemplate" @click="downloadExampleTemplate" />
                      </div>
                    </B24FormField>
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
                  </div>
                  <div class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                    <B24FormField label="Файл для импорта" class="w-full">
                      <input ref="fileInputRef" type="file" accept=".xlsx,.xls,.csv" class="hidden" @change="handleFileChange">
                      <div class="space-y-4">
                        <div class="rounded-[16px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-4">
                          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Файл</div>
                          <div class="truncate text-sm font-medium text-[#314256]">{{ fileName || 'Файл еще не выбран' }}</div>
                          <div class="mt-1 text-sm text-[#7f8d9c]">Поддерживаются форматы Excel и CSV</div>
                        </div>
                        <B24Button label="Выбрать файл" color="air-primary" size="lg" class="w-full" :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)" @click="openFilePicker" />
                        <div class="rounded-[16px] border border-[#dce7f7] bg-[#f7fbff] px-4 py-4">
                          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаблон</div>
                          <div class="mt-2 text-sm font-medium text-[#314256]">{{ exampleTemplateDownloadMeta.title }}</div>
                          <div class="mt-1 text-xs text-[#7f92a7]">{{ exampleTemplateDownloadMeta.description }}</div>
                        </div>
                        <B24Button label="Скачать шаблон Excel" color="air-secondary-accent-2" size="lg" class="w-full" :loading="busyAction === 'example-template'" :disabled="!canDownloadExampleTemplate" @click="downloadExampleTemplate" />
                      </div>
                    </B24FormField>
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

                  <div class="rounded-[18px] border border-[#e5ebf2] bg-white p-4">
                    <B24FormField label="Файл для импорта" class="w-full">
                      <input ref="fileInputRef" type="file" accept=".xlsx,.xls,.csv" class="hidden" @change="handleFileChange">
                      <div class="space-y-4">
                        <div class="rounded-[16px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-4">
                          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Файл</div>
                          <div class="truncate text-sm font-medium text-[#314256]">{{ fileName || 'Файл еще не выбран' }}</div>
                          <div class="mt-1 text-sm text-[#7f8d9c]">Поддерживаются форматы Excel и CSV</div>
                        </div>
                        <B24Button label="Выбрать файл" color="air-primary" size="lg" class="w-full" :disabled="!importerPermissionState.canCreateSessions || Boolean(busyAction)" @click="openFilePicker" />
                        <div class="rounded-[16px] border border-[#dce7f7] bg-[#f7fbff] px-4 py-4">
                          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаблон</div>
                          <div class="mt-2 text-sm font-medium text-[#314256]">{{ exampleTemplateDownloadMeta.title }}</div>
                          <div class="mt-1 text-xs text-[#7f92a7]">{{ exampleTemplateDownloadMeta.description }}</div>
                        </div>
                        <B24Button label="Скачать шаблон Excel" color="air-secondary-accent-2" size="lg" class="w-full" :loading="busyAction === 'example-template'" :disabled="!canDownloadExampleTemplate" @click="downloadExampleTemplate" />
                      </div>
                    </B24FormField>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <section v-if="currentStep === 2" class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
            <div class="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 2</div>
                <h2 class="mt-1 text-xl font-semibold text-[#314256]">Параметры чтения файла</h2>
              </div>

              <B24Button
                label="Применить"
                color="air-primary"
                size="lg"
                :loading="busyAction === 'structure'"
                :disabled="!canApplyStructure"
                @click="applyStructure"
              />
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
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Строки</div>
                  <div class="mt-1 text-lg font-semibold text-[#314256]">{{ previewRows.length || 0 }}</div>
                </div>
                <div class="rounded-[18px] border border-[#e5ebf2] bg-white px-4 py-4 text-sm text-[#5f7285]">
                  <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Лист</div>
                  <div class="mt-1 truncate text-lg font-semibold text-[#314256]">{{ preview?.selected_sheet_name || '—' }}</div>
                </div>
              </div>
            </div>

            <div
              v-if="showInlineWizardFooter"
              class="mt-6 rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f7fbff_0%,#eef5ff_100%)] px-4 py-4 sm:px-5"
            >
              <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                <div class="min-w-0 flex-1 xl:max-w-[460px]">
                  <div class="mb-2 flex items-center justify-between gap-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                    <span>Прогресс</span>
                    <span>{{ currentStep }} / 7</span>
                  </div>
                  <div class="h-2 rounded-full bg-[#e6edf5]">
                    <div
                      class="h-2 rounded-full bg-[linear-gradient(90deg,#2e6bd9_0%,#41b7ff_100%)] transition-all duration-300"
                      :style="{ width: `${progressPercent}%` }"
                    />
                  </div>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                  <div class="rounded-full border border-[#d7e7ff] bg-white/85 px-3 py-1.5 text-sm font-medium text-[#2e6bd9]">
                    {{ footerStatusLabel }}
                  </div>

                  <B24Button
                    label="Назад"
                    color="air-tertiary"
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
            </div>
          </section>

          <section v-if="currentStep === 3" class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5">
            <div class="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 3</div>
                <h2 class="mt-1 text-xl font-semibold text-[#314256]">Пример файла</h2>
              </div>

              <div class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1.5 text-sm font-medium text-[#2e6bd9]">
                {{ previewTableRows.length }} строк в предпросмотре
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

            <div
              v-if="showInlineWizardFooter"
              class="mt-6 rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f7fbff_0%,#eef5ff_100%)] px-4 py-4 sm:px-5"
            >
              <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                <div class="min-w-0 flex-1 xl:max-w-[460px]">
                  <div class="mb-2 flex items-center justify-between gap-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                    <span>Прогресс</span>
                    <span>{{ currentStep }} / 7</span>
                  </div>
                  <div class="h-2 rounded-full bg-[#e6edf5]">
                    <div
                      class="h-2 rounded-full bg-[linear-gradient(90deg,#2e6bd9_0%,#41b7ff_100%)] transition-all duration-300"
                      :style="{ width: `${progressPercent}%` }"
                    />
                  </div>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                  <div class="rounded-full border border-[#d7e7ff] bg-white/85 px-3 py-1.5 text-sm font-medium text-[#2e6bd9]">
                    {{ footerStatusLabel }}
                  </div>

                  <B24Button
                    label="Назад"
                    color="air-tertiary"
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
              </div>
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

            <div class="mb-5 grid gap-4 xl:grid-cols-2">
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
              class="mb-5 rounded-[20px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4"
            >
              <div class="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Маппинг статусов и списков</div>
              <div class="mb-3 text-sm text-[#5f7285]">
                Для полей типа статус, этап или список сопоставьте значения из файла с целевыми значениями Bitrix24.
              </div>
              <div
                class="mb-4 flex flex-wrap items-center gap-3 rounded-[14px] border px-3 py-2 text-sm"
                :class="valueMappingStatus.hasUnmappedValues
                  ? 'border-[#ffe1c7] bg-[#fff7ef] text-[#a96017]'
                  : 'border-[#d7e7ff] bg-[#f4f9ff] text-[#2e6bd9]'"
              >
                <span class="font-semibold">
                  {{ valueMappingStatus.hasUnmappedValues
                    ? `Не сопоставлено: ${valueMappingStatus.unmappedValues}`
                    : 'Все значения сопоставлены' }}
                </span>
                <span class="text-[#6f8194]">
                  {{ `Всего значений: ${valueMappingStatus.totalValues}` }}
                </span>
              </div>

              <div class="space-y-3">
                <div
                  v-for="row in valueMappingRows"
                  :key="row.key"
                  class="grid gap-3 rounded-[16px] border border-white/70 bg-white/85 px-4 py-4 lg:grid-cols-[minmax(180px,1fr),minmax(220px,1fr),minmax(260px,1.2fr)]"
                >
                  <div>
                    <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Поле Bitrix24</div>
                    <div class="mt-1 font-medium text-[#314256]">{{ row.targetFieldTitle }}</div>
                  </div>

                  <div>
                    <div class="text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Значение в файле</div>
                    <div class="mt-1 font-medium text-[#314256]">{{ row.sourceValue }}</div>
                  </div>

                  <div>
                    <div class="mb-2 text-xs uppercase tracking-[0.1em] text-[#9aa9b8]">Значение Bitrix24</div>
                    <B24Select
                      :model-value="row.selectedTargetValue"
                      class="w-full"
                      size="md"
                      placeholder="Не выбрано"
                      :items="[{ value: '', label: 'Не выбрано' }, ...row.options]"
                      @update:model-value="updateValueMappingSelection(row.targetFieldId, row.sourceValue, String($event || ''))"
                    />
                  </div>
                </div>
              </div>
            </section>

            <div class="overflow-hidden rounded-[20px] border border-[#dfe5eb] bg-white">
              <B24Table
                class="w-full"
                :loading="busyAction === 'start' || busyAction === 'structure' || busyAction === 'mapping' || busyAction === 'template-apply'"
                loading-color="air-primary"
                loading-animation="loading"
                :columns="mappingTableColumns"
                :data="mappingRows"
                empty="После загрузки файла здесь появится список колонок для сопоставления."
              >
                <template #targetFieldId-cell="{ row }">
                  <div class="min-w-[260px]">
                    <B24SelectMenu
                      :model-value="resolveMappingSelectValue(row.original.targetFieldId)"
                      class="w-full"
                      size="md"
                      placeholder="Не импортировать"
                      :items="mappingFieldItems"
                      value-key="value"
                      :filter-fields="['label', 'description']"
                      :search-input="{ placeholder: 'Поиск полей...' }"
                      @update:model-value="updateMappingFieldSelection(row.original, String($event || ''))"
                    />

                    <div
                      v-if="row.original.targetFieldId"
                      class="mt-2 flex flex-wrap gap-2"
                    >
                      <span
                        v-if="row.original.autoMatchType"
                        class="rounded-full border border-[#d9e6f5] bg-[#f6f9fd] px-2.5 py-1 text-xs font-medium text-[#58708b]"
                      >
                        {{ row.original.autoMatchLabel || 'Автоподбор' }}
                      </span>
                      <span class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-2.5 py-1 text-xs font-medium text-[#2e6bd9]">
                        {{ row.original.targetFieldTypeLabel || 'Поле' }}
                      </span>
                      <span
                        v-if="row.original.targetFieldRequired"
                        class="rounded-full border border-[#f2d1ac] bg-[#fff8ef] px-2.5 py-1 text-xs font-medium text-[#9a6432]"
                      >
                        Обязательное
                      </span>
                      <span
                        v-if="row.original.targetFieldIsCustom"
                        class="rounded-full border border-[#dcefe1] bg-[#f1fbf4] px-2.5 py-1 text-xs font-medium text-[#2d7a4b]"
                      >
                        Кастомное
                      </span>
                      <span
                        v-if="row.original.targetFieldIsMultiple"
                        class="rounded-full border border-[#efe3cf] bg-[#fff8ef] px-2.5 py-1 text-xs font-medium text-[#9a6432]"
                      >
                        Множественное
                      </span>
                    </div>

                    <div
                      v-if="row.original.targetFieldGuidanceHints?.length"
                      class="mt-2 space-y-1 text-xs text-[#6f8194]"
                    >
                      <div
                        v-for="hint in row.original.targetFieldGuidanceHints"
                        :key="hint"
                      >
                        {{ hint }}
                      </div>
                    </div>
                  </div>
                </template>
              </B24Table>
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
                    label="Сохранить правила"
                    color="air-secondary-accent-2"
                    size="lg"
                    :loading="busyAction === 'dedup'"
                    :disabled="!canSaveDedup"
                    @click="saveDedupSettings"
                  />
                  <B24Button
                    label="Проверить данные"
                    color="air-primary"
                    size="lg"
                    :loading="busyAction === 'validation'"
                    :disabled="!canRunValidation"
                    @click="runValidation"
                  />
                </div>
              </div>

              <div class="mb-5 text-sm text-[#5f7285]">
                Отдельно задайте, как искать совпадения и что делать с найденными дублями, чтобы шаг соответствия полей оставался чистым и понятным.
              </div>

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

              <div class="grid gap-4 lg:grid-cols-[280px,1fr]">
                <B24Select
                  :model-value="dedupStrategy"
                  class="w-full"
                  size="lg"
                  :items="dedupStrategyItems"
                  @update:model-value="dedupStrategy = String($event || 'create')"
                />

                <div class="rounded-[16px] border border-white/70 bg-white/85 px-4 py-4 text-sm text-[#5f7285]">
                  <div class="font-medium text-[#314256]">Ключи поиска дубля</div>
                  <div class="mt-1 text-xs text-[#7f92a7]">
                    Первый рабочий срез использует только уже сопоставленные поля `EMAIL`, `PHONE` и `TITLE`. Если выбрано несколько ключей, дубль ищется по их совместному совпадению.
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
                    Сначала сопоставьте одно из полей `EMAIL`, `PHONE` или `TITLE`.
                  </div>
                </div>
              </div>
            </section>
          </section>

          <section v-if="currentStep === 6" class="space-y-6">
            <section class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-4 md:p-5">
              <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Шаг 6</div>
                  <h2 class="mt-1 text-lg font-semibold text-[#314256]">Проверка</h2>
                </div>

                <div class="flex flex-wrap gap-3">
                  <B24Button
                    label="Тестовый импорт"
                    color="air-secondary-accent-2"
                    size="lg"
                    :loading="busyAction === 'dry-run'"
                    :disabled="!canRunDryRun"
                    @click="runDryRun"
                  />
                  <B24Button
                    label="Запустить импорт"
                    color="air-primary"
                    size="lg"
                    :loading="busyAction === 'run'"
                    :disabled="!canRunImport"
                    @click="runImport"
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
                  {{ dryRunData ? 'Тестовый импорт' : 'Проверка данных' }}
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
                v-if="dryRunDedupWeakeningNotice.hasWarnings"
                class="mb-4 rounded-[18px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-4 text-[#8f5b18]"
              >
                <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#c77d2b]">Неполный поиск дублей</div>
                    <div class="mt-1 text-sm font-semibold">{{ dryRunDedupWeakeningNotice.title }}</div>
                    <div class="mt-1 text-sm text-[#9c6a2a]">{{ dryRunDedupWeakeningNotice.description }}</div>
                  </div>
                  <div class="rounded-full border border-[#f3c995] bg-white px-3 py-1 text-sm font-semibold text-[#a96017]">
                    {{ dryRunDedupWeakeningNotice.count }}
                  </div>
                </div>
                <div class="mt-3 grid gap-2 text-sm text-[#8f5b18] md:grid-cols-2">
                  <div>Поля не заполнены: {{ dryRunDedupWeakeningNotice.fieldsLabel }}</div>
                  <div>Строки риска: {{ dryRunDedupWeakeningNotice.rowsLabel }}</div>
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
                  :loading="busyAction === 'dry-run'"
                  loading-color="air-primary"
                  loading-animation="loading"
                  :columns="dryRunTableColumns"
                  :data="filteredDryRunRows"
                  :empty="activeDryRunDedupRiskOnly
                    ? 'Строки с риском неполного поиска дублей не найдены.'
                    : 'После тестового импорта здесь появится предварительный отчет по строкам.'"
                />
                <B24Table
                  v-else
                  class="w-full"
                  :loading="busyAction === 'validation' || busyAction === 'dry-run'"
                  loading-color="air-primary"
                  loading-animation="loading"
                  :columns="validationTableColumns"
                  :data="validationIssueRows"
                  empty="Ошибок не найдено. Можно запускать тестовый импорт."
                />
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

                <div
                  class="rounded-full px-4 py-2 text-sm font-semibold"
                  :class="importRunFailedRows > 0 ? 'border border-[#ffe1c7] bg-[#fff7ef] text-[#c77d2b]' : 'border border-[#d7e7ff] bg-[#f4f9ff] text-[#2e6bd9]'"
                >
                  {{ importRunFailedRows > 0 ? `Есть ошибки: ${importRunFailedRows}` : 'Импорт завершен без ошибок' }}
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
              v-if="isLinkedCompanyContactImport && linkedImportRunSummary.hasSummary"
              class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5"
            >
              <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Итог</div>
                  <h3 class="mt-1 text-xl font-semibold text-[#314256]">Что создано по связанному импорту</h3>
                </div>

                <div
                  v-if="linkedImportRunSummary.hasOverflow"
                  class="rounded-[16px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-3 text-sm text-[#a96c25]"
                >
                  {{ linkedImportRunSummary.overflowMessage }}
                </div>
              </div>

              <div class="mt-5 grid gap-4 xl:grid-cols-2">
                <div
                  v-for="section in linkedImportRunSummary.sections"
                  :key="section.id"
                  class="rounded-[18px] border border-[#e8eef5] bg-white p-4"
                >
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <div class="text-sm font-semibold text-[#314256]">{{ section.title }}</div>
                      <div class="mt-1 text-sm text-[#7b8a99]">Всего: {{ section.total }}</div>
                    </div>
                  </div>

                  <div class="mt-4 space-y-2">
                    <div
                      v-for="item in buildVisibleLinkedSummaryItems(section)"
                      :key="item.key"
                      class="flex items-start justify-between gap-3 rounded-[14px] border border-[#e8eef5] bg-[#fbfcfe] px-3 py-3"
                    >
                      <div class="min-w-0">
                        <div class="truncate text-sm font-medium text-[#314256]">{{ item.title }}</div>
                        <div class="mt-1 text-sm text-[#7b8a99]">ID {{ item.recordId }}</div>
                      </div>
                      <div class="shrink-0 rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-3 py-1 text-xs font-semibold text-[#2e6bd9]">
                        {{ item.statusLabel }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="linkedSummaryPageCount > 1"
                class="mt-5 flex flex-wrap items-center justify-center gap-2"
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

              <div class="mt-5 flex flex-wrap gap-3">
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
              v-if="!isLinkedCompanyContactImport || !linkedImportRunSummary.hasSummary"
              class="rounded-[24px] border border-[#e3e9f0] bg-[#fbfcfe] p-5"
            >
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
                  <div class="mt-2 text-sm font-medium text-[#314256]">{{ group.reason }}</div>
                  <div class="mt-3 text-xs text-[#8a6c4a]">Строки: {{ group.rowNumbers.join(', ') }}</div>
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
                    <div class="mt-1 text-sm text-[#9c6a2a]">{{ importRunDedupWeakeningNotice.description }}</div>
                  </div>
                  <div class="rounded-full border border-[#f3c995] bg-white px-3 py-1 text-sm font-semibold text-[#a96017]">
                    {{ importRunDedupWeakeningNotice.count }}
                  </div>
                </div>
                <div class="mt-3 grid gap-2 text-sm text-[#8f5b18] md:grid-cols-2">
                  <div>Поля не заполнены: {{ importRunDedupWeakeningNotice.fieldsLabel }}</div>
                  <div>Строки риска: {{ importRunDedupWeakeningNotice.rowsLabel }}</div>
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
                  :data="filteredImportRunRows"
                  :empty="activeImportRunFilter === 'all'
                    ? 'После запуска импорта здесь появится итог по строкам.'
                    : 'Для выбранного фильтра строк не найдено.'"
                />
              </div>
            </section>
          </section>
        </div>

        <div
          v-if="!showInlineWizardFooter"
          class="border-t border-[#e5ebf1] bg-[linear-gradient(180deg,#ffffff_0%,#f9fbfe_100%)] px-6 py-5 sm:px-8"
        >
          <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div class="min-w-0 flex-1 xl:max-w-[460px]">
                <div class="mb-2 flex items-center justify-between gap-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">
                  <span>Прогресс</span>
                  <span>{{ currentStep }} / 7</span>
                </div>
                <div class="h-2 rounded-full bg-[#e6edf5]">
                <div
                  class="h-2 rounded-full bg-[linear-gradient(90deg,#2e6bd9_0%,#41b7ff_100%)] transition-all duration-300"
                  :style="{ width: `${progressPercent}%` }"
                />
              </div>
            </div>

            <div class="flex flex-wrap gap-3">
              <B24Button
                label="Назад"
                color="air-tertiary"
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
        </div>
      </div>
    </div>
  </section>
</template>
