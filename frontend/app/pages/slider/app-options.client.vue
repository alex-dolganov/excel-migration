<script setup lang="ts">
import type { B24Frame } from '@bitrix24/b24jssdk'
import type { AccordionItem } from '@bitrix24/b24ui-nuxt'
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useDashboard } from '@bitrix24/b24ui-nuxt/utils/dashboard'
import { usePageStore } from '~/stores/page'
import { useUserStore } from '~/stores/user'
import { useAppSettingsStore } from '~/stores/appSettings'
import { AjaxError } from '@bitrix24/b24jssdk'
import { buildRoleAssignmentPayload, buildRoleAssignmentsRows } from '~/utils/importer-ui'
import ListIcon from '@bitrix24/b24icons-vue/main/ListIcon'
import CloudErrorIcon from '@bitrix24/b24icons-vue/main/CloudErrorIcon'
import ClockWithArrowIcon from '@bitrix24/b24icons-vue/main/ClockWithArrowIcon'
import Settings5Icon from '@bitrix24/b24icons-vue/editor/Settings5Icon'

definePageMeta({
  layout: false
})

const { t, locales: localesI18n, setLocale } = useI18n()
const page = usePageStore()
const toast = useToast()

// region Init ////
const { $logger, moduleId, initApp, destroyB24Helper, usePullClient, startPullClient, processErrorGlobal } = useAppInit('SliderAppOptionsPage')
const appSettings = useAppSettingsStore()
const user = useUserStore()
const apiStore = useApiStore()
const { $initializeB24Frame } = useNuxtApp()
let $b24: null | B24Frame = null
const { track } = useTelemetry()

const someList = ref([
  15, 30, 60, 90, 120, 180
])

const someValue_1 = ref(appSettings.configSettings.someValue_1)
const someValue_2 = ref(appSettings.configSettings.someValue_2)
const isSomeOption = ref(appSettings.configSettings.isSomeOption)
const activeInfoItem = ref(['0'])
const importerRoleItems = ref<Record<string, any>[]>([])
const importerRoleUserId = ref('')
const importerRoleValue = ref('viewer')
const importerRoleError = ref('')
const importerRoleSuccess = ref('')
const importerRoleBusyAction = ref('')
const canManageImporterRoles = computed(() => user.hasImporterPermission('roles.manage'))
const importerRoleOptions = [
  { value: 'operator', label: 'Оператор' },
  { value: 'viewer', label: 'Только просмотр' },
]
const importerRoleAssignments = computed(() => buildRoleAssignmentsRows(importerRoleItems.value))
const importerRoleTableColumns = computed(() => [
  {
    accessorKey: 'userId',
    header: 'User ID',
    meta: {
      class: {
        th: 'w-[120px]',
        td: 'font-medium text-(--ui-color-base-60)',
      },
    },
  },
  {
    accessorKey: 'roleLabel',
    header: 'Роль',
    meta: {
      class: {
        th: 'w-[180px]',
      },
    },
  },
  {
    accessorKey: 'grantedByUserId',
    header: 'Кем выдано',
    meta: {
      class: {
        th: 'w-[140px]',
      },
    },
  },
  {
    accessorKey: 'updatedAt',
    header: 'Обновлено',
    meta: {
      class: {
        th: 'min-w-[220px]',
      },
    },
  },
])
const infoItems = computed(() => [
  {
    label: t('page.app-options.option.history.title'),
    icon: ClockWithArrowIcon,
    slot: 'history'
  },
  {
    label: 'Роли импорта',
    icon: Settings5Icon,
    slot: 'roles'
  },
  {
    label: t('page.app-options.option.present.title'),
    icon: ListIcon,
    slot: 'present'
  }
] satisfies AccordionItem[])
// endregion ////

const { contextId, isLoading: isLoadingState, load } = useDashboard({ isLoading: ref(false), load: () => {} })
const isLoading = computed({
  get: () => isLoadingState?.value === true,
  set: (value: boolean) => {
    load?.(value, contextId)
  }
})

// region Actions ////
function initData() {
  someValue_1.value = appSettings.configSettings.someValue_1
  someValue_2.value = appSettings.configSettings.someValue_2
  isSomeOption.value = appSettings.configSettings.isSomeOption
}

function resetImporterRoleMessages() {
  importerRoleError.value = ''
  importerRoleSuccess.value = ''
}

function describeError(error: unknown, fallback = 'Не удалось выполнить действие') {
  if (error instanceof AjaxError) {
    return error.message || fallback
  }

  if (error instanceof Error) {
    return error.message || fallback
  }

  return String(error || fallback)
}

async function loadImporterRoles() {
  if (!canManageImporterRoles.value) {
    importerRoleItems.value = []
    return
  }

  importerRoleBusyAction.value = 'load'
  importerRoleError.value = ''

  try {
    const response = await apiStore.getImportRoles()
    importerRoleItems.value = Array.isArray(response.items) ? response.items : []
  } catch (error) {
    importerRoleError.value = describeError(error, 'Не удалось загрузить роли импорта')
  } finally {
    importerRoleBusyAction.value = ''
  }
}

