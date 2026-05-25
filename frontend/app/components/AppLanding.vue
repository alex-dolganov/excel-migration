<script setup lang="ts">
const emit = defineEmits<{ select: [mode: string] }>()

const hover = ref<string | null>(null)
const runtimeConfig = useRuntimeConfig()

const palette = {
  simple:   { bg: '#E8F6EE', ink: '#1E8A52', glow: 'rgba(30,138,82,0.18)' },
  advanced: { bg: '#EEF2FF', ink: '#3B47D6', glow: 'rgba(59,71,214,0.18)' },
}

const defaultImportMaxFileSizeBytes = 50 * 1024 * 1024
const normalizedImportMaxFileSizeBytes = Math.max(1, Number(runtimeConfig.public.importMaxFileSizeBytes || defaultImportMaxFileSizeBytes))
const importMaxFileSizeLabel = normalizedImportMaxFileSizeBytes % (1024 * 1024) === 0
  ? `${normalizedImportMaxFileSizeBytes / (1024 * 1024)} МБ`
  : `${(normalizedImportMaxFileSizeBytes / (1024 * 1024)).toFixed(1)} МБ`

const simpleFeatures  = [`Файл XLSX / CSV до ${importMaxFileSizeLabel}`, 'Автосопоставление полей', 'Базовая защита от дублей']
const advancedFeatures = ['Сохранённые шаблоны маппинга', 'Гибкие правила поиска дублей', 'Построчный отчёт + откат']
</script>

