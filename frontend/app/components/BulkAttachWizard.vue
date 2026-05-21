<script setup lang="ts">
type InitialPreview = {
  total: number
  sample: Array<{ id: number, title: string }>
  hasMore?: boolean
}

type InitialFilterRow = {
  fieldId: string
  value: string
}

const props = withDefaults(defineProps<{
  initialEntityType?: string
  initialFieldId?: string
  initialFilterRows?: InitialFilterRow[]
  initialPreview?: InitialPreview | null
  initialFile?: File | null
  lockEntityType?: boolean
  lockFieldId?: boolean
  lockFilters?: boolean
  resumeSessionId?: string
}>(), {
  initialEntityType: '',
  initialFieldId: '',
  initialFilterRows: () => [],
  initialPreview: null,
  initialFile: null,
  lockEntityType: false,
  lockFieldId: false,
  lockFilters: false,
  resumeSessionId: '',
})

const emit = defineEmits<{ finish: [] }>()

const apiStore = useApiStore()

type FilterFieldItem = { id: string, title: string }
type FilterFieldCatalogEntry = {
  id: string
  title: string
  type: string
  items: Array<{ id: string, title: string }>
}
type FilterFieldRow = {
  key: string
  fieldId: string
  title: string
  type: string
  items: Array<{ id: string, title: string }>
  value: string
}

const ENTITY_OPTIONS = [
  { value: 'lead', label: 'Лиды', icon: '📋' },
  { value: 'contact', label: 'Контакты', icon: '👤' },
  { value: 'company', label: 'Компании', icon: '🏢' },
  { value: 'deal', label: 'Сделки', icon: '💼' },
]
const PREVIEW_SAMPLE_LIMIT = 5

// Steps: 1=entity+filter, 2=preview, 3=file config, 4=run+result
const step = ref(1)
const busy = ref(false)
const error = ref('')
const loadingFilterFields = ref(false)
const isAddingFilterField = ref(false)
const pendingFilterFieldId = ref('')

// Step 1
function resolveEntityType(value: string) {
  const normalizedValue = String(value || '').trim()
  return ENTITY_OPTIONS.some((option) => option.value === normalizedValue) ? normalizedValue : 'lead'
}

const entityType = ref(resolveEntityType(props.initialEntityType))
const filterFieldCatalog = ref<FilterFieldCatalogEntry[]>([])
const filterFieldRows = ref<FilterFieldRow[]>([])

// Step 2 — preview result
const previewTotal = ref(0)
const previewSample = ref<{ id: number, title: string }[]>([])
const previewHasMore = ref(false)

// Step 3
const fileUrl = ref('')
const fieldId = ref('')
const fileName = ref('')
const selectedUploadFile = ref<File | null>(null)
const uploadedFileId = ref('')
const uploadedFileName = ref('')
const uploadingFile = ref(false)

// Step 4 — run result
const sessionId = ref('')
const sessionStatus = ref('')
const resultTotal = ref(0)
const resultSuccessful = ref(0)
const resultFailed = ref(0)
const progressProcessed = ref(0)
const progressTotal = ref(0)
const pollingHandle = ref<ReturnType<typeof setInterval> | null>(null)
const cancelRequested = ref(false)

const filterFieldOptions = computed(() => (
  filterFieldCatalog.value
    .filter((field) => !filterFieldRows.value.some((row) => row.fieldId === field.id))
    .map((field) => ({
      value: field.id,
      label: field.title,
    }))
))

const fileFieldOptions = computed(() =>
  filterFieldCatalog.value
    .filter((field) => field.type === 'file' || field.type === 'disk_file')
    .map((field) => ({
      value: field.id,
      label: field.title,
    }))
)

const selectedFieldLabel = computed(() => (
  fileFieldOptions.value.find((item) => item.value === fieldId.value)?.label
  || filterFieldCatalog.value.find((item) => item.id === fieldId.value)?.title
  || fieldId.value
))

const selectedUploadFileLabel = computed(() => (
  uploadedFileName.value
  || selectedUploadFile.value?.name
  || ''
))