async function saveImporterRole() {
  track('ui_button_click', { 'ui.button_id': 'import_role_save' })
  resetImporterRoleMessages()

  let payload

  try {
    payload = buildRoleAssignmentPayload({
      userId: importerRoleUserId.value,
      role: importerRoleValue.value,
    })
  } catch (error) {
    importerRoleError.value = describeError(error, 'Не удалось подготовить данные роли')
    return
  }

  importerRoleBusyAction.value = 'save'

  try {
    const response = await apiStore.saveImportRole(payload)
    importerRoleUserId.value = ''
    importerRoleValue.value = 'viewer'
    await loadImporterRoles()
    importerRoleSuccess.value = `Роль сохранена для пользователя ${response.item?.b24_user_id ?? payload.b24_user_id}.`
  } catch (error) {
    importerRoleError.value = describeError(error, 'Не удалось сохранить роль импорта')
  } finally {
    importerRoleBusyAction.value = ''
  }
}

async function makeSave() {
  track('ui_button_click', { 'ui.button_id': 'app_options_save' })
  try {
    isLoading.value = true

    appSettings.configSettings.someValue_1 = someValue_1.value
    appSettings.configSettings.someValue_2 = someValue_2.value
    appSettings.configSettings.isSomeOption = isSomeOption.value

    await appSettings.saveSettings()

    await makeSendPullCommand('reload.options', { from: 'app.options' })
    await makeClose()
  } catch (error) {
    $logger.error(error)

    let title = t('page.app-options.error.title')
    let description = ''

    if (error instanceof AjaxError) {
      title = `[${error.name}] ${error.code} (${error.status})`
      description = `${error.message}`
    } else if (error instanceof Error) {
      description = error.message
    } else {
      description = error as string
    }

    toast.add({
      title: title,
      description,
      color: 'air-primary-alert',
      icon: CloudErrorIcon
    })
  } finally {
    isLoading.value = false
  }
}

async function makeSendPullCommand(command: string, params: Record<string, any> = {}) {
  try {
    $logger.warn('>> pull.send >>>', {
      COMMAND: command,
      PARAMS: params,
      MODULE_ID: moduleId
    })

    await $b24?.callMethod(
      'pull.application.event.add',
      {
        COMMAND: command,
        PARAMS: params,
        MODULE_ID: moduleId
      }
    )
  } catch (error) {
    processErrorGlobal(error)
  }
}

async function makeClose() {
  await $b24?.parent.closeApplication()
}

async function makeCancel() {
  track('ui_button_click', { 'ui.button_id': 'app_options_cancel' })
  await $b24?.parent.closeApplication()
}
// endregion ////

// region Lifecycle Hooks ////
onMounted(async () => {
  $logger.info('Hi from slider/app-options')

  try {
    isLoading.value = true

    $b24 = await $initializeB24Frame()
    await initApp($b24, localesI18n, setLocale)

    if( !user.isAdmin ) {
      throw new Error(t('page.app-options.error.notAdmin'))
    }

    page.title = t('page.app-options.seo.title')
    page.description = t('page.app-options.seo.description')

    usePullClient()
    startPullClient()

    initData()
    await loadImporterRoles()
  } catch (error) {
    processErrorGlobal(error)
  } finally {
    isLoading.value = false
  }
})

onUnmounted(() => {
  destroyB24Helper()
})
// endregion ////
</script>

