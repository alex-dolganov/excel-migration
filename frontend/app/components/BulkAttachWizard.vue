<script setup lang="ts">
const apiStore = useApiStore()

const ENTITY_OPTIONS = [
  { value: 'lead', label: 'Лиды', icon: '📋' },
  { value: 'contact', label: 'Контакты', icon: '👤' },
  { value: 'company', label: 'Компании', icon: '🏢' },
  { value: 'deal', label: 'Сделки', icon: '💼' },
]

// Steps: 1=entity+filter, 2=preview, 3=file config, 4=run+result
const step = ref(1)
const busy = ref(false)
const error = ref('')

// Step 1
const entityType = ref('lead')
const filterStatusId = ref('')
const filterAssignedById = ref('')

// Step 2 — preview result
const previewTotal = ref(0)
const previewSample = ref<{ id: number, title: string }[]>([])
const previewHasMore = ref(false)

// Step 3
const fileUrl = ref('')
const fieldId = ref('')
const fileName = ref('')

// Step 4 — run result
const sessionId = ref('')
const sessionStatus = ref('')
const resultTotal = ref(0)
const resultSuccessful = ref(0)
const resultFailed = ref(0)
const progressProcessed = ref(0)
const progressTotal = ref(0)
const pollingHandle = ref<ReturnType<typeof setInterval> | null>(null)

const computedFilter = computed(() => {
  const f: Record<string, any> = {}
  if (filterStatusId.value.trim()) f['STATUS_ID'] = filterStatusId.value.trim()
  if (filterAssignedById.value.trim()) {
    const parsed = parseInt(filterAssignedById.value.trim())
    if (!isNaN(parsed)) f['ASSIGNED_BY_ID'] = parsed
  }
  return f
})

const entityLabel = computed(() => ENTITY_OPTIONS.find(o => o.value === entityType.value)?.label || entityType.value)

const progressPercent = computed(() => {
  if (!progressTotal.value) return 0
  return Math.min(100, Math.round((progressProcessed.value / progressTotal.value) * 100))
})