const computedFilter = computed(() => {
  const f: Record<string, any> = {}
  for (const row of filterFieldRows.value) {
    const normalizedValue = String(row.value || '').trim()
    if (!normalizedValue) {
      continue
    }
    f[row.fieldId] = normalizedValue
  }
  return f
})

const entityLabel = computed(() => ENTITY_OPTIONS.find(o => o.value === entityType.value)?.label || entityType.value)

const progressPercent = computed(() => {
  if (!progressTotal.value) return 0
  return Math.min(100, Math.round((progressProcessed.value / progressTotal.value) * 100))
})

watch(() => props.initialEntityType, (value) => {
  entityType.value = resolveEntityType(value)
}, { immediate: true })

watch(entityType, async (_value, previousValue) => {
  if (String(previousValue || '').trim() !== String(entityType.value || '').trim()) {
    filterFieldRows.value = []
    pendingFilterFieldId.value = ''
    isAddingFilterField.value = false
  }
  await loadFilterFields()
  applyInitialStepOnePrefill()
}, { immediate: true })

watch(() => props.initialFieldId, () => {
  applyInitialStepOnePrefill()
}, { immediate: true })

watch(() => props.initialPreview, () => {
  applyInitialStepOnePrefill()
}, { immediate: true })

watch(() => props.initialFile, () => {
  applyInitialStepOnePrefill()
}, { immediate: true })

watch(() => props.initialFilterRows, () => {
  applyInitialStepOnePrefill()
}, { immediate: true, deep: true })

async function loadFilterFields() {
  loadingFilterFields.value = true
  try {
    const response = await apiStore.getImportFields(entityType.value)
    const rawItems = Array.isArray(response.items) ? response.items : []
    filterFieldCatalog.value = rawItems
      .map((item) => ({
        id: String(item?.id || '').trim(),
        title: String(item?.title || item?.id || '').trim(),
        type: String(item?.type || '').trim(),
        items: Array.isArray(item?.items)
          ? item.items
            .map((option: any) => ({
              id: String(option?.id || '').trim(),
              title: String(option?.title || option?.id || '').trim(),
            }))
            .filter((option: FilterFieldItem) => option.id && option.title)
          : [],
      }))
      .filter((item) => item.id && item.title)
      .sort((left, right) => left.title.localeCompare(right.title, 'ru'))
  } catch {
    filterFieldCatalog.value = []
  } finally {
    loadingFilterFields.value = false
  }
}

function buildFilterFieldRow(fieldKey: string, value: string, index: number) {
  const normalizedFieldId = String(fieldKey || '').trim()
  if (!normalizedFieldId) {
    return null
  }

  const selectedField = filterFieldCatalog.value.find((field) => field.id === normalizedFieldId)
  if (!selectedField) {
    return null
  }

  return {
    key: `${normalizedFieldId}:${index + 1}`,
    fieldId: normalizedFieldId,
    title: selectedField.title,
    type: selectedField.type,
    items: selectedField.items,
    value: String(value || '').trim(),
  }
}

function applyInitialStepOnePrefill() {
  if (props.initialFieldId) {
    fieldId.value = String(props.initialFieldId || '').trim()
  }

  if (props.initialFile) {
    selectedUploadFile.value = props.initialFile
    uploadedFileName.value = props.initialFile.name
  }

  if (props.initialPreview) {
    previewTotal.value = Number(props.initialPreview.total || 0)
    previewSample.value = Array.isArray(props.initialPreview.sample) ? props.initialPreview.sample.slice(0, PREVIEW_SAMPLE_LIMIT) : []
    previewHasMore.value = Boolean(
      props.initialPreview.hasMore
      ?? (Number(props.initialPreview.total || 0) > Number(props.initialPreview.sample?.length || 0))
    )
  }

  if (!props.initialFilterRows.length) {
    if (props.lockFilters) {
      filterFieldRows.value = []
    }
  } else {
    filterFieldRows.value = props.initialFilterRows
      .map((row, index) => buildFilterFieldRow(row.fieldId, row.value, index))
      .filter((row): row is FilterFieldRow => Boolean(row))
  }

  if (!props.resumeSessionId && props.lockFilters && props.initialPreview) {
    step.value = props.initialFile && props.initialFieldId && props.lockFieldId ? 3 : 2
  }
}

