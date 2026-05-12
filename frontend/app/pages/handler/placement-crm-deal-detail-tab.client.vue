<script setup lang="ts">
import type { B24Frame } from '@bitrix24/b24jssdk'
import { onErrorCaptured, onMounted } from 'vue'
import { useDashboard } from '@bitrix24/b24ui-nuxt/utils/dashboard'
import { getInitStageDescription, shouldRenderInitCard } from '~/utils/index-page-init'

definePageMeta({
  layout: 'placement'
})

const { t, locales: localesI18n, setLocale } = useI18n()

useHead({
  title: t('page.index.seo.title')
})

const { $logger, initApp, processErrorGlobal } = useAppInit('crm_deal_detail_tab')
const { $initializeB24Frame } = useNuxtApp()
let $b24: null | B24Frame = null

const { contextId, isLoading: isLoadingState, load } = useDashboard({ isLoading: ref(false), load: () => {} })
const isLoading = computed({
  get: () => isLoadingState?.value === true,
  set: (value: boolean) => {
    $logger.info(load, value, contextId, isLoadingState?.value)
    load?.(value, contextId)
  }
})

const isInit = ref(false)
const initError = ref('')
const pageRenderError = ref('')
const initStage = ref<'idle' | 'frame' | 'app-init' | 'fit' | 'title' | 'error'>('idle')
const initStageDescription = computed(() => getInitStageDescription(initStage.value === 'fit' ? 'title' : initStage.value))
const isInitStateVisible = computed(() => shouldRenderInitCard({
  isInit: isInit.value,
  initError: initError.value,
  initStage: initStage.value === 'fit' ? 'title' : initStage.value,
}))

onErrorCaptured((error, instance, info) => {
  const details = [
    error instanceof Error ? error.message : String(error),
    info ? `scope: ${info}` : '',
    instance?.type ? `component: ${String((instance.type as { name?: string })?.name || 'anonymous')}` : '',
  ].filter(Boolean).join(' | ')

  pageRenderError.value = details || 'Unknown client-side rendering error'
  $logger.error('Captured placement render error', error, info)
  return false
})

onMounted(async () => {
  $logger.info('Hi from crm-deal-detail-tab placement')

  try {
    isLoading.value = true
    initStage.value = 'frame'
    $b24 = await $initializeB24Frame()
    initStage.value = 'app-init'
    await initApp($b24, localesI18n, setLocale)

    isInit.value = true
    initStage.value = 'fit'
    await $b24.parent.fitWindow()
    initStage.value = 'title'
    await $b24.parent.setTitle(t('page.index.seo.title'))
    initStage.value = 'idle'
  } catch (error) {
    initStage.value = 'error'
    initError.value = error instanceof Error ? error.message : String(error)
    processErrorGlobal(error, {
      homePageIsHide: true,
      isShowClearError: true,
      clearErrorHref: '/',
    })
  } finally {
    isLoading.value = false
  }
})
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

      <ImporterWorkbench v-if="isInit && !pageRenderError" />
    </div>
  </div>
</template>
