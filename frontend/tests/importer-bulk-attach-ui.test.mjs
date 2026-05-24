import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const apiStoreSource = readFileSync(
  new URL('../app/stores/api.ts', import.meta.url),
  'utf8',
)

test('importer workbench keeps bulk attach inside the main wizard and does not expose a dedicated bulk page', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const currentView = ref<'wizard' | 'history'>('wizard')"), true)
  assert.equal(importerWorkbenchSource.includes("v-else-if=\"currentView === 'bulkAttach'\""), false)
  assert.equal(importerWorkbenchSource.includes("currentView.value = 'bulkAttach'"), false)
  assert.equal(importerWorkbenchSource.includes('<BulkAttachWizard'), false)
})

test('bulk attach no longer opens a separate page from the advanced CRM scenario section', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Массовый импорт файлов'), true)
  assert.equal(importerWorkbenchSource.includes('Откроется отдельный экран сценария S17'), false)
  assert.equal(importerWorkbenchSource.includes('Массовое добавление файлов по фильтру CRM'), false)
  assert.equal(importerWorkbenchSource.includes('Найдено записей'), true)
  assert.equal(importerWorkbenchSource.includes("@click=\"goBackFromBulkAttach\""), false)
  assert.equal(importerWorkbenchSource.includes("v-if=\"showsAdvancedImportTools && selectedFileAttachEntityType\""), false)
})

test('bulk attach wizard can start from a preselected CRM entity inside the importer', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('initialEntityType'), true)
  assert.equal(bulkAttachWizardSource.includes('lockEntityType'), true)
  assert.equal(bulkAttachWizardSource.includes("v-if=\"!lockEntityType\""), true)
})

test('bulk attach wizard uses full-width layouts instead of a narrow centered column', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('mx-auto max-w-2xl'), false)
  assert.equal(bulkAttachWizardSource.includes('w-full space-y-6'), true)
  assert.equal(bulkAttachWizardSource.includes('lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]'), true)
})

test('bulk attach wizard builds dynamic CRM filters from Bitrix field catalog instead of two hardcoded fields', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes("const filterStatusId = ref('')"), false)
  assert.equal(bulkAttachWizardSource.includes("const filterAssignedById = ref('')"), false)
  assert.equal(bulkAttachWizardSource.includes('filterFieldRows'), true)
  assert.equal(bulkAttachWizardSource.includes('Добавить поле'), true)
  assert.equal(bulkAttachWizardSource.includes('Если поля не добавлены, будут выбраны все'), true)
  assert.equal(bulkAttachWizardSource.includes(":filter-fields=\"['label']\""), true)
  assert.equal(bulkAttachWizardSource.includes("placeholder: 'Поиск поля Bitrix24'"), true)
})

test('bulk attach wizard renders Bitrix24 enum filter values as selectable lists', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('items: Array<{ id: string, title: string }>'), true)
  assert.equal(bulkAttachWizardSource.includes('const hasSelectableItems = Array.isArray(row.items) && row.items.length > 0'), true)
  assert.equal(bulkAttachWizardSource.includes("placeholder=\"Выберите значение Bitrix24\""), true)
  assert.equal(bulkAttachWizardSource.includes("placeholder: 'Поиск значения Bitrix24'"), true)
})

test('bulk attach preview mentions only first 5 sample records', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('показаны первые 10'), false)
  assert.equal(bulkAttachWizardSource.includes('показаны первые 5'), true)
})

test('api store exposes import field catalog loader for bulk attach filters', () => {
  assert.equal(apiStoreSource.includes('const getImportFields = async ('), true)
  assert.equal(apiStoreSource.includes("/api/import-fields?${searchParams.toString()}"), true)
  assert.equal(apiStoreSource.includes('getImportFields,'), true)
})

test('step 1 bulk setup runs bulk attach directly from the workbench card', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('function startBulkAttachSetup()'), true)
  assert.equal(importerWorkbenchSource.includes('@click="startBulkAttachSetup"'), true)
  assert.equal(importerWorkbenchSource.includes('apiStore.uploadBulkAttachFile(selectedFile.value as File)'), true)
  assert.equal(importerWorkbenchSource.includes('apiStore.createBulkAttachSession({'), true)
  assert.equal(importerWorkbenchSource.includes('apiStore.runBulkAttachSession(sessionId)'), true)
  assert.equal(importerWorkbenchSource.includes('bulkAttachDraft.value = {'), false)
})

