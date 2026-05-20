<script setup lang="ts">
const emit = defineEmits<{ select: [mode: string] }>()

const activeInfo = ref<string | null>(null)

function toggleInfo(mode: string, event: MouseEvent) {
  event.stopPropagation()
  activeInfo.value = activeInfo.value === mode ? null : mode
}

const INFO = {
  simple: {
    points: [
      'Загрузите файл Excel или CSV',
      'Выберите тип данных: CRM, задачи или сотрудники',
      'Сопоставьте колонки файла с полями Bitrix24',
      'Запустите импорт — данные появятся в Bitrix24',
    ],
    note: 'Управление дублями и шаблоны сопоставления недоступны. Подходит для разовых переносов.',
  },
  advanced: {
    points: [
      'Всё из простого режима',
      'Шаблоны сопоставления — сохраняйте и переиспользуйте настройки',
      'Полный контроль над дублями: пропустить, обновить или спросить',
      'Тестовый запуск — проверьте данные без реальных изменений в Bitrix24',
      'Расширенная валидация и детальный отчёт по каждой строке',
    ],
    note: 'Рекомендуется для регулярных переносов и больших объёмов данных.',
  },
}
</script>

<template>
  <div class="overflow-hidden rounded-[30px] border border-[#dfe5eb] bg-white shadow-[0_24px_60px_rgba(23,54,110,0.10)]">

    <!-- Hero -->
    <div class="border-b border-[#e5ebf1] bg-[linear-gradient(180deg,#ffffff_0%,#f4f8fe_100%)] px-6 py-8 sm:px-8 sm:py-10">
      <div class="flex flex-col items-center text-center">
        <img
          src="/logo.png"
          alt="Excel Migration"
          class="mb-4 h-20 w-auto object-contain"
        />
        <h1 class="text-[30px] font-semibold leading-tight tracking-tight text-[#2f4254]">Excel Migration</h1>
        <p class="mt-2 text-[14px] leading-relaxed text-[#6c8093]">
          Перенесите данные из Excel и CSV в Bitrix24 — CRM, задачи и сотрудников.
        </p>
      </div>
    </div>

    <!-- Mode selection -->
    <div class="px-6 py-8 sm:px-8">
      <div class="mb-6">
        <h2 class="text-[17px] font-semibold text-[#314256]">Выберите режим импорта</h2>
        <p class="mt-1.5 text-sm text-[#6c8093]">
          Простой — для быстрого старта, расширенный — для полного контроля над процессом.
        </p>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">

        <!-- Simple -->
        <div class="flex flex-col rounded-[22px] border border-[#e5ebf2] bg-[#fbfcfe] p-6 transition-all duration-300 hover:border-[#c2d4f0] hover:bg-white hover:shadow-[0_4px_20px_rgba(46,107,217,0.06)]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">Режим</div>
              <h3 class="mt-1.5 text-[16px] font-semibold text-[#2f4254]">Простой импорт</h3>
            </div>
            <button
              type="button"
              class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition"
              :class="activeInfo === 'simple'
                ? 'border-[#2e6bd9] bg-[#e6eefc] text-[#2e6bd9]'
                : 'border-[#dde8f8] bg-[#f4f9ff] text-[#6898d8] hover:border-[#2e6bd9] hover:text-[#2e6bd9]'"
              @click="toggleInfo('simple', $event)"
            >
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                <path d="M7 6.5v3.5M7 4.2v.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <p class="mt-3 text-sm leading-relaxed text-[#6c8093]">
            Только файл, сущность, простое сопоставление полей и запуск.
          </p>

          <Transition name="info-panel">
            <div v-if="activeInfo === 'simple'" class="mt-4 rounded-[14px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-4">
              <ul class="space-y-2">
                <li
                  v-for="point in INFO.simple.points"
                  :key="point"
                  class="flex items-start gap-2.5 text-[12px] leading-relaxed text-[#5c7592]"
                >
                  <span class="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#2e6bd9]" />
                  {{ point }}
                </li>
              </ul>
              <p class="mt-3 text-[11px] leading-relaxed text-[#9aa9b8]">{{ INFO.simple.note }}</p>
            </div>
          </Transition>

          <div class="mt-auto pt-5">
            <button
              type="button"
              class="w-full rounded-[12px] bg-[#2e6bd9] py-2.5 text-sm font-semibold text-white transition duration-200 hover:bg-[#2560c5]"
              @click="emit('select', 'simple')"
            >
              Начать
            </button>
          </div>
        </div>

        <!-- Advanced -->
        <div class="flex flex-col rounded-[22px] border border-[#e5ebf2] bg-[#fbfcfe] p-6 transition-all duration-300 hover:border-[#c2d4f0] hover:bg-white hover:shadow-[0_4px_20px_rgba(46,107,217,0.06)]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8ea0b2]">Режим</div>
              <h3 class="mt-1.5 text-[16px] font-semibold text-[#2f4254]">Расширенный импорт</h3>
            </div>
            <button
              type="button"
              class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition"
              :class="activeInfo === 'advanced'
                ? 'border-[#2e6bd9] bg-[#e6eefc] text-[#2e6bd9]'
                : 'border-[#dde8f8] bg-[#f4f9ff] text-[#6898d8] hover:border-[#2e6bd9] hover:text-[#2e6bd9]'"
              @click="toggleInfo('advanced', $event)"
            >
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.5"/>
                <path d="M7 6.5v3.5M7 4.2v.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <p class="mt-3 text-sm leading-relaxed text-[#6c8093]">
            Полный сценарий с шаблонами, правилами сопоставления и настройкой дублей.
          </p>

          <Transition name="info-panel">
            <div v-if="activeInfo === 'advanced'" class="mt-4 rounded-[14px] border border-[#d7e7ff] bg-[#f4f9ff] px-4 py-4">
              <ul class="space-y-2">
                <li
                  v-for="point in INFO.advanced.points"
                  :key="point"
                  class="flex items-start gap-2.5 text-[12px] leading-relaxed text-[#5c7592]"
                >
                  <span class="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#2e6bd9]" />
                  {{ point }}
                </li>
              </ul>
              <p class="mt-3 text-[11px] leading-relaxed text-[#9aa9b8]">{{ INFO.advanced.note }}</p>
            </div>
          </Transition>

          <div class="mt-auto pt-5">
            <button
              type="button"
              class="w-full rounded-[12px] bg-[#2e6bd9] py-2.5 text-sm font-semibold text-white transition duration-200 hover:bg-[#2560c5]"
              @click="emit('select', 'advanced')"
            >
              Начать
            </button>
          </div>
        </div>

      </div>

      <p class="mt-5 text-[13px] text-[#b0bec8]">Режим можно изменить в любой момент, нажав «← Режим» внутри приложения.</p>
    </div>

  </div>
</template>

<style scoped>
.info-panel-enter-active,
.info-panel-leave-active {
  transition: opacity 0.2s ease, max-height 0.25s ease;
  overflow: hidden;
  max-height: 300px;
}
.info-panel-enter-from,
.info-panel-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