async function openAddFilterField() {
  error.value = ''
  if (!filterFieldCatalog.value.length && !loadingFilterFields.value) {
    await loadFilterFields()
  }
  isAddingFilterField.value = true
}

function addFilterField(fieldId: string) {
  const normalizedFieldId = String(fieldId || '').trim()
  if (!normalizedFieldId) {
    return
  }

  const selectedField = filterFieldCatalog.value.find((field) => field.id === normalizedFieldId)
  if (!selectedField) {
    return
  }

  if (filterFieldRows.value.some((row) => row.fieldId === normalizedFieldId)) {
    pendingFilterFieldId.value = ''
    isAddingFilterField.value = false
    return
  }

  filterFieldRows.value = [
    ...filterFieldRows.value,
    {
      key: `${normalizedFieldId}:${filterFieldRows.value.length + 1}`,
      fieldId: normalizedFieldId,
      title: selectedField.title,
      type: selectedField.type,
      items: selectedField.items,
      value: '',
    },
  ]
  pendingFilterFieldId.value = ''
  isAddingFilterField.value = false
}

function removeFilterField(fieldId: string) {
  filterFieldRows.value = filterFieldRows.value.filter((row) => row.fieldId !== fieldId)
}

function hasFilterFieldSelectableItems(row: FilterFieldRow) {
  const hasSelectableItems = Array.isArray(row.items) && row.items.length > 0
  return hasSelectableItems
}

function getFilterFieldValueOptions(row: FilterFieldRow) {
  return row.items.map((item) => ({
    value: item.id,
    label: item.title,
  }))
}

async function goPreview() {
  error.value = ''
  busy.value = true
  try {
    const res = await apiStore.crmFilterPreview({ entity_type: entityType.value, filter: computedFilter.value })
    previewTotal.value = res.total
    previewSample.value = Array.isArray(res.sample) ? res.sample.slice(0, PREVIEW_SAMPLE_LIMIT) : []
    previewHasMore.value = res.has_more
    step.value = 2
  } catch (e: any) {
    error.value = String(e?.data?.error || e?.message || 'Ошибка при запросе')
  } finally {
    busy.value = false
  }
}

async function goFileConfig() {
  error.value = ''
  if (!previewTotal.value) {
    error.value = 'Нет сущностей, подходящих под фильтр'
    return
  }
  step.value = 3
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  error.value = ''
  selectedUploadFile.value = file
  uploadingFile.value = true
  uploadedFileId.value = ''
  uploadedFileName.value = file.name
  try {
    const res = await apiStore.uploadBulkAttachFile(file)
    uploadedFileId.value = res.file_id
    uploadedFileName.value = res.file_name
  } catch (e: any) {
    error.value = String(e?.data?.error || e?.message || 'Ошибка загрузки файла')
  } finally {
    uploadingFile.value = false
    input.value = ''
  }
}

async function ensureUploadedFile() {
  if (uploadedFileId.value || !selectedUploadFile.value) {
    return
  }

  uploadingFile.value = true
  try {
    const res = await apiStore.uploadBulkAttachFile(selectedUploadFile.value)
    uploadedFileId.value = res.file_id
    uploadedFileName.value = res.file_name
  } catch (e: any) {
    error.value = String(e?.data?.error || e?.message || 'Ошибка загрузки файла')
  } finally {
    uploadingFile.value = false
  }
}

function startPolling(sid: string) {
  if (pollingHandle.value) return
  pollingHandle.value = setInterval(async () => {
    try {
      const res = await apiStore.getImportSession(sid)
      const snap = res.item
      if (!snap) return
      const status = String(snap.status || '')
      progressProcessed.value = Number(snap.processed_rows || 0)
      progressTotal.value = Number(snap.total_rows || progressTotal.value)
      if (status !== 'running' && status !== 'draft') {
        stopPolling()
        sessionStatus.value = status
        resultTotal.value = Number(snap.total_rows || 0)
        resultSuccessful.value = Number(snap.successful_rows || 0)
        resultFailed.value = Number(snap.failed_rows || 0)
        progressProcessed.value = resultTotal.value
      }
    } catch { /* ignore polling errors */ }
  }, 2000)
}