test('new bulk upload stays inside crm step 1 and does not redirect to the dedicated bulk page', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const startIndex = importerWorkbenchSource.indexOf('function startBulkAttachSetup() {')
  const endIndex = importerWorkbenchSource.indexOf('function updateLinkedPrimaryEntityType(value: string) {', startIndex)
  const startSource = importerWorkbenchSource.slice(startIndex, endIndex)

  assert.equal(startSource.includes("currentView.value = 'bulkAttach'"), false)
  assert.equal(startSource.includes('updateFileAttachEntityType('), false)
  assert.equal(importerWorkbenchSource.includes('showBulkAttachExecutionState'), true)
  assert.equal(importerWorkbenchSource.includes('goBackFromBulkPreview()'), true)
})

test('bulk attach execution card shows a stop action and keeps the file picker locked after start', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const isBulkAttachExecutionLocked = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes("busyAction.value === 'bulk-attach-cancel'"), true)
  assert.equal(importerWorkbenchSource.includes('const canCancelBulkAttach = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('label="Остановить"'), true)
  assert.equal(importerWorkbenchSource.includes('color="air-tertiary"'), true)
  assert.equal(importerWorkbenchSource.includes('@click="cancelBulkAttachExecution"'), true)
  assert.equal(importerWorkbenchSource.includes('label="Завершить"'), true)
  assert.equal(importerWorkbenchSource.includes('@click="finishInlineBulkAttachFlow"'), true)
  assert.equal(importerWorkbenchSource.includes('Загрузка уже выполняется. Чтобы заменить файл, сначала остановите текущую сессию.'), true)
})

test('bulk mode uses dedicated step labels and headings instead of the regular import wizard copy', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const isBulkAttachFlow = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('const bulkFlowStep = computed<BulkFlowStep>(() => {'), true)
  assert.equal(importerWorkbenchSource.includes('const bulkFlowStepMeta = computed(() => {'), true)
  assert.equal(importerWorkbenchSource.includes("eyebrow: 'Шаг 2 · Файл и выборка'"), true)
  assert.equal(importerWorkbenchSource.includes("eyebrow: 'Шаг 3 · Загрузка'"), true)
  assert.equal(importerWorkbenchSource.includes("title: 'Назначение'"), true)
  assert.equal(importerWorkbenchSource.includes("title: 'Файл и выборка'"), true)
  assert.equal(importerWorkbenchSource.includes("title: isTaskBulkAttachFlow.value ? 'Загрузка вложений' : 'Загрузка файлов'"), true)
  assert.equal(importerWorkbenchSource.includes('const visibleSteps = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('{{ selectedFamilyHeaderMeta.eyebrow }}'), true)
  assert.equal(importerWorkbenchSource.includes('{{ selectedFamilyHeaderMeta.title }}'), true)
  assert.equal(importerWorkbenchSource.includes('{{ selectedFamilyHeaderMeta.description }}'), true)
  assert.equal(importerWorkbenchSource.includes('const currentStepHeaderStatusMeta = computed(() => {'), true)
  assert.equal(importerWorkbenchSource.includes('{{ currentStepMeta.description }}'), true)
  assert.equal(importerWorkbenchSource.includes('Текущий статус'), false)
  assert.equal(importerWorkbenchSource.includes('v-for="(step, index) in visibleSteps"'), true)
  assert.equal(importerWorkbenchSource.includes('@click="goToSidebarStep(step.id)"'), true)
})

test('bulk setup keeps only the add-field filter controls without extra helper framing', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Фильтр отбора:'), true)
  assert.equal(importerWorkbenchSource.includes('placeholder="Например, Сделки"'), true)
  assert.equal(importerWorkbenchSource.includes('Сначала выберите CRM-сущность'), true)
  assert.equal(importerWorkbenchSource.includes('У выбранной сущности нет полей типа «Файл»'), true)
  assert.equal(importerWorkbenchSource.includes('Сначала выберите CRM-сущность и поле для файлов'), true)
  assert.equal(importerWorkbenchSource.includes('Сначала выберите CRM-сущность, затем поле назначения.'), false)
  assert.equal(importerWorkbenchSource.includes('Шаг 1 — Выберите тип сущности и фильтр'), false)
  assert.equal(importerWorkbenchSource.includes('Выбранная CRM-сущность:'), false)
  assert.equal(importerWorkbenchSource.includes('Если поля не добавлены, будут выбраны все'), false)
  assert.equal(importerWorkbenchSource.includes('Без фильтров — будут выбраны все'), false)
  assert.equal(importerWorkbenchSource.includes('Показано {{ bulkFilterPreview.sample.length }} из {{ bulkFilterPreview.total }}'), false)
  assert.equal(importerWorkbenchSource.includes('Поиск поля Bitrix24'), true)
  assert.equal(importerWorkbenchSource.includes('Выберите значение Bitrix24'), true)
  assert.equal(importerWorkbenchSource.includes('Показываем системные и пользовательские поля. Поиск работает по названию из Bitrix24.'), false)
})