<template>
  <div class="overflow-hidden rounded-[30px] border border-[#dfe5eb] bg-white shadow-[0_24px_60px_rgba(23,54,110,0.10)]">

    <!-- ── Hero ── -->
    <section
      class="relative overflow-hidden border-b border-[#e5ebf1] px-8 py-6 sm:px-10"
      style="background: linear-gradient(180deg, #F7F8FA 0%, #FFFFFF 100%)"
    >
      <!-- Dot grid -->
      <div
        class="pointer-events-none absolute inset-0 opacity-[0.3]"
        style="
          background-image: radial-gradient(circle, #D8DCE6 1px, transparent 1.5px);
          background-size: 22px 22px;
          mask-image: radial-gradient(ellipse at top, black 20%, transparent 70%);
          -webkit-mask-image: radial-gradient(ellipse at top, black 20%, transparent 70%);
        "
      />

      <div class="relative flex items-center gap-6">
        <!-- Logo -->
        <img src="/logo.png" alt="Excel Migration" class="h-12 w-auto shrink-0 object-contain" />

        <!-- Text -->
        <div>
          <h1 class="text-[26px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#0F1115]">
            Перенесите Excel в&nbsp;ваш&nbsp;портал
          </h1>
          <p class="mt-1 text-[13px] text-[#5A5E6E]">
            CRM-сущности, задачи, сотрудники — за&nbsp;7 шагов с&nbsp;предпросмотром, проверкой дублей и&nbsp;тестовым запуском.
          </p>
        </div>
      </div>
    </section>

    <!-- ── Mode picker ── -->
    <section class="px-8 pb-8 pt-6 sm:px-10">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <div class="mb-1 text-[10px] uppercase tracking-[0.16em] text-[#8B8FA0]">Шаг 0 · Выбор режима</div>
          <h2 class="text-[18px] font-semibold tracking-tight text-[#0F1115]">Как импортируем?</h2>
        </div>
        <div class="hidden items-center gap-1.5 text-[11.5px] text-[#8B8FA0] sm:flex">
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.2" />
            <path d="M7 4.5v3M7 9.2v.3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
          </svg>
          Режим можно сменить внутри приложения
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">

        <!-- ── Простой ── -->
        <div
          class="relative flex cursor-pointer flex-col overflow-hidden rounded-2xl bg-white transition-all duration-200"
          :style="{
            border: `1.5px solid ${hover === 'simple' ? palette.simple.ink : '#ECEEF3'}`,
            boxShadow: hover === 'simple' ? `0 12px 32px -16px ${palette.simple.glow}` : 'none',
            transform: hover === 'simple' ? 'translateY(-2px)' : 'translateY(0)',
          }"
          @mouseenter="hover = 'simple'"
          @mouseleave="hover = null"
          @click="emit('select', 'simple')"
        >
          <!-- Card hero -->
          <div class="relative h-[90px] shrink-0 overflow-hidden" :style="{ background: palette.simple.bg }">
            <div class="absolute bottom-4 left-0 right-0 flex items-center justify-center gap-3 px-8">
              <div class="h-[5px] flex-1 rounded-full" :style="{ background: palette.simple.ink, opacity: '0.85' }" />
              <div class="h-[5px] flex-1 rounded-full" :style="{ background: palette.simple.ink, opacity: '0.55' }" />
              <div class="h-[5px] flex-1 rounded-full" :style="{ background: palette.simple.ink, opacity: '0.25' }" />
            </div>
            <div class="absolute left-5 top-4 flex items-center gap-2">
              <div class="grid h-8 w-8 place-items-center rounded-xl text-white" :style="{ background: palette.simple.ink }">
                <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                  <path d="M10 1L3 10h4l-1 7 8-10H10l1-6z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                </svg>
              </div>
              <span class="text-[10px] font-semibold uppercase tracking-[0.18em]" :style="{ color: palette.simple.ink }">
                Режим · Простой
              </span>
            </div>
            <span class="absolute right-4 top-4 rounded-full bg-white px-2 py-0.5 text-[10px] font-medium" :style="{ color: palette.simple.ink }">
              ~3 минуты
            </span>
          </div>

          <!-- Card body -->
          <div class="flex flex-1 flex-col px-5 pb-5 pt-4">
            <h3 class="text-[17px] font-semibold tracking-tight text-[#0F1115]">Простой импорт</h3>
            <p class="mt-1.5 text-[12.5px] leading-relaxed text-[#5A5E6E]">
              Загрузите файл, выберите сущность, подтвердите сопоставление — и&nbsp;запускайте.
            </p>
            <ul class="mt-3 space-y-1.5">
              <li v-for="f in simpleFeatures" :key="f" class="flex items-center gap-2 text-[12.5px] text-[#3A3D47]">
                <span class="grid h-4 w-4 shrink-0 place-items-center rounded-full" :style="{ background: palette.simple.bg }">
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                    <path d="M2 4.5l1.6 1.6L7 2.6" :stroke="palette.simple.ink" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                </span>
                {{ f }}
              </li>
            </ul>
            <button
              type="button"
              class="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-xl text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
              :style="{ background: palette.simple.ink }"
              @click.stop="emit('select', 'simple')"
            >
              Начать простой импорт
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
        </div>

        <!-- ── Расширенный ── -->
        <div
          class="relative flex cursor-pointer flex-col overflow-hidden rounded-2xl bg-white transition-all duration-200"
          :style="{
            border: `1.5px solid ${hover === 'advanced' ? palette.advanced.ink : '#ECEEF3'}`,
            boxShadow: hover === 'advanced' ? `0 12px 32px -16px ${palette.advanced.glow}` : 'none',
            transform: hover === 'advanced' ? 'translateY(-2px)' : 'translateY(0)',
          }"
          @mouseenter="hover = 'advanced'"
          @mouseleave="hover = null"
          @click="emit('select', 'advanced')"
        >
          <!-- Card hero -->
          <div class="relative h-[90px] shrink-0 overflow-hidden" :style="{ background: palette.advanced.bg }">
            <svg class="absolute bottom-0 left-0 right-0 w-full" style="height:48px" viewBox="0 0 400 48" preserveAspectRatio="none">
              <g :stroke="palette.advanced.ink" stroke-width="1.5">
                <circle cx="60" cy="10" r="3" :fill="palette.advanced.ink" />
                <circle cx="60" cy="24" r="3" :fill="palette.advanced.ink" opacity=".75" />
                <circle cx="60" cy="38" r="3" :fill="palette.advanced.ink" opacity=".5" />
                <circle cx="340" cy="10" r="3" :fill="palette.advanced.ink" opacity=".5" />
                <circle cx="340" cy="24" r="3" :fill="palette.advanced.ink" />
                <circle cx="340" cy="38" r="3" :fill="palette.advanced.ink" opacity=".75" />
                <path d="M63 10 C 180 10, 220 24, 337 24" fill="none" />
                <path d="M63 24 C 180 24, 220 10, 337 10" fill="none" opacity=".7" />
                <path d="M63 38 C 180 38, 220 38, 337 38" fill="none" opacity=".5" />
              </g>
            </svg>
            <div class="absolute left-5 top-4 z-10 flex items-center gap-2">
              <div class="grid h-8 w-8 place-items-center rounded-xl text-white" :style="{ background: palette.advanced.ink }">
                <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                  <path d="M3 5h12M3 9h12M3 13h12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
                  <circle cx="6" cy="5" r="1.5" fill="#fff" :stroke="palette.advanced.ink" stroke-width="1" />
                  <circle cx="11" cy="9" r="1.5" fill="#fff" :stroke="palette.advanced.ink" stroke-width="1" />
                  <circle cx="8" cy="13" r="1.5" fill="#fff" :stroke="palette.advanced.ink" stroke-width="1" />
                </svg>
              </div>
              <span class="text-[10px] font-semibold uppercase tracking-[0.18em]" :style="{ color: palette.advanced.ink }">
                Режим · Расширенный
              </span>
            </div>
            <span class="absolute right-4 top-4 z-10 rounded-full bg-white px-2 py-0.5 text-[10px] font-medium" :style="{ color: palette.advanced.ink }">
              Шаблоны · Отчёты
            </span>
          </div>

          <!-- Card body -->
          <div class="flex flex-1 flex-col px-5 pb-5 pt-4">
            <h3 class="text-[17px] font-semibold tracking-tight text-[#0F1115]">Расширенный импорт</h3>
            <p class="mt-1.5 text-[12.5px] leading-relaxed text-[#5A5E6E]">
              Шаблоны маппинга, тонкая настройка дублей, тестовый запуск и&nbsp;детальный отчёт.
            </p>
            <ul class="mt-3 space-y-1.5">
              <li v-for="f in advancedFeatures" :key="f" class="flex items-center gap-2 text-[12.5px] text-[#3A3D47]">
                <span class="grid h-4 w-4 shrink-0 place-items-center rounded-full" :style="{ background: palette.advanced.bg }">
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                    <path d="M2 4.5l1.6 1.6L7 2.6" :stroke="palette.advanced.ink" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                </span>
                {{ f }}
              </li>
            </ul>
            <button
              type="button"
              class="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-xl text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
              :style="{ background: palette.advanced.ink }"
              @click.stop="emit('select', 'advanced')"
            >
              Начать расширенный
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>