function stopPolling() {
  if (pollingHandle.value) {
    clearInterval(pollingHandle.value)
    pollingHandle.value = null
  }
}

async function cancelAttach() {
  if (!sessionId.value || cancelRequested.value) return
  cancelRequested.value = true
  try {
    const res = await apiStore.cancelImportSession(sessionId.value)
    stopPolling()
    const snap = res.item || {}
    sessionStatus.value = String(snap.status || 'cancelled')
    resultTotal.value = Number(snap.total_rows || progressTotal.value)
    resultSuccessful.value = Number(snap.successful_rows || resultSuccessful.value)
    resultFailed.value = Number(snap.failed_rows || resultFailed.value)
    progressProcessed.value = Number(snap.processed_rows || progressProcessed.value)
  } catch (e: any) {
    error.value = String(e?.data?.error || e?.message || 'Ошибка при остановке')
  } finally {
    cancelRequested.value = false
  }
}

async function applySessionSnapshot(snap: Record<string, any>) {
  sessionId.value = String(snap.id || '')
  sessionStatus.value = String(snap.status || '')
  progressTotal.value = Number(snap.total_rows || 0)
  progressProcessed.value = Number(snap.processed_rows || 0)
  resultTotal.value = Number(snap.total_rows || 0)
  resultSuccessful.value = Number(snap.successful_rows || 0)
  resultFailed.value = Number(snap.failed_rows || 0)
  step.value = 4
  if (sessionStatus.value === 'running') {
    startPolling(sessionId.value)
  }
}

async function runAttach() {
  error.value = ''
  if (!selectedUploadFile.value && !uploadedFileId.value && !fileUrl.value.trim()) { error.value = 'Загрузите файл'; return }
  if (!fieldId.value.trim()) { error.value = 'Укажите ID поля'; return }

  busy.value = true
  try {
    await ensureUploadedFile()
    if (!uploadedFileId.value && !fileUrl.value.trim()) {
      error.value = 'Загрузите файл'
      return
    }

    const created = await apiStore.createBulkAttachSession({
      entity_type: entityType.value,
      filter: computedFilter.value,
      ...(uploadedFileId.value
        ? { file_id: uploadedFileId.value, file_name: uploadedFileName.value }
        : { file_url: fileUrl.value.trim(), file_name: fileName.value.trim() }),
      field_id: fieldId.value.trim(),
    })
    sessionId.value = String(created.item.id)
    sessionStatus.value = 'running'
    step.value = 4
    progressProcessed.value = 0
    progressTotal.value = previewTotal.value

    const runRes = await apiStore.runBulkAttachSession(sessionId.value)
    const runStatus = String(runRes.item?.status || '')

    if (runStatus === 'running') {
      // фоновый режим — поллим
      startPolling(sessionId.value)
    } else {
      sessionStatus.value = runStatus || 'completed'
      resultTotal.value = Number(runRes.result?.total ?? runRes.item?.total_rows ?? 0)
      resultSuccessful.value = Number(runRes.result?.successful ?? runRes.item?.successful_rows ?? 0)
      resultFailed.value = Number(runRes.result?.failed ?? runRes.item?.failed_rows ?? 0)
      progressProcessed.value = resultTotal.value
    }
  } catch (e: any) {
    error.value = String(e?.data?.error || e?.message || 'Ошибка при выполнении')
    sessionStatus.value = 'failed'
  } finally {
    busy.value = false
  }
}

watch(() => props.resumeSessionId, async (newId) => {
  if (!newId) return
  stopPolling()
  try {
    const res = await apiStore.getImportSession(newId)
    if (res.item) await applySessionSnapshot(res.item)
  } catch { /* ignore */ }
}, { immediate: true })

onUnmounted(() => {
  stopPolling()
})