test('dependent linked and bulk selects stay readable instead of fading as disabled placeholders', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Сначала выберите основную сущность'), true)
  assert.equal(importerWorkbenchSource.includes('Для этой сущности нет связанных вариантов'), true)
  assert.equal(importerWorkbenchSource.includes(':disabled="!selectedLinkedPrimaryEntityType || !importerPermissionState.canCreateSessions || Boolean(busyAction)"'), false)
  assert.equal(importerWorkbenchSource.includes(':disabled="!selectedFileAttachEntityType || loadingBulkFileFields || !bulkFileFields.length || Boolean(busyAction)"'), false)
  assert.equal(importerWorkbenchSource.includes(':disabled="loadingBulkFileFields || Boolean(busyAction)"'), false)
  assert.equal(importerWorkbenchSource.includes(":placeholder=\"loadingBulkFileFields"), false)
  assert.equal(importerWorkbenchSource.includes("v-if=\"loadingBulkFileFields\""), true)
})

test('bulk scenario selector becomes unavailable while file execution is active', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const isBulkAttachScenarioLocked = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('if (isBulkAttachScenarioLocked.value && normalizedValue !== crmFlavor.value) {'), true)
  assert.equal(importerWorkbenchSource.includes(":disabled=\"!importerPermissionState.canCreateSessions || Boolean(busyAction) || isBulkAttachScenarioLocked\""), true)
  assert.equal(importerWorkbenchSource.includes("cursor-not-allowed"), true)
})

test('bulk file picker handlers respect the full lock state while execution is active', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const openStart = importerWorkbenchSource.indexOf('function openFilePicker() {')
  const openEnd = importerWorkbenchSource.indexOf('function handleFileChange(event: Event) {', openStart)
  const openSource = importerWorkbenchSource.slice(openStart, openEnd)
  const dropStart = importerWorkbenchSource.indexOf('function handleDropFile(event: DragEvent) {')
  const dropEnd = importerWorkbenchSource.indexOf('function buildImportFileSizeErrorMessage(file: File) {', dropStart)
  const dropSource = importerWorkbenchSource.slice(dropStart, dropEnd)

  assert.equal(openSource.includes("crmFlavor.value === 'bulk' && !isBulkFilePickerReady.value"), false)
  assert.equal(dropSource.includes("crmFlavor.value === 'bulk' && !isBulkFilePickerReady.value"), false)
  assert.equal(openSource.includes("isBulkAttachFlow.value && isBulkFilePickerLocked.value"), true)
  assert.equal(dropSource.includes("isBulkAttachFlow.value && isBulkFilePickerLocked.value"), true)
})

test('bulk flow step is derived from preview and execution state so restored sessions reopen the correct substep', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const bulkStepStart = importerWorkbenchSource.indexOf('const bulkFlowStep = computed<BulkFlowStep>(() => {')
  const bulkStepEnd = importerWorkbenchSource.indexOf('const bulkFlowStepMeta = computed(() => {', bulkStepStart)
  const bulkStepSource = importerWorkbenchSource.slice(bulkStepStart, bulkStepEnd)

  assert.equal(bulkStepSource.includes("if (showBulkAttachExecutionState.value) return 'execution'"), true)
  assert.equal(bulkStepSource.includes("if (bulkFilterPreview.value) return 'review'"), true)
  assert.equal(bulkStepSource.includes("return 'setup'"), true)
})

