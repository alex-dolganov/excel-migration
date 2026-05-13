<script setup lang="ts">
import type { B24Frame } from '@bitrix24/b24jssdk'
import { onErrorCaptured, onMounted } from 'vue'
import { useDashboard } from '@bitrix24/b24ui-nuxt/utils/dashboard'
import { getInitStageDescription, shouldRenderInitCard } from '~/utils/index-page-init'

const { t, locales: localesI18n, setLocale } = useI18n()

useHead({
  title: t('page.index.seo.title')
})

const activeTab = ref('excel')

// region Init ////
const { $logger, initApp, processErrorGlobal } = useAppInit('IndexPage')
const { $initializeB24Frame } = useNuxtApp()
let $b24: null | B24Frame = null

// endregion ////

const { contextId, isLoading: isLoadingState, load } = useDashboard({ isLoading: ref(false), load: () => {} })
const isLoading = computed({
  get: () => isLoadingState?.value === true,
  set: (value: boolean) => {
    $logger.info(load, value, contextId, isLoadingState?.value)
    load?.(value, contextId)
  }
})

// region Lifecycle Hooks ////
const isInit = ref(false)
const initError = ref('')
const pageRenderError = ref('')
const initStage = ref<'idle' | 'frame' | 'app-init' | 'title' | 'error'>('idle')
const initStageDescription = computed(() => getInitStageDescription(initStage.value))
const isInitStateVisible = computed(() => shouldRenderInitCard({
  isInit: isInit.value,
  initError: initError.value,
  initStage: initStage.value,
}))

onErrorCaptured((error, instance, info) => {
  const details = [
    error instanceof Error ? error.message : String(error),
    info ? `scope: ${info}` : '',
    instance?.type ? `component: ${String((instance.type as { name?: string })?.name || 'anonymous')}` : '',
  ].filter(Boolean).join(' | ')

  pageRenderError.value = details || 'Unknown client-side rendering error'
  $logger.error('Captured page render error', error, info)
  return false
})

onMounted(async () => {
  $logger.info('Hi from index page')

  try {
    isLoading.value = true
    initStage.value = 'frame'
    $b24 = await $initializeB24Frame()
    initStage.value = 'app-init'
    await initApp($b24, localesI18n, setLocale)

    isInit.value = true
    initStage.value = 'title'
    await $b24.parent.setTitle(t('page.index.seo.title'))
    initStage.value = 'idle'
  } catch (error) {
    initStage.value = 'error'
    initError.value = error instanceof Error ? error.message : String(error)
    processErrorGlobal(error)
  } finally {
    isLoading.value = false
  }
})
// endregion ////
</script>

<template>
  <div class="min-h-screen w-full min-w-0 bg-[#eef2f4]">
    <div class="flex w-full min-w-0 flex-col gap-4 px-2 py-4 sm:px-4 sm:py-5 lg:px-5 lg:py-6">
      <B24Alert
        v-if="pageRenderError"
        color="air-primary-alert"
        title="Client runtime error"
        :description="`Страница упала в рантайме: ${pageRenderError}`"
      />

      <B24Alert
        v-if="isInitStateVisible && !isInit && !pageRenderError"
        color="air-secondary"
        title="Инициализация приложения"
        :description="initError || initStageDescription"
      />

      <template v-if="isInit && !pageRenderError">
        <div class="mb-4 flex gap-2 rounded-[14px] border border-[#e5ebf2] bg-white p-1.5 w-fit">
          <button
            v-for="tab in [{ id: 'excel', label: 'Excel-импорт' }, { id: 'bulk', label: 'Массовый импорт файлов' }]"
            :key="tab.id"
            type="button"
            class="rounded-[10px] px-4 py-1.5 text-sm font-medium transition"
            :class="activeTab === tab.id
              ? 'bg-[#2e6bd9] text-white'
              : 'text-[#5f7285] hover:bg-[#f0f4f8]'"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>
        <ImporterWorkbench v-if="activeTab === 'excel'" />
        <BulkAttachWizard v-if="activeTab === 'bulk'" />
      </template>
    </div>
  </div>
</template>
