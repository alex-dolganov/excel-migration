/**
 * Some info about User
 * @memo not save to settings
 */
export const useUserStore = defineStore(
  'user',
  () => {
    // region State ////
    const id = ref(0)
    const login = ref('')
    const isAdmin = ref(false)
    const importerRole = ref('')
    const importerPermissions = ref<string[]>([])
    const importerIsPortalAdmin = ref(false)
    // endregion ////

    // region Actions ////
    /**
     * Initialize store from batch response data
     * @param data - Raw data from Bitrix24 API
     * @param data.id
     * @param data.name
     * @param data.lastName
     * @param data.isAdmin
     */
    function initFromBatch(data: {
      id?: number
      name?: string
      lastName?: string
      isAdmin?: boolean
    }) {
      id.value = data?.id ?? 0
      login.value = [data?.name, data?.lastName].filter(Boolean).join(' ') || ' '
      isAdmin.value = data.isAdmin || false
    }

    function initImporterPermissions(data: {
      role?: string | null
      permissions?: string[]
      is_portal_admin?: boolean
    }) {
      importerRole.value = String(data?.role || '')
      importerPermissions.value = Array.isArray(data?.permissions)
        ? data.permissions.map((permission) => String(permission || '')).filter(Boolean)
        : []
      importerIsPortalAdmin.value = Boolean(data?.is_portal_admin)
    }

    const hasImporterPermission = (permissionCode: string) => importerPermissions.value.includes(permissionCode)
    // endregion ////

    return {
      id,
      login,
      isAdmin,
      importerRole,
      importerPermissions,
      importerIsPortalAdmin,
      initFromBatch,
      initImporterPermissions,
      hasImporterPermission,
    }
  }
)