async function goPreview() {
  error.value = ''
  busy.value = true
  try {
    const res = await apiStore.crmFilterPreview({ entity_type: entityType.value, filter: computedFilter.value })
    previewTotal.value = res.total
    previewSample.value = res.sample || []
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

async function runAttach() {
  error.value = ''
  if (!fileUrl.value.trim()) { error.value = 'Укажите URL файла'; return }
  if (!fieldId.value.trim()) { error.value = 'Укажите ID поля'; return }

  busy.value = true
  try {
    const created = await apiStore.createBulkAttachSession({
      entity_type: entityType.value,
      filter: computedFilter.value,
      file_url: fileUrl.value.trim(),
      field_id: fieldId.value.trim(),
      file_name: fileName.value.trim(),
    })
    sessionId.value = String(created.item.id)
    sessionStatus.value = 'running'
    step.value = 4
    progressProcessed.value = 0
    progressTotal.value = previewTotal.value

    const runRes = await apiStore.runBulkAttachSession(sessionId.value)
    sessionStatus.value = String(runRes.item?.status || 'completed')
    resultTotal.value = Number(runRes.result?.total || 0)
    resultSuccessful.value = Number(runRes.result?.successful || 0)
    resultFailed.value = Number(runRes.result?.failed || 0)
    progressProcessed.value = resultTotal.value
  } catch (e: any) {
    error.value = String(e?.data?.error || e?.message || 'Ошибка при выполнении')
    sessionStatus.value = 'failed'
  } finally {
    busy.value = false
  }
}

function reset() {
  step.value = 1
  error.value = ''
  filterStatusId.value = ''
  filterAssignedById.value = ''
  fileUrl.value = ''
  fieldId.value = ''
  fileName.value = ''
  sessionId.value = ''
  sessionStatus.value = ''
  resultTotal.value = 0
  resultSuccessful.value = 0
  resultFailed.value = 0
  progressProcessed.value = 0
  progressTotal.value = 0
}
</script>

<template>
  <div class="mx-auto max-w-2xl">
    <div class="mb-6">
      <h2 class="text-xl font-bold text-[#314256]">Массовый импорт файлов (С17)</h2>
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
    <div v-if="step === 1" class="rounded-[18px] border border-[#e5ebf2] bg-white p-5">
      <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 1 — Выберите тип сущности и фильтр</div>

      <div class="mb-4">
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

      <div class="mb-4">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">
          STATUS_ID <span class="font-normal normal-case text-[#b0bec8]">(оставьте пустым — без фильтра по статусу)</span>
        </label>
        <input
          v-model="filterStatusId"
          type="text"
          placeholder="Например: NEW"
          class="w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
        />
      </div>

      <div class="mb-5">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">
          ASSIGNED_BY_ID <span class="font-normal normal-case text-[#b0bec8]">(ID ответственного, необязательно)</span>
        </label>
        <input
          v-model="filterAssignedById"
          type="text"
          placeholder="Например: 42"
          class="w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
        />
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

    <!-- STEP 2: Preview -->
    <div v-if="step === 2" class="rounded-[18px] border border-[#e5ebf2] bg-white p-5">
      <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 2 — Предпросмотр</div>

      <div class="mb-4 flex items-center gap-3">
        <div class="rounded-full border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-2 text-sm font-semibold text-[#2e6bd9]">
          {{ previewTotal }} {{ entityLabel.toLowerCase() }}
        </div>
        <span v-if="previewHasMore" class="text-xs text-[#9aa9b8]">показаны первые 10</span>
      </div>

      <div v-if="previewSample.length" class="mb-4 max-h-48 overflow-y-auto rounded-[10px] border border-[#e5ebf2]">
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

    <!-- STEP 3: File config -->
    <div v-if="step === 3" class="rounded-[18px] border border-[#e5ebf2] bg-white p-5">
      <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 3 — Параметры файла</div>

      <div class="mb-4 rounded-[10px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-2.5 text-sm text-[#2e6bd9]">
        Файл будет прикреплён к <strong>{{ previewTotal }}</strong> {{ entityLabel.toLowerCase() }}
      </div>

      <div class="mb-4">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">URL файла <span class="text-[#c24b53]">*</span></label>
        <input
          v-model="fileUrl"
          type="url"
          placeholder="https://example.com/promo.pdf"
          class="w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
        />
        <p class="mt-1 text-xs text-[#9aa9b8]">Публично доступный URL файла для скачивания</p>
      </div>

      <div class="mb-4">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">ID поля типа «Файл» <span class="text-[#c24b53]">*</span></label>
        <input
          v-model="fieldId"
          type="text"
          placeholder="Например: UF_CRM_PROMO_FILE"
          class="w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
        />
        <p class="mt-1 text-xs text-[#9aa9b8]">User Field или стандартное поле типа «Файл» в Bitrix24</p>
      </div>

      <div class="mb-5">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-[#9aa9b8]">Имя файла <span class="font-normal normal-case text-[#b0bec8]">(необязательно)</span></label>
        <input
          v-model="fileName"
          type="text"
          placeholder="promo.pdf"
          class="w-full rounded-[10px] border border-[#d8e3ef] px-3 py-2 text-sm text-[#314256] outline-none focus:border-[#2e6bd9]"
        />
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

    <!-- STEP 4: Running / Result -->
    <div v-if="step === 4" class="rounded-[18px] border border-[#e5ebf2] bg-white p-5">
      <div class="mb-4 text-sm font-semibold text-[#314256]">Шаг 4 — Выполнение</div>

      <!-- Running state -->
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

      <!-- Completed -->
      <div v-if="!busy && sessionStatus !== 'running'" class="mb-4">
        <div
          class="mb-3 rounded-[10px] px-4 py-3 text-sm font-medium"
          :class="sessionStatus === 'completed'
            ? 'border border-[#b3e0c8] bg-[#f0fdf6] text-[#1a7a4a]'
            : 'border border-[#ffd4d4] bg-[#fff5f5] text-[#c24b53]'"
        >
          {{ sessionStatus === 'completed' ? 'Завершено успешно' : 'Завершено с ошибками' }}
        </div>

        <div class="grid grid-cols-3 gap-3">
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

      <div v-if="!busy" class="flex justify-end">
        <B24Button label="Новый импорт" color="air-secondary" size="md" @click="reset" />
      </div>
    </div>
  </div>
</template>
