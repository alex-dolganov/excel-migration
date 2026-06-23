<script setup lang="ts">
import type { B24Frame } from '@bitrix24/b24jssdk'
import { onErrorCaptured, onMounted } from 'vue'
import { useDashboard } from '@bitrix24/b24ui-nuxt/utils/dashboard'
import { getInitStageDescription, shouldRenderInitCard } from '~/utils/index-page-init'

const { t, locales: localesI18n, setLocale } = useI18n()

useHead({
  title: t('page.index.seo.title')
})

const { $logger, initApp, processErrorGlobal } = useAppInit('IndexPage')
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
const initStage = ref<'idle' | 'frame' | 'app-init' | 'title' | 'error'>('idle')
const initStageDescription = computed(() => getInitStageDescription(initStage.value))
const isInitStateVisible = computed(() => shouldRenderInitCard({
  isInit: isInit.value,
  initError: initError.value,
  initStage: initStage.value,
}))

const selectedImportMode = ref('')

function onModeSelect(mode: string) {
  selectedImportMode.value = mode
}

function onBackToLanding() {
  selectedImportMode.value = ''
}

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
</script>

<template>
  <div class="h-full w-full min-w-0 overflow-y-auto bg-[#eef2f4]">
    <B24Alert
      v-if="pageRenderError"
      class="m-4"
      color="air-primary-alert"
      title="Client runtime error"
      :description="t('app.runtime_error', { details: pageRenderError })"
    />

    <B24Alert
      v-if="isInitStateVisible && !isInit && !pageRenderError"
      class="m-4"
      color="air-secondary"
      :title="t('app.init_title')"
      :description="initError || initStageDescription"
    />

    <template v-if="isInit && !pageRenderError">
      <div class="flex w-full min-w-0 flex-col gap-4 px-2 py-4 sm:px-4 sm:py-5 lg:px-5 lg:py-6">
        <Transition name="page-switch" mode="out-in">
          <AppLanding
            v-if="!selectedImportMode"
            key="landing"
            @select="onModeSelect"
          />
          <ImporterWorkbench
            v-else
            :initial-import-mode="selectedImportMode"
            @back-to-landing="onBackToLanding"
          />
        </Transition>
      </div>
    </template>
  </div>
</template>

<style>
.page-switch-enter-active,
.page-switch-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}
.page-switch-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.page-switch-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