function reset() {
  stopPolling()
  step.value = 1
  error.value = ''
  filterFieldRows.value = []
  pendingFilterFieldId.value = ''
  isAddingFilterField.value = false
  fileUrl.value = ''
  fieldId.value = ''
  fileName.value = ''
  selectedUploadFile.value = null
  uploadedFileId.value = ''
  uploadedFileName.value = ''
  uploadingFile.value = false
  sessionId.value = ''
  sessionStatus.value = ''
  resultTotal.value = 0
  resultSuccessful.value = 0
  resultFailed.value = 0
  progressProcessed.value = 0
  progressTotal.value = 0
  applyInitialStepOnePrefill()
}
</script>

<template>
  <div class="w-full space-y-6">
    <div class="mb-6">
      <h2 class="text-xl font-bold text-[#314256]">Массовое добавление файлов</h2>
      <p class="mt-1 text-sm text-[#6f8194]">Прикрепите файл к выбранным CRM-сущностям по фильтру — без Excel-файла.</p>
    </div>

    <!-- Step indicators -->
    <div class="mb-6 flex items-center gap-2 text-sm">
      <template v-for="(label, i) in ['Фильтр', 'Предпросмотр', 'Файл', 'Выполнение']" :key="i">
        <div
          class="flex items-center gap-1.5 rounded-full px-3 py-1 font-medium"
          :class="step === i + 1
            ? 'bg-[#2e6bd9] text-white'
            : step > i + 1
              ? 'bg-[#e6eefc] text-[#2e6bd9]'
              : 'bg-[#f0f4f8] text-[#9aa9b8]'"
        >
          <span>{{ i + 1 }}</span>
          <span class="hidden sm:inline">{{ label }}</span>
        </div>
        <div v-if="i < 3" class="h-px w-4 bg-[#dde5ef]" />
      </template>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 rounded-[14px] border border-[#ffd4d4] bg-[#fff5f5] px-4 py-3 text-sm text-[#c24b53]">
      {{ error }}
    </div>

    <!-- STEP 1: Entity + Filter -->
    <div v-if="step === 1" class="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div class="rounded-[22px] border border-[#e5ebf2] bg-white p-5">
        <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 1 — Выберите тип сущности и фильтр</div>

        <div v-if="!lockEntityType" class="mb-4">
          <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">Тип сущности</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="opt in ENTITY_OPTIONS"
              :key="opt.value"
              type="button"
              class="rounded-full border px-4 py-1.5 text-sm font-medium transition"
              :class="entityType === opt.value
                ? 'border-[#2e6bd9] bg-[#e6eefc] text-[#2e6bd9]'
                : 'border-[#d8e3ef] bg-white text-[#5f7285] hover:border-[#a8c1e8]'"
              @click="entityType = opt.value"
            >
              {{ opt.icon }} {{ opt.label }}
            </button>
          </div>
        </div>
        <div v-else class="mb-4 rounded-[10px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3 text-sm text-[#2e6bd9]">
          Выбранная CRM-сущность: <span class="font-semibold">{{ entityLabel }}</span>
        </div>

        <div v-if="lockFilters" class="space-y-4">
          <div
            v-if="filterFieldRows.length === 0"
            class="rounded-[14px] border border-dashed border-[#d7e7ff] bg-[#f8fbff] px-4 py-4 text-sm text-[#67809b]"
          >
            Фильтр не задан. В массовое добавление попадут все {{ entityLabel.toLowerCase() }}.
          </div>

          <div
            v-for="row in filterFieldRows"
            :key="row.key"
            class="rounded-[16px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-4"
          >
            <div class="text-sm font-semibold text-[#314256]">
              {{ row.title }}
            </div>
            <div class="mt-3 rounded-[10px] border border-[#d8e3ef] bg-white px-3 py-2 text-sm text-[#314256]">
              {{ row.value || '—' }}
            </div>
          </div>
        </div>

        <div v-else class="space-y-4">
          <div
            v-if="filterFieldRows.length === 0"
            class="rounded-[14px] border border-dashed border-[#d7e7ff] bg-[#f8fbff] px-4 py-4 text-sm text-[#67809b]"
          >
            Если поля не добавлены, будут выбраны все {{ entityLabel.toLowerCase() }}.
          </div>

          <div
            v-for="row in filterFieldRows"
            :key="row.key"
            class="rounded-[16px] border border-[#e5ebf2] bg-[#fbfcfe] px-4 py-4"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="text-sm font-semibold text-[#314256]">
                {{ row.title }}
              </div>
              <button
                type="button"
                class="rounded-full border border-[#d9e5f1] bg-white px-3 py-1 text-xs font-medium text-[#6d8194] transition hover:border-[#f0b7b7] hover:text-[#c24b53]"
                @click="removeFilterField(row.fieldId)"
              >
                Удалить
              </button>
            </div>
            <B24SelectMenu
              v-if="hasFilterFieldSelectableItems(row)"
              :model-value="row.value"
              class="mt-3 w-full"
              placeholder="Выберите значение Bitrix24"
              :items="getFilterFieldValueOptions(row)"
              value-key="value"
              :filter-fields="['label']"
              :search-input="{ placeholder: 'Поиск значения Bitrix24' }"
              @update:model-value="row.value = String($event || '')"
            />
            <input
              v-else
              v-model="row.value"
              type="text"
              :placeholder="`Введите значение для поля «${row.title}»`"
              class="mt-3 w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
            />
          </div>

          <div v-if="isAddingFilterField" class="rounded-[16px] border border-[#dce7f7] bg-[#f7fbff] px-4 py-4">
            <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Новое поле фильтра</div>
            <B24SelectMenu
              :model-value="pendingFilterFieldId"
              class="mt-3 w-full"
              placeholder="Выберите поле Bitrix24"
              :items="filterFieldOptions"
              value-key="value"
              :filter-fields="['label']"
              :search-input="{ placeholder: 'Поиск поля Bitrix24' }"
              @update:model-value="addFilterField(String($event || ''))"
            />
            <div class="mt-2 text-xs text-[#7f92a7]">
              {{ loadingFilterFields
                ? 'Загружаем поля Bitrix24...'
                : filterFieldOptions.length
                  ? 'Показываем системные и пользовательские поля. Поиск работает по названию из Bitrix24.'
                  : 'Свободных полей для добавления не осталось.' }}
            </div>
          </div>

          <button
            type="button"
            class="inline-flex items-center rounded-full border border-dashed border-[#c6d7ee] bg-transparent px-4 py-2 text-sm font-medium text-[#53749b] transition hover:border-[#2e6bd9] hover:text-[#2e6bd9]"
            @click="openAddFilterField"
          >
            Добавить поле
          </button>
        </div>

        <div class="flex items-center justify-between">
          <span class="text-xs text-[#9aa9b8]">Без фильтров — будут выбраны все {{ entityLabel.toLowerCase() }}</span>
          <B24Button
            label="Предпросмотр →"
            color="air-primary"
            size="md"
            :loading="busy"
            @click="goPreview"
          />
        </div>
      </div>

      <aside class="rounded-[22px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f7fbff_0%,#eef5ff_100%)] p-5">
        <div class="mt-2 text-lg font-semibold text-[#314256]">Выбор CRM-элементов по фильтру</div>
        <div class="mt-3 space-y-3 text-sm text-[#5b728b]">
          <p>Отберите нужные записи по полям Bitrix24, проверьте превью, затем укажите файл и целевое поле.</p>
        </div>
      </aside>
    </div>

    <!-- STEP 2: Preview -->
    <div v-if="step === 2" class="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div class="rounded-[22px] border border-[#e5ebf2] bg-white p-5">
        <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 2 — Предпросмотр</div>

        <div class="mb-4 flex items-center gap-3">
          <div class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-2 text-sm font-semibold text-[#2e6bd9]">
            {{ previewTotal }} {{ entityLabel.toLowerCase() }}
          </div>
          <span v-if="previewHasMore" class="text-xs text-[#9aa9b8]">показаны первые 5</span>
        </div>

        <div v-if="previewSample.length" class="mb-4 max-h-[420px] overflow-y-auto rounded-[10px] border border-[#e5ebf2]">
          <div
            v-for="item in previewSample"
            :key="item.id"
            class="flex items-center gap-2 border-b border-[#f0f4f8] px-3 py-2 text-sm last:border-0"
          >
            <span class="text-xs text-[#9aa9b8]">#{{ item.id }}</span>
            <span class="text-[#314256]">{{ item.title }}</span>
          </div>
        </div>

        <div v-if="!previewTotal" class="mb-4 rounded-[10px] border border-[#ffe1c7] bg-[#fff7ef] px-4 py-3 text-sm text-[#c77d2b]">
          По заданному фильтру не найдено ни одной {{ entityLabel.toLowerCase().slice(0, -1) }}а. Вернитесь и измените фильтр.
        </div>

        <div class="flex justify-between">
          <B24Button label="← Назад" color="air-tertiary" size="md" @click="step = 1" />
          <B24Button
            :label="`Далее — указать файл →`"
            color="air-primary"
            size="md"
            :disabled="!previewTotal"
            @click="goFileConfig"
          />
        </div>
      </div>

      <aside class="rounded-[22px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f7fbff_0%,#eef5ff_100%)] p-5">
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Итог фильтра</div>
        <div class="mt-2 text-3xl font-semibold text-[#314256]">{{ previewTotal }}</div>
        <div class="text-sm text-[#5b728b]">записей попадут в массовое добавление файлов</div>
      </aside>
    </div>

    <!-- STEP 3: File config -->
    <div v-if="step === 3" class="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div class="rounded-[22px] border border-[#e5ebf2] bg-white p-5">
        <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 3 — Параметры файла</div>

        <div class="mb-4 rounded-[10px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-2.5 text-sm text-[#2e6bd9]">
          Файл будет прикреплён к <strong>{{ previewTotal }}</strong> {{ entityLabel.toLowerCase() }}
        </div>

        <div class="mb-4">
          <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">Файл <span class="text-[#c24b53]">*</span></label>
          <label class="flex cursor-pointer items-center gap-3 rounded-[10px] border border-dashed border-[#c6d7ee] bg-[#f8fbff] px-4 py-3 transition hover:border-[#2e6bd9]">
            <input type="file" class="hidden" :disabled="uploadingFile" @change="handleFileSelect" />
            <span class="text-base">📎</span>
            <span v-if="uploadingFile" class="text-sm text-[#6f8194]">Загрузка...</span>
            <span v-else-if="selectedUploadFileLabel" class="text-sm font-medium text-[#314256]">{{ selectedUploadFileLabel }}</span>
            <span v-else class="text-sm text-[#9aa9b8]">Выберите файл с компьютера</span>
            <span v-if="selectedUploadFileLabel && !uploadingFile" class="ml-auto text-xs text-[#4caf7d]">✓ готов</span>
          </label>
          <p class="mt-1 text-xs text-[#9aa9b8]">Файл будет прикреплён к каждой из {{ previewTotal }} записей</p>
        </div>

        <div class="mb-4">
          <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">Поле для файла <span class="text-[#c24b53]">*</span></label>
          <div v-if="lockFieldId" class="rounded-[10px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-3 text-sm text-[#2e6bd9]">
            Выбранное поле для файла: <span class="font-semibold">{{ selectedFieldLabel }}</span>
          </div>
          <div v-else-if="loadingFilterFields" class="rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#9aa9b8]">
            Загружаем поля...
          </div>
          <template v-else-if="fileFieldOptions.length">
            <B24SelectMenu
              v-if="!lockFieldId"
              :model-value="fieldId"
              class="w-full"
              placeholder="Выберите поле типа «Файл»"
              :items="fileFieldOptions"
              value-key="value"
              :filter-fields="['label']"
              :search-input="{ placeholder: 'Поиск поля' }"
              @update:model-value="fieldId = String($event || '')"
            />
            <p class="mt-1 text-xs text-[#9aa9b8]">Показаны системные и пользовательские поля типа «Файл» из Bitrix24</p>
          </template>
          <template v-else>
            <input
              v-model="fieldId"
              type="text"
              placeholder="Например: UF_CRM_PROMO_FILE"
              class="w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
            />
            <p class="mt-1 text-xs text-[#b87a30]">Поля типа «Файл» не найдены — введите ID вручную</p>
          </template>
        </div>


        <div class="flex justify-between">
          <B24Button label="← Назад" color="air-tertiary" size="md" @click="step = 2" />
          <B24Button
            :label="`Прикрепить к ${previewTotal} ${entityLabel.toLowerCase()}`"
            color="air-primary"
            size="md"
            :loading="busy"
            @click="runAttach"
          />
        </div>
      </div>

      <aside class="rounded-[22px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f7fbff_0%,#eef5ff_100%)] p-5">
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Памятка</div>
        <div class="mt-3 space-y-3 text-sm text-[#5b728b]">
          <p>Загрузи файл с компьютера — он будет прикреплён к каждой из отфильтрованных записей.</p>
          <p>В поле назначения используй ID пользовательского поля Bitrix24 типа «Файл», например `UF_CRM_*`.</p>
        </div>
      </aside>
    </div>

    <!-- STEP 4: Running / Result -->
    <div v-if="step === 4" class="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <div class="rounded-[22px] border border-[#e5ebf2] bg-white p-5">
        <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 4 — Выполнение</div>

        <div v-if="busy || sessionStatus === 'running'" class="mb-4">
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="font-medium text-[#2e6bd9]">Прикрепление файлов...</span>
            <span class="text-[#6f8194]">{{ progressProcessed }} из {{ progressTotal }}</span>
          </div>
          <div class="h-2 w-full overflow-hidden rounded-full bg-[#dde8f8]">
            <div
              class="h-2 rounded-full bg-[#2e6bd9] transition-all duration-500"
              :style="{ width: progressPercent + '%' }"
            />
          </div>
        </div>

        <div v-if="!busy && sessionStatus !== 'running'" class="mb-4">
          <div
            class="mb-3 rounded-[10px] px-4 py-3 text-sm font-medium"
            :class="sessionStatus === 'completed'
              ? 'border border-[#b3e0c8] bg-[#f0fdf6] text-[#1a7a4a]'
              : 'border border-[#ffd4d4] bg-[#fff5f5] text-[#c24b53]'"
          >
            {{ sessionStatus === 'completed' ? 'Завершено успешно' : 'Завершено с ошибками' }}
          </div>

          <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div class="rounded-[14px] border border-[#e5ebf2] bg-[#f8fafc] p-3 text-center">
              <div class="text-xs uppercase text-[#9aa9b8]">Всего</div>
              <div class="text-lg font-bold text-[#314256]">{{ resultTotal }}</div>
            </div>
            <div class="rounded-[14px] border border-[#b3e0c8] bg-[#f0fdf6] p-3 text-center">
              <div class="text-xs uppercase text-[#4caf7d]">Успешно</div>
              <div class="text-lg font-bold text-[#1a7a4a]">{{ resultSuccessful }}</div>
            </div>
            <div class="rounded-[14px] border border-[#ffd4d4] bg-[#fff5f5] p-3 text-center">
              <div class="text-xs uppercase text-[#e57373]">Ошибок</div>
              <div class="text-lg font-bold text-[#c24b53]">{{ resultFailed }}</div>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between gap-3">
          <B24Button
            v-if="!busy && sessionStatus === 'running'"
            label="Остановить"
            color="air-tertiary"
            size="md"
            :loading="cancelRequested"
            :disabled="cancelRequested"
            @click="cancelAttach"
          />
          <template v-if="!busy && sessionStatus !== 'running'">
            <B24Button label="Новый импорт" color="air-secondary" size="md" @click="reset" />
            <B24Button label="Завершить" color="air-primary" size="md" @click="emit('finish')" />
          </template>
        </div>
      </div>

      <aside class="rounded-[22px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f7fbff_0%,#eef5ff_100%)] p-5">
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Прогресс</div>
        <div class="mt-2 text-3xl font-semibold text-[#314256]">{{ progressPercent }}%</div>
        <div class="mt-1 text-sm text-[#5b728b]">массового добавления файлов завершено</div>
      </aside>
    </div>
  </div>
</template>