test('resuming bulk attach from history restores the new inline crm bulk flow instead of the legacy page', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const resumeStart = importerWorkbenchSource.indexOf('async function resumeHistorySession(sessionId: string) {')
  const resumeEnd = importerWorkbenchSource.indexOf('function getStepStatus(step: number): StepState {', resumeStart)
  const resumeSource = importerWorkbenchSource.slice(resumeStart, resumeEnd)
  const bulkBranchStart = resumeSource.indexOf('if (isBulkAttach) {')
  const bulkBranchSource = resumeSource.slice(bulkBranchStart)

  assert.equal(bulkBranchSource.includes("selectedFamily.value = 'crm'"), true)
  assert.equal(bulkBranchSource.includes("crmFlavor.value = 'bulk'"), true)
  assert.equal(bulkBranchSource.includes("currentView.value = 'wizard'"), true)
  assert.equal(resumeSource.includes('if (!isBulkAttach) {'), true)
  assert.equal(resumeSource.includes('applyHistoryScenarioSelection(snapshot)'), true)
  assert.equal(bulkBranchSource.includes('await loadBulkAttachEntityFields(normalizedEntityType)'), true)
  assert.equal(bulkBranchSource.includes('applyBulkAttachSnapshot(snapshot)'), true)
  assert.equal(resumeSource.includes('const isBulkAttach = isBulkAttachSessionSnapshot(snapshot)'), true)
  assert.equal(bulkBranchSource.includes("currentView.value = 'bulkAttach'"), false)
})

test('history shows all import sessions including cancelled bulk attach records', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const visibleHistorySessions = computed(() => recentSessions.value.filter((session) => {'), false)
  assert.equal(importerWorkbenchSource.includes('const historyRows = computed(() => buildSessionHistoryRows(recentSessions.value))'), true)
})

test('active running session warning now compares session ids instead of clearing on any opened session', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const activeRunningSessionId = computed(() => String(activeRunningSession.value?.id || activeRunningSession.value?.session_id || '').trim())"), true)
  assert.equal(importerWorkbenchSource.includes("const currentSessionId = computed(() => String(session.value?.id || session.value?.session_id || '').trim())"), true)
  assert.equal(importerWorkbenchSource.includes('const isViewingActiveRunningSession = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('Boolean(activeRunningSessionId.value && currentSessionId.value && activeRunningSessionId.value === currentSessionId.value)'), true)
  assert.equal(importerWorkbenchSource.includes('Boolean(activeRunningSessionId.value && !isViewingActiveRunningSession.value)'), true)
})

test('importer workbench no longer persists or auto-resumes the last opened session', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const IMPORTER_RESUME_STORAGE_KEY = 'excel-migration-importer-resume-v1'"), false)
  assert.equal(importerWorkbenchSource.includes('function readPersistedImporterResume() {'), false)
  assert.equal(importerWorkbenchSource.includes('function persistImporterResumeState() {'), false)
  assert.equal(importerWorkbenchSource.includes('function clearPersistedImporterResume() {'), false)
  assert.equal(importerWorkbenchSource.includes('const persistedResume = readPersistedImporterResume()'), false)
  assert.equal(importerWorkbenchSource.includes('await resumeHistorySession(persistedResume.sessionId)'), false)
})

test('bulk attach wizard accepts locked prefill data from step 1 and hides repeated field setup', () => {
  const bulkAttachWizardSource = readFileSync(
    new URL('../app/components/BulkAttachWizard.vue', import.meta.url),
    'utf8',
  )

  assert.equal(bulkAttachWizardSource.includes('initialFieldId'), true)
  assert.equal(bulkAttachWizardSource.includes('lockFieldId'), true)
  assert.equal(bulkAttachWizardSource.includes('initialFilterRows'), true)
  assert.equal(bulkAttachWizardSource.includes('lockFilters'), true)
  assert.equal(bulkAttachWizardSource.includes('initialPreview'), true)
  assert.equal(bulkAttachWizardSource.includes('initialFile'), true)
  assert.equal(bulkAttachWizardSource.includes('Выбранное поле для файла'), true)
  assert.equal(bulkAttachWizardSource.includes("v-if=\"!lockFieldId\""), true)
  assert.equal(bulkAttachWizardSource.includes('uploadedFileName.value = props.initialFile.name'), true)
})

test('explicit landing mode selection always starts a new importer flow', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const hasExplicitInitialImportMode = Boolean(String(props.initialImportMode || '').trim())"), false)
  assert.equal(importerWorkbenchSource.includes('if (hasExplicitInitialImportMode) {'), false)
  assert.equal(importerWorkbenchSource.includes('selectImportMode(props.initialImportMode)'), true)
  assert.equal(importerWorkbenchSource.includes('if (!hasExplicitInitialImportMode && persistedResume?.sessionId) {'), false)
})