<template>
  <NuxtLayout name="slider">
    <B24Accordion
      v-if="isLoading === false"
      v-model="activeInfoItem"
      type="multiple"
      :items="infoItems"
      :b24ui="{
          root: 'light',
          item: 'mb-[16px] last:mb-0 bg-(--ui-color-bg-content-primary) rounded-(--ui-border-radius-md) border-b-0',
          trigger: 'py-[20px] px-[20px]',
          label: 'text-(length:--ui-font-size-2xl) text-(-ui-color-text-primary)',
          leadingIcon: 'text-(--ui-color-base-60)',
          trailingIcon: 'text-(-ui-color-text-primary)',
        }"
    >
      <template #history>
        <div class="px-4 pb-[12px]">
          <B24Separator class="mb-3" />
          <div class="flex flex-col items-start justify-between gap-[18px]">
            <B24Alert
              color="air-secondary"
              :description="$t('page.app-options.option.history.alert')"
              :b24ui="{ description: 'text-(--ui-color-base-70)' }"
            />

            <B24FormField
              class="w-[190px]"
              :description="$t('page.app-options.option.history.property_1')"
            >
              <B24Select
                v-model="someValue_1"
                :items="someList"
                size="lg"
                class="w-full"
              />
            </B24FormField>
            <B24FormField
              class="w-[190px]"
              :description="$t('page.app-options.option.history.property_2')"
            >
              <B24Input
                v-model="someValue_2"
                size="lg"
                class="w-full"
              />
            </B24FormField>
            <B24FormField
              class="w-[190px]"
              :description="$t('page.app-options.option.history.property_bool')"
            >
              <B24Switch
                v-model="isSomeOption"
                size="lg"
              />
            </B24FormField>
          </div>
        </div>
      </template>
      <template #present>
        <div class="px-4 pb-[12px]">
          <B24Separator class="mb-3" />
          <div class="flex flex-col items-start justify-between gap-[18px]">
            <B24Alert
              color="air-secondary"
              :description="$t('page.app-options.option.present.alert')"
              :b24ui="{ description: 'text-(--ui-color-base-70)' }"
            />
          </div>
        </div>
      </template>
      <template #roles>
        <div class="px-4 pb-[12px]">
          <B24Separator class="mb-3" />
          <div class="flex flex-col gap-[18px]">
            <B24Alert
              color="air-secondary"
              description="Назначайте локальные роли для мастера импорта. Администратор портала сохраняет полный доступ автоматически."
              :b24ui="{ description: 'text-(--ui-color-base-70)' }"
            />

            <template v-if="canManageImporterRoles">
              <div class="grid gap-4 xl:grid-cols-[minmax(260px,320px),1fr]">
                <section class="rounded-[18px] border border-[#dce7f7] bg-[linear-gradient(180deg,#f5faff_0%,#edf5ff_100%)] p-4">
                  <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Новое назначение</div>
                  <div class="mt-3 flex flex-col gap-3">
                    <B24FormField description="Bitrix user ID">
                      <B24Input
                        v-model="importerRoleUserId"
                        size="lg"
                        class="w-full"
                        placeholder="Например, 59"
                      />
                    </B24FormField>
                    <B24FormField description="Роль">
                      <B24Select
                        v-model="importerRoleValue"
                        :items="importerRoleOptions"
                        size="lg"
                        class="w-full"
                      />
                    </B24FormField>
                    <B24Button
                      label="Сохранить роль"
                      color="air-primary"
                      size="lg"
                      :loading="importerRoleBusyAction === 'save'"
                      :disabled="importerRoleBusyAction === 'load'"
                      @click="saveImporterRole"
                    />
                  </div>
                  <div class="mt-3 text-xs text-[#7f92a7]">
                    Здесь управляются только локальные роли `operator` и `viewer`. Роль `portal_admin` приходит из самого Bitrix24.
                  </div>
                </section>

                <section class="rounded-[18px] border border-[#e4e9ef] bg-white p-4">
                  <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-[#8ea0b2]">Текущие назначения</div>
                      <div class="mt-1 text-sm text-[#5f7285]">Список ролей внутри текущего портала.</div>
                    </div>
                    <B24Button
                      label="Обновить"
                      color="air-tertiary"
                      size="sm"
                      :loading="importerRoleBusyAction === 'load'"
                      @click="loadImporterRoles"
                    />
                  </div>

                  <B24Alert
                    v-if="importerRoleSuccess"
                    color="air-primary-success"
                    class="mb-3"
                    :description="importerRoleSuccess"
                    :b24ui="{ description: 'text-(--ui-color-base-80)' }"
                  />
                  <B24Alert
                    v-if="importerRoleError"
                    color="air-primary-alert"
                    class="mb-3"
                    :description="importerRoleError"
                    :b24ui="{ description: 'text-(--ui-color-base-80)' }"
                  />

                  <div class="overflow-hidden rounded-[16px] border border-[#dfe5eb]">
                    <B24Table
                      class="w-full"
                      :loading="importerRoleBusyAction === 'load'"
                      loading-color="air-primary"
                      loading-animation="loading"
                      :columns="importerRoleTableColumns"
                      :data="importerRoleAssignments"
                      empty="Назначений пока нет. Операторов и наблюдателей можно добавить вручную."
                    >
                      <template #roleLabel-cell="{ row }">
                        <B24Badge
                          rounded
                          inverted
                          size="sm"
                          :color="row.original.role === 'operator' ? 'air-primary-copilot' : 'air-secondary-accent-2'"
                          :label="row.original.roleLabel"
                        />
                      </template>
                    </B24Table>
                  </div>
                </section>
              </div>
            </template>

            <B24Alert
              v-else
              color="air-primary-alert"
              description="Права на управление ролями пока недоступны. Обновите приложение, чтобы синхронизировать статус администратора портала."
              :b24ui="{ description: 'text-(--ui-color-base-80)' }"
            />
          </div>
        </div>
      </template>
    </B24Accordion>
    <template #footer>
      <B24Button
        :label="t('page.app-options.actions.save')"
        color="air-primary-success"
        loading-auto
        @click.stop="makeSave"
      />
      <B24Button
        :label="t('page.app-options.actions.cancel')"
        color="air-tertiary"
        @click.stop="makeCancel"
      />
    </template>
  </NuxtLayout>
</template>
