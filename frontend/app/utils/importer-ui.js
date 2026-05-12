export const EMPTY_MAPPING_SELECT_VALUE = '__skip_import__'
export const SUPPORTED_DEDUP_FIELDS = ['EMAIL', 'PHONE', 'TITLE']
export const SUPPORTED_DEDUP_STRATEGIES = ['create', 'skip', 'update', 'ask']
export const ASSIGNABLE_IMPORTER_ROLES = ['operator', 'viewer']
export const IMPORTER_PERMISSION_CODES = [
  'roles.manage',
  'templates.manage',
  'sessions.create',
  'sessions.edit_own',
  'sessions.view',
  'sessions.run',
  'sessions.cancel',
  'reports.view',
]
export const SUPPORTED_IMPORT_ENTITIES = [
  { value: 'lead', label: 'Лиды' },
  { value: 'contact', label: 'Контакты' },
  { value: 'company', label: 'Компании' },
  { value: 'deal', label: 'Сделки' },
  { value: 'linked_company_contact', label: 'Компания + Контакт' },
  { value: 'task', label: 'Задачи' },
  { value: 'task_comment', label: 'Комментарии задач' },
  { value: 'task_checklist_item', label: 'Чек-листы задач' },
  { value: 'task_attachment', label: 'Вложения задач' },
  { value: 'user', label: 'Пользователи' },
  { value: 'department', label: 'Отделы' },
]
const IMPORT_ENTITY_LABELS = new Map(
  SUPPORTED_IMPORT_ENTITIES.map((entity) => [String(entity.value || ''), String(entity.label || '')]),
)
const TASK_IMPORT_FAMILY_LABEL = 'Импорт в задачи'
const CRM_IMPORT_FAMILY_LABEL = 'CRM-сущности'
const LINKED_IMPORT_FAMILY_LABEL = 'Связанный импорт'
const HR_IMPORT_FAMILY_LABEL = 'Пользователи и отделы'
const TASK_IMPORT_SCENARIOS = {
  task: {
    value: 'task',
    label: 'Задачи',
    family: 'task',
    title: 'Задачи и подзадачи',
    description: 'Каждая строка создаёт задачу или подзадачу.',
    minimumFields: ['TITLE', 'RESPONSIBLE_ID или исполнитель по умолчанию'],
    destinationLabel: 'Создаёт отдельную задачу. Для подзадач используйте PARENT_ID.',
    guide: {
      title: 'Импорт задач и подзадач',
      description: 'Каждая строка создаёт отдельную задачу. Для подзадач можно указать родительскую задачу через PARENT_ID.',
      highlights: [
        'Минимум для импорта: TITLE и RESPONSIBLE_ID или выбранный исполнитель по умолчанию.',
        'Если нужен внешний ключ для последующих связей, добавьте XML_ID.',
        'PARENT_ID принимает Bitrix ID задачи или XML_ID.',
      ],
      exampleColumns: ['TITLE', 'RESPONSIBLE_ID', 'XML_ID', 'PARENT_ID'],
    },
  },
  task_comment: {
    value: 'task_comment',
    label: 'Комментарии задач',
    family: 'task',
    title: 'Сообщения в чат задачи',
    description: 'Каждая строка отправляет одно сообщение в чат выбранной задачи.',
    minimumFields: ['TASK_ID', 'AUTHOR_ID или пользователь по умолчанию', 'POST_MESSAGE'],
    destinationLabel: 'Импортирует запись внутрь существующей задачи по TASK_ID.',
    guide: {
      title: 'Импорт сообщений в чат задачи',
      description: 'Каждая строка отправляет одно сообщение в чат выбранной задачи.',
      highlights: [
        'Минимум для импорта: TASK_ID, POST_MESSAGE и AUTHOR_ID или выбранный пользователь по умолчанию.',
        'TASK_ID можно передавать как Bitrix ID задачи или XML_ID.',
        'Если AUTHOR_ID указан в файле, он имеет приоритет над пользователем по умолчанию.',
      ],
      exampleColumns: ['TASK_ID', 'AUTHOR_ID', 'POST_MESSAGE'],
    },
  },
  task_checklist_item: {
    value: 'task_checklist_item',
    label: 'Чек-листы задач',
    family: 'task',
    title: 'Чек-листы в задачи',
    description: 'Каждая строка создаёт один пункт чек-листа в выбранной задаче.',
    minimumFields: ['TASK_ID', 'TITLE'],
    destinationLabel: 'Добавляет пункт чек-листа в существующую задачу по TASK_ID.',
    guide: {
      title: 'Импорт чек-листов в задачи',
      description: 'Каждая строка создаёт один пункт чек-листа в выбранной задаче.',
      highlights: [
        'Минимум для импорта: TASK_ID и TITLE.',
        'TASK_ID можно передавать как Bitrix ID задачи или XML_ID.',
        'IS_COMPLETE позволяет сразу отметить пункт выполненным.',
      ],
      exampleColumns: ['TASK_ID', 'TITLE', 'IS_COMPLETE'],
    },
  },
  task_attachment: {
    value: 'task_attachment',
    label: 'Вложения задач',
    family: 'task',
    title: 'Вложения в задачи',
    description: 'Каждая строка прикладывает файл к выбранной задаче.',
    minimumFields: ['TASK_ID', 'FILE_URL'],
    destinationLabel: 'Прикрепляет файл к существующей задаче по TASK_ID.',
    guide: {
      title: 'Импорт вложений в задачи',
      description: 'Каждая строка скачивает файл из источника и прикрепляет его к выбранной задаче.',
      highlights: [
        'Минимум для импорта: TASK_ID и FILE_URL.',
        'TASK_ID можно передавать как Bitrix ID задачи или XML_ID.',
        'FILE_NAME можно указать отдельно, чтобы переименовать вложение при импорте.',
      ],
      exampleColumns: ['TASK_ID', 'FILE_URL', 'FILE_NAME'],
    },
  },
}
const HR_IMPORT_SCENARIOS = {
  user: {
    value: 'user',
    label: 'Пользователи',
    family: 'hr',
    title: 'Пользователи портала',
    description: 'Каждая строка создаёт или обновляет сотрудника портала Bitrix24.',
    minimumFields: ['NAME', 'EMAIL'],
    destinationLabel: 'Создаёт нового пользователя или обновляет существующего по EMAIL.',
    guide: {
      title: 'Импорт пользователей',
      description: 'Каждая строка файла создаёт нового сотрудника или обновляет существующего.',
      highlights: [
        'Минимум для создания: NAME и EMAIL.',
        'Для обновления существующих пользователей выберите стратегию дублей «Обновить» и укажите EMAIL как ключ.',
        'UF_DEPARTMENT принимает числовой ID отдела, несколько отделов — через запятую.',
        'ACTIVE: «Да» / «1» — активен, «Нет» / «0» — заблокирован.',
      ],
      exampleColumns: ['NAME', 'LAST_NAME', 'EMAIL', 'WORK_POSITION', 'UF_DEPARTMENT'],
    },
  },
  department: {
    value: 'department',
    label: 'Отделы',
    family: 'hr',
    title: 'Организационная структура',
    description: 'Каждая строка создаёт или обновляет отдел в структуре компании.',
    minimumFields: ['NAME'],
    destinationLabel: 'Создаёт отдел или обновляет существующий по названию.',
    guide: {
      title: 'Импорт отделов',
      description: 'Каждая строка создаёт отдел или обновляет существующий по точному совпадению названия.',
      highlights: [
        'Минимум для создания: NAME (название отдела).',
        'PARENT — ID родительского отдела для построения иерархии.',
        'UF_HEAD — ID пользователя Bitrix24, который станет руководителем отдела.',
        'Для обновления выберите стратегию дублей «Обновить» и «Название» как ключ.',
      ],
      exampleColumns: ['NAME', 'PARENT', 'UF_HEAD', 'SORT'],
    },
  },
}

const LINKED_IMPORT_SCENARIOS = {
  linked_company_contact: {
    value: 'linked_company_contact',
    label: 'Компания + Контакт',
    family: 'linked',
    title: 'Связанный импорт компании и контакта',
    description: 'Каждая строка создаёт или обновляет компанию и контакт с автоматической привязкой.',
    minimumFields: ['COMPANY__TITLE', 'CONTACT__NAME или CONTACT__LAST_NAME'],
    destinationLabel: 'Сначала обрабатывает компанию, затем контакт и связывает их автоматически.',
    guide: {
      title: 'Связанный импорт компании и контакта',
      description: 'Одна строка Excel создаёт или обновляет компанию и связанный с ней контакт.',
      highlights: [
        'Компания и контакт загружаются из одной строки и связываются автоматически.',
        'Для компании используйте колонки с префиксом COMPANY__, для контакта с префиксом CONTACT__.',
        'Если в строке заполнена только одна часть, импортируется только она.',
      ],
      exampleColumns: ['COMPANY__TITLE', 'COMPANY__PHONE', 'CONTACT__NAME', 'CONTACT__LAST_NAME', 'CONTACT__EMAIL'],
    },
  },
}

export const FILE_ATTACH_IMPORT_SCENARIOS = {
  crm_files_lead: {
    value: 'crm_files_lead',
    label: 'Лиды',
    family: 'crm_files',
    entityLabel: 'Лид',
    title: 'Массовый импорт файлов в лиды',
    description: 'Каждая строка прикрепляет файл к лиду по его ID.',
    minimumFields: ['ID', 'FILE_URL'],
    destinationLabel: 'Прикрепляет файл к полю типа «Файл» существующего лида по ID.',
  },
  crm_files_contact: {
    value: 'crm_files_contact',
    label: 'Контакты',
    family: 'crm_files',
    entityLabel: 'Контакт',
    title: 'Массовый импорт файлов в контакты',
    description: 'Каждая строка прикрепляет файл к контакту по его ID.',
    minimumFields: ['ID', 'FILE_URL'],
    destinationLabel: 'Прикрепляет файл к полю типа «Файл» существующего контакта по ID.',
  },
  crm_files_company: {
    value: 'crm_files_company',
    label: 'Компании',
    family: 'crm_files',
    entityLabel: 'Компания',
    title: 'Массовый импорт файлов в компании',
    description: 'Каждая строка прикрепляет файл к компании по её ID.',
    minimumFields: ['ID', 'FILE_URL'],
    destinationLabel: 'Прикрепляет файл к полю типа «Файл» существующей компании по ID.',
  },
  crm_files_deal: {
    value: 'crm_files_deal',
    label: 'Сделки',
    family: 'crm_files',
    entityLabel: 'Сделка',
    title: 'Массовый импорт файлов в сделки',
    description: 'Каждая строка прикрепляет файл к сделке по её ID.',
    minimumFields: ['ID', 'FILE_URL'],
    destinationLabel: 'Прикрепляет файл к полю типа «Файл» существующей сделки по ID.',
  },
}

const FILE_ATTACH_IMPORT_FAMILY_LABEL = 'Импорт файлов в CRM'

function isTaskImportEntity(entityType) {
  return Object.hasOwn(TASK_IMPORT_SCENARIOS, String(entityType || '').trim())
}

function isLinkedImportEntity(entityType) {
  return Object.hasOwn(LINKED_IMPORT_SCENARIOS, String(entityType || '').trim())
}

function isHrImportEntity(entityType) {
  return Object.hasOwn(HR_IMPORT_SCENARIOS, String(entityType || '').trim())
}

function isFileAttachEntity(entityType) {
  return Object.hasOwn(FILE_ATTACH_IMPORT_SCENARIOS, String(entityType || '').trim())
}

export function buildImportScenarioSections() {
  const crmItems = SUPPORTED_IMPORT_ENTITIES
    .filter((entity) => !isTaskImportEntity(entity?.value) && !isLinkedImportEntity(entity?.value) && !isHrImportEntity(entity?.value))
    .map((entity) => ({
      value: String(entity?.value || ''),
      label: String(entity?.label || ''),
      family: 'crm',
    }))

  const taskItems = Object.values(TASK_IMPORT_SCENARIOS).map((scenario) => ({
    value: scenario.value,
    label: scenario.label,
    family: scenario.family,
  }))
  const linkedItems = Object.values(LINKED_IMPORT_SCENARIOS).map((scenario) => ({
    value: scenario.value,
    label: scenario.label,
    family: scenario.family,
  }))
  const hrItems = Object.values(HR_IMPORT_SCENARIOS).map((scenario) => ({
    value: scenario.value,
    label: scenario.label,
    family: scenario.family,
  }))

  return [
    {
      id: 'crm',
      title: CRM_IMPORT_FAMILY_LABEL,
      description: 'Прямой импорт в стандартные CRM-разделы.',
      items: crmItems,
    },
    {
      id: 'task',
      title: TASK_IMPORT_FAMILY_LABEL,
      description: 'Выберите, что импортировать в задачи.',
      items: taskItems,
    },
    {
      id: 'linked',
      title: LINKED_IMPORT_FAMILY_LABEL,
      description: 'Одна строка Excel создаёт и связывает несколько сущностей.',
      items: linkedItems,
    },
    {
      id: 'hr',
      title: HR_IMPORT_FAMILY_LABEL,
      description: 'Импорт пользователей и организационной структуры.',
      items: hrItems,
    },
  ]
}

export function buildScenarioSelectionSummary(entityType) {
  const normalizedEntityType = String(entityType || '').trim()
  const taskScenario = TASK_IMPORT_SCENARIOS[normalizedEntityType]
  if (taskScenario) {
    return {
      family: 'task',
      familyLabel: TASK_IMPORT_FAMILY_LABEL,
      selectedLabel: taskScenario.label,
      title: taskScenario.title,
      description: taskScenario.description,
      minimumFields: [...taskScenario.minimumFields],
      destinationLabel: taskScenario.destinationLabel,
    }
  }

  const linkedScenario = LINKED_IMPORT_SCENARIOS[normalizedEntityType]
  if (linkedScenario) {
    return {
      family: 'linked',
      familyLabel: LINKED_IMPORT_FAMILY_LABEL,
      selectedLabel: linkedScenario.label,
      title: linkedScenario.title,
      description: linkedScenario.description,
      minimumFields: [...linkedScenario.minimumFields],
      destinationLabel: linkedScenario.destinationLabel,
    }
  }

  const hrScenario = HR_IMPORT_SCENARIOS[normalizedEntityType]
  if (hrScenario) {
    return {
      family: 'hr',
      familyLabel: HR_IMPORT_FAMILY_LABEL,
      selectedLabel: hrScenario.label,
      title: hrScenario.title,
      description: hrScenario.description,
      minimumFields: [...hrScenario.minimumFields],
      destinationLabel: hrScenario.destinationLabel,
    }
  }

  const fileAttachScenario = FILE_ATTACH_IMPORT_SCENARIOS[normalizedEntityType]
  if (fileAttachScenario) {
    return {
      family: 'crm_files',
      familyLabel: FILE_ATTACH_IMPORT_FAMILY_LABEL,
      selectedLabel: fileAttachScenario.label,
      title: fileAttachScenario.title,
      description: fileAttachScenario.description,
      minimumFields: [...fileAttachScenario.minimumFields],
      destinationLabel: fileAttachScenario.destinationLabel,
    }
  }

  const selectedLabel = getImportEntityLabel(normalizedEntityType)
  return {
    family: 'crm',
    familyLabel: CRM_IMPORT_FAMILY_LABEL,
    selectedLabel,
    title: selectedLabel,
    description: 'Каждая строка создаёт или обновляет отдельную CRM-запись в выбранном разделе.',
    minimumFields: [],
    destinationLabel: 'Импортирует записи напрямую в выбранную CRM-сущность.',
  }
}

export function buildExampleTemplateDownloadMeta(entityType) {
  const normalizedEntityType = String(entityType || '').trim()
  const summary = buildScenarioSelectionSummary(normalizedEntityType)

  return {
    title: `Шаблон для «${summary.selectedLabel}»`,
    description: 'Скачайте пример Excel с заголовками и одной тестовой строкой под выбранный импорт.',
    filename: `${normalizedEntityType || 'import'}-import-example.xlsx`,
  }
}

export function detectSourceFormat(filename) {
  const normalizedName = String(filename || '').trim().toLowerCase()
  if (normalizedName.endsWith('.xlsx')) {
    return 'xlsx'
  }
  if (normalizedName.endsWith('.xls')) {
    return 'xls'
  }
  if (normalizedName.endsWith('.csv')) {
    return 'csv'
  }
  return ''
}

function buildFieldMap(fields) {
  return new Map(
    (Array.isArray(fields) ? fields : [])
      .filter((field) => String(field?.id || '').trim().length > 0)
      .map((field) => [String(field?.id || ''), String(field?.title || '')]),
  )
}

function normalizeFieldType(fieldType) {
  return String(fieldType || 'string').trim().toLowerCase() || 'string'
}

export function buildFieldTypeLabel(fieldType) {
  const normalizedType = normalizeFieldType(fieldType)
  const typeLabels = {
    string: 'Текст',
    text: 'Текст',
    crm_status: 'Статус',
    enumeration: 'Список',
    list: 'Список',
    boolean: 'Да/нет',
    bool: 'Да/нет',
    integer: 'Число',
    int: 'Число',
    double: 'Число',
    float: 'Число',
    money: 'Число',
    number: 'Число',
    date: 'Дата',
    datetime: 'Дата/время',
    crm_multifield: 'Контактное поле',
    phone: 'Телефон',
    email: 'Email',
    web: 'Сайт',
    im: 'Мессенджер',
    file: 'Файл',
  }

  return typeLabels[normalizedType] || normalizedType || 'Текст'
}

function buildAutoMatchLabel(matchType) {
  const normalizedMatchType = String(matchType || '').trim().toLowerCase()
  if (normalizedMatchType === 'exact') {
    return 'Точное'
  }
  if (normalizedMatchType === 'fuzzy') {
    return 'Похожее'
  }
  return ''
}

export function buildFieldGuidanceHints(field) {
  const fieldId = String(field?.id || '').trim().toUpperCase()
  const normalizedType = normalizeFieldType(field?.type)
  const hints = []

  if (fieldId === 'TASK_ID') {
    hints.push('Укажите задачу, в которую нужно импортировать запись.')
    hints.push('Поддерживаются Bitrix ID задачи и внешний ключ XML_ID.')
    return hints
  }

  if (fieldId === 'PARENT_ID') {
    hints.push('Используйте поле для импорта подзадач с привязкой к родительской задаче.')
    hints.push('Поддерживаются Bitrix ID задачи и внешний ключ XML_ID.')
    return hints
  }

  if (
    ['enumeration', 'list', 'crm_status'].includes(normalizedType)
    || (Array.isArray(field?.items) && field.items.length > 0)
  ) {
    hints.push('Выберите соответствие значений в блоке маппинга списков ниже.')
  }

  if (field?.multiple) {
    hints.push('Несколько значений можно передавать через ";" или с новой строки.')
  }

  if (normalizedType === 'date' || normalizedType === 'datetime') {
    hints.push('Поддерживаются форматы: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, MM/DD/YYYY.')
  }

  if (['integer', 'int', 'double', 'float', 'money', 'number'].includes(normalizedType)) {
    hints.push('Для чисел поддерживаются значения с точкой или запятой.')
  }

  if (['boolean', 'bool'].includes(normalizedType)) {
    hints.push('Допустимые значения: 1, 0, true, false, yes, no, да, нет.')
  }

  return hints
}

export function getImportEntityLabel(entityType) {
  const normalizedEntityType = String(entityType || '').trim()
  return IMPORT_ENTITY_LABELS.get(normalizedEntityType) || normalizedEntityType || '—'
}

export function buildEntityScenarioGuide(entityType) {
  const normalizedEntityType = String(entityType || '').trim()
  const taskScenario = TASK_IMPORT_SCENARIOS[normalizedEntityType]
  if (taskScenario) {
    return taskScenario.guide
  }

  const linkedScenario = LINKED_IMPORT_SCENARIOS[normalizedEntityType]
  if (linkedScenario) {
    return linkedScenario.guide
  }

  return {
    title: `Импорт в раздел «${getImportEntityLabel(normalizedEntityType)}»`,
    description: 'Выберите файл, проверьте структуру, сопоставьте обязательные поля и запустите импорт.',
    highlights: [
      'На шаге соответствия полей обязательно сопоставьте поля с пометкой «Обязательное».',
      'Перед запуском проверьте найденные ошибки и потенциальные дубли.',
    ],
    exampleColumns: [],
  }
}

export function buildTaskScenarioQuickStart(entityType) {
  void entityType
  return null
}

function buildFieldIndex(fields) {
  return new Map(
    (Array.isArray(fields) ? fields : [])
      .filter((field) => String(field?.id || '').trim().length > 0)
      .map((field) => [String(field?.id || ''), field]),
  )
}

function normalizeValueMapping(valueMapping) {
  if (!valueMapping || typeof valueMapping !== 'object' || Array.isArray(valueMapping)) {
    return {}
  }

  return Object.entries(valueMapping).reduce((normalized, [sourceValue, targetValue]) => {
    const normalizedSourceValue = String(sourceValue || '').trim()
    const normalizedTargetValue = String(targetValue || '').trim()
    if (!normalizedSourceValue || !normalizedTargetValue) {
      return normalized
    }

    normalized[normalizedSourceValue] = normalizedTargetValue
    return normalized
  }, {})
}

function collectUniqueValues(values) {
  const observedValues = []
  const seenValues = new Set()

  for (const value of Array.isArray(values) ? values : []) {
    const normalizedValue = String(value || '').trim()
    if (!normalizedValue || seenValues.has(normalizedValue)) {
      continue
    }

    seenValues.add(normalizedValue)
    observedValues.push(normalizedValue)
  }

  return observedValues
}

function columnLetterToIndex(column) {
  return String(column || '')
    .trim()
    .toUpperCase()
    .split('')
    .reduce((value, letter) => (value * 26) + (letter.charCodeAt(0) - 64), 0) - 1
}

export function resolveMappingSelectValue(value) {
  return String(value || '') || EMPTY_MAPPING_SELECT_VALUE
}

export function normalizeMappingSelectValue(value) {
  return String(value || '') === EMPTY_MAPPING_SELECT_VALUE ? '' : String(value || '')
}

function buildSelectionIndex(mapping) {
  const index = new Map()

  for (const item of Object.values(mapping || {})) {
    if (!item || typeof item !== 'object') {
      continue
    }

    const column = String(item.column || '')
    const sourceHeader = String(item.source_header || '')
    const targetFieldId = String(item.target_field || '')

    index.set(`${column}:${sourceHeader}`, targetFieldId)
  }

  return index
}

export function buildMappingFieldItems(fields) {
  return [
    { value: EMPTY_MAPPING_SELECT_VALUE, label: 'Не импортировать' },
    ...(Array.isArray(fields) ? fields : []).map((field) => {
      const typeLabel = buildFieldTypeLabel(field?.type)
      const titlePrefix = field?.required ? '★ ' : ''
      const title = String(field?.title || field?.id || '')
      return {
        value: String(field?.id || ''),
        label: `${titlePrefix}${title} (${typeLabel})`,
        description: String(field?.id || ''),
      }
    }).filter((field) => field.value.trim().length > 0),
  ]
}

export function buildMappingRows({ headers, columns, fields, candidateMapping, savedMapping }) {
  const safeHeaders = Array.isArray(headers) ? headers : []
  const safeColumns = Array.isArray(columns) ? columns : []
  const fieldMap = buildFieldMap(fields)
  const fieldIndex = buildFieldIndex(fields)
  const hasSavedMapping = Boolean(savedMapping && Object.keys(savedMapping).length > 0)
  const sourceMapping = hasSavedMapping ? savedMapping : candidateMapping
  const selectionIndex = buildSelectionIndex(hasSavedMapping ? savedMapping : candidateMapping)

  return safeHeaders.map((header, index) => {
    const column = String(safeColumns[index] || '')
    const sourceHeader = String(header || '')
    const targetFieldId = String(selectionIndex.get(`${column}:${sourceHeader}`) || '')
    const mappingItem = targetFieldId ? sourceMapping?.[targetFieldId] : null
    const field = targetFieldId ? fieldIndex.get(targetFieldId) : null
    const valueMapping = normalizeValueMapping(mappingItem?.value_mapping)
    const autoMatchType = hasSavedMapping ? '' : String(mappingItem?.match_type || '').trim().toLowerCase()
    const columnType = String(mappingItem?.column_type || '').trim().toLowerCase()

    const row = {
      key: `${column}:${sourceHeader}`,
      column,
      sourceHeader,
      targetFieldId,
      targetFieldTitle: targetFieldId ? String(fieldMap.get(targetFieldId) || '') : '',
      targetFieldType: field ? normalizeFieldType(field.type) : '',
      targetFieldTypeLabel: field ? buildFieldTypeLabel(field.type) : '',
      targetFieldRequired: Boolean(field?.required),
      targetFieldIsCustom: Boolean(field?.is_custom),
      targetFieldIsMultiple: Boolean(field?.multiple),
      targetFieldGuidanceHints: field ? buildFieldGuidanceHints(field) : [],
      columnType,
    }

    if (autoMatchType) {
      row.autoMatchType = autoMatchType
      row.autoMatchLabel = buildAutoMatchLabel(autoMatchType)
    }

    if (Object.keys(valueMapping).length > 0) {
      row.valueMapping = valueMapping
    }

    return row
  })
}

export function buildRequiredFieldSummary({ fields, mappingRows, defaultFieldIds, ignoreFieldIds } = {}) {
  const ignoredFieldIds = new Set(
    (Array.isArray(ignoreFieldIds) ? ignoreFieldIds : [])
      .map((fieldId) => String(fieldId || '').trim())
      .filter(Boolean),
  )
  const requiredFields = (Array.isArray(fields) ? fields : [])
    .filter((field) => Boolean(field?.required) && !ignoredFieldIds.has(String(field?.id || '').trim()))
    .map((field) => ({
      id: String(field?.id || '').trim(),
      title: String(field?.title || field?.id || '').trim() || 'Поле',
    }))
    .filter((field) => field.id.length > 0)

  const mappedFieldIds = new Set(
    (Array.isArray(mappingRows) ? mappingRows : [])
      .map((row) => String(row?.targetFieldId || '').trim())
      .filter(Boolean),
  )
  for (const fieldId of Array.isArray(defaultFieldIds) ? defaultFieldIds : []) {
    const normalizedFieldId = String(fieldId || '').trim()
    if (normalizedFieldId) {
      mappedFieldIds.add(normalizedFieldId)
    }
  }

  const missingRequired = requiredFields.filter((field) => !mappedFieldIds.has(field.id))

  return {
    totalRequired: requiredFields.length,
    mappedRequired: requiredFields.length - missingRequired.length,
    missingRequiredCount: missingRequired.length,
    hasRequiredFields: requiredFields.length > 0,
    hasMissingRequired: missingRequired.length > 0,
    requiredFields,
    missingRequired,
  }
}

export function buildMappingPayload(rows) {
  return (Array.isArray(rows) ? rows : []).reduce((payload, row) => {
    const targetFieldId = normalizeMappingSelectValue(row?.targetFieldId)
    if (!targetFieldId) {
      return payload
    }

    const mappingItem = {
      source_header: String(row?.sourceHeader || ''),
      column: String(row?.column || ''),
      target_field: targetFieldId,
    }
    const columnType = String(row?.columnType || '').trim().toLowerCase()
    if (columnType) {
      mappingItem.column_type = columnType
    }
    const valueMapping = normalizeValueMapping(row?.valueMapping)
    if (Object.keys(valueMapping).length > 0) {
      mappingItem.value_mapping = valueMapping
    }

    payload[targetFieldId] = mappingItem

    return payload
  }, {})
}

export function buildValueMappingRows({
  previewRows,
  headerRow,
  dataStartRow,
  observedValues,
  mappingRows,
  fields,
  savedMapping,
}) {
  const safePreviewRows = Array.isArray(previewRows) ? previewRows : []
  const safeObservedValues = observedValues && typeof observedValues === 'object' ? observedValues : {}
  const safeMappingRows = Array.isArray(mappingRows) ? mappingRows : []
  const fieldIndex = buildFieldIndex(fields)
  const safeSavedMapping = savedMapping && typeof savedMapping === 'object' ? savedMapping : {}
  const previewStartIndex = Math.max(0, Number(dataStartRow || headerRow || 1) - 1)

  return safeMappingRows.flatMap((mappingRow) => {
    const targetFieldId = String(mappingRow?.targetFieldId || '').trim()
    const field = fieldIndex.get(targetFieldId)
    const fieldItems = Array.isArray(field?.items) ? field.items : []
    if (!targetFieldId || fieldItems.length === 0) {
      return []
    }

    const sourceColumnIndex = columnLetterToIndex(mappingRow?.column)
    if (sourceColumnIndex < 0) {
      return []
    }

    const observedSourceValues = collectUniqueValues(
      safeObservedValues[targetFieldId] || safePreviewRows.slice(previewStartIndex).map((row) => row?.[sourceColumnIndex]),
    )

    if (!observedSourceValues.length) {
      return []
    }

    const valueMapping = {
      ...normalizeValueMapping(safeSavedMapping?.[targetFieldId]?.value_mapping),
      ...normalizeValueMapping(mappingRow?.valueMapping),
    }
    const options = fieldItems
      .map((item) => ({
        value: String(item?.id || '').trim(),
        label: String(item?.title || item?.id || '').trim(),
      }))
      .filter((item) => item.value.length > 0)

    return observedSourceValues.map((sourceValue) => ({
      key: `${targetFieldId}:${sourceValue}`,
      targetFieldId,
      targetFieldTitle: String(field?.title || targetFieldId),
      sourceValue,
      selectedTargetValue: String(valueMapping[sourceValue] || ''),
      options,
    }))
  })
}

export function buildValueMappingStatus(rows) {
  const safeRows = Array.isArray(rows) ? rows : []
  const unmappedValues = safeRows.filter((row) => String(row?.selectedTargetValue || '').trim().length === 0).length

  return {
    totalValues: safeRows.length,
    mappedValues: safeRows.length - unmappedValues,
    unmappedValues,
    hasUnmappedValues: unmappedValues > 0,
  }
}

export function buildUnmappedValueSummary({ unmappedValues, fields } = {}) {
  const fieldMap = buildFieldMap(fields)
  const groups = Object.entries(unmappedValues && typeof unmappedValues === 'object' ? unmappedValues : {})
    .map(([fieldId, values]) => {
      const normalizedValues = collectUniqueValues(values)
      if (!normalizedValues.length) {
        return null
      }

      return {
        fieldId: String(fieldId || ''),
        fieldTitle: String(fieldMap.get(String(fieldId || '')) || fieldId || 'Поле'),
        values: normalizedValues,
        count: normalizedValues.length,
      }
    })
    .filter(Boolean)

  return {
    totalValues: groups.reduce((total, group) => total + Number(group?.count || 0), 0),
    fieldCount: groups.length,
    hasUnmappedValues: groups.length > 0,
    groups,
  }
}

export function buildDedupPayload(settings) {
  const strategy = SUPPORTED_DEDUP_STRATEGIES.includes(String(settings?.strategy || ''))
    ? String(settings?.strategy || '')
    : 'create'

  const fields = Array.from(new Set(
    (Array.isArray(settings?.fields) ? settings.fields : [])
      .map((field) => String(field || '').trim().toUpperCase())
      .filter((field) => SUPPORTED_DEDUP_FIELDS.includes(field)),
  ))

  return {
    strategy,
    fields: strategy === 'create' ? [] : fields,
  }
}

export function buildValidationIssueRows(validationData) {
  return (Array.isArray(validationData?.issues) ? validationData.issues : []).map((issue) => ({
    key: `${Number(issue?.row_number || 0)}:${String(issue?.column || '')}:${String(issue?.target_field || '')}`,
    rowNumber: Number(issue?.row_number || 0),
    column: String(issue?.column || ''),
    sourceHeader: String(issue?.source_header || ''),
    targetField: String(issue?.target_field || ''),
    message: String(issue?.message || ''),
    value: String(issue?.value || '').trim() || '—',
  }))
}

export function buildImportRunRows(importRunData) {
  const statusLabels = IMPORT_RUN_STATUS_LABELS

  return (Array.isArray(importRunData?.results) ? importRunData.results : []).map((item) => {
    const status = String(item?.status || '')
    const linkedRecords = item?.linked_records && typeof item.linked_records === 'object' ? item.linked_records : null
    const recordId = buildImportRunRecordId(item, linkedRecords)
    const duplicateMatchDetails = buildDuplicateMatchDetails(item)
    const dedupMissingDetails = buildDedupMissingDetails(item)
    const errorDetails = String(item?.error || '').trim()
    const linkedDetails = buildLinkedImportRunDetails(linkedRecords)

    return {
      key: `${Number(item?.row_number || 0)}:${status}`,
      rowNumber: Number(item?.row_number || 0),
      status,
      statusLabel: statusLabels[status] || status || '—',
      recordId,
      details: [
        linkedDetails || (recordId !== '—' ? `ID ${recordId}` : errorDetails),
        duplicateMatchDetails,
        dedupMissingDetails,
      ].filter(Boolean).join(' · ') || '—',
    }
  })
}

const IMPORT_RUN_STATUS_LABELS = {
  created: 'Создано',
  updated: 'Обновлено',
  failed: 'Ошибка',
  skipped: 'Пропущено',
  skipped_duplicate: 'Дубль пропущен',
  cancelled: 'Остановлено',
}

const IMPORT_RUN_PROBLEM_STATUSES = new Set(['failed', 'skipped', 'cancelled'])
const IMPORT_RUN_SKIPPED_STATUSES = new Set(['skipped', 'skipped_duplicate'])
const DEDUP_RISK_DETAILS_PREFIX = 'Неполный поиск дублей:'

function normalizeImportRunStatus(value) {
  return String(value || '').trim()
}

function normalizeImportRunReason(item) {
  return String(item?.error || '').trim() || 'Без описания'
}

export function buildImportRunStatusFilters(importRunData) {
  const results = Array.isArray(importRunData?.results) ? importRunData.results : []
  const counts = {
    all: results.length,
    problem: 0,
    dedup_risk: 0,
    created: 0,
    updated: 0,
    failed: 0,
    skipped: 0,
    cancelled: 0,
  }

  for (const item of results) {
    const status = normalizeImportRunStatus(item?.status)

    if (IMPORT_RUN_PROBLEM_STATUSES.has(status)) {
      counts.problem += 1
    }

    if (Array.isArray(item?.dedup_missing_fields) && item.dedup_missing_fields.length > 0) {
      counts.dedup_risk += 1
    }

    if (status === 'created') {
      counts.created += 1
    } else if (status === 'updated') {
      counts.updated += 1
    } else if (status === 'failed') {
      counts.failed += 1
    } else if (IMPORT_RUN_SKIPPED_STATUSES.has(status)) {
      counts.skipped += 1
    } else if (status === 'cancelled') {
      counts.cancelled += 1
    }
  }

  return [
    { id: 'all', label: 'Все', count: counts.all },
    { id: 'problem', label: 'Проблемные', count: counts.problem },
    { id: 'dedup_risk', label: 'Риск дублей', count: counts.dedup_risk },
    { id: 'created', label: 'Создано', count: counts.created },
    { id: 'updated', label: 'Обновлено', count: counts.updated },
    { id: 'failed', label: 'Ошибки', count: counts.failed },
    { id: 'skipped', label: 'Пропущено', count: counts.skipped },
    { id: 'cancelled', label: 'Остановлено', count: counts.cancelled },
  ]
}

export function resolveImportRunFilterId(importRunData, requestedFilterId = '') {
  const filters = buildImportRunStatusFilters(importRunData)
  const availableFilterIds = new Set(filters.filter((item) => Number(item?.count || 0) > 0).map((item) => item.id))
  const normalizedRequestedFilterId = String(requestedFilterId || '').trim()

  if (normalizedRequestedFilterId && availableFilterIds.has(normalizedRequestedFilterId)) {
    return normalizedRequestedFilterId
  }

  if (availableFilterIds.has('problem')) {
    return 'problem'
  }

  return 'all'
}

export function filterImportRunRows(rows, filterId = 'all') {
  const safeRows = Array.isArray(rows) ? rows : []
  const normalizedFilterId = String(filterId || '').trim() || 'all'

  if (normalizedFilterId === 'all') {
    return safeRows
  }

  if (normalizedFilterId === 'problem') {
    return safeRows.filter((row) => IMPORT_RUN_PROBLEM_STATUSES.has(normalizeImportRunStatus(row?.status)))
  }

  if (normalizedFilterId === 'skipped') {
    return safeRows.filter((row) => IMPORT_RUN_SKIPPED_STATUSES.has(normalizeImportRunStatus(row?.status)))
  }

  if (normalizedFilterId === 'dedup_risk') {
    return safeRows.filter((row) => String(row?.details || '').includes(DEDUP_RISK_DETAILS_PREFIX))
  }

  return safeRows.filter((row) => normalizeImportRunStatus(row?.status) === normalizedFilterId)
}

export function buildImportRunProblemGroups(importRunData) {
  const groupsByKey = new Map()

  for (const item of Array.isArray(importRunData?.results) ? importRunData.results : []) {
    const status = normalizeImportRunStatus(item?.status)
    if (!IMPORT_RUN_PROBLEM_STATUSES.has(status)) {
      continue
    }

    const reason = normalizeImportRunReason(item)
    const key = `${status}:${reason}`
    const rowNumber = Number(item?.row_number || 0)
    const existingGroup = groupsByKey.get(key)

    if (existingGroup) {
      existingGroup.count += 1
      if (Number.isInteger(rowNumber) && rowNumber > 0) {
        existingGroup.rowNumbers.push(rowNumber)
      }
      if (!existingGroup.statuses.includes(status)) {
        existingGroup.statuses.push(status)
      }
      continue
    }

    groupsByKey.set(key, {
      key,
      label: IMPORT_RUN_STATUS_LABELS[status] || status || '—',
      reason,
      count: 1,
      rowNumbers: Number.isInteger(rowNumber) && rowNumber > 0 ? [rowNumber] : [],
      statuses: [status],
    })
  }

  return Array.from(groupsByKey.values()).sort((left, right) => {
    return (left.rowNumbers[0] || 0) - (right.rowNumbers[0] || 0)
  })
}

export function buildImportRunRetryState(importRunData) {
  const retryableRowNumbers = (Array.isArray(importRunData?.results) ? importRunData.results : [])
    .filter((item) => ['failed', 'skipped', 'cancelled'].includes(String(item?.status || '').trim()))
    .map((item) => Number(item?.row_number || 0))
    .filter((rowNumber) => Number.isInteger(rowNumber) && rowNumber > 0)

  return {
    retryableRows: retryableRowNumbers.length,
    hasRetryableRows: retryableRowNumbers.length > 0,
    retryableRowNumbers,
  }
}

function flattenFieldValue(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (item && typeof item === 'object') {
          return String(item.VALUE || item.value || '').trim()
        }
        return String(item || '').trim()
      })
      .filter(Boolean)
      .join(', ')
  }

  return String(value || '').trim()
}

function buildDuplicateMatchDetails(item) {
  const fields = (Array.isArray(item?.duplicate_match_fields) ? item.duplicate_match_fields : [])
    .map((field) => String(field || '').trim())
    .filter(Boolean)

  if (!fields.length) {
    return ''
  }

  return `Совпадение: ${fields.join(', ')}`
}

function normalizeLinkedRecord(item) {
  if (!item || typeof item !== 'object') {
    return null
  }

  const id = item?.id === undefined || item?.id === null || item?.id === ''
    ? ''
    : String(item.id)
  const title = String(item?.title || '').trim()
  const status = String(item?.status || '').trim()

  if (!id && !title && !status) {
    return null
  }

  return {
    id,
    title,
    status,
  }
}

function buildImportRunRecordId(item, linkedRecords) {
  const companyRecord = normalizeLinkedRecord(linkedRecords?.company)
  const contactRecord = normalizeLinkedRecord(linkedRecords?.contact)

  if (companyRecord || contactRecord) {
    const labels = []
    if (companyRecord?.id) {
      labels.push(`Компания ${companyRecord.id}`)
    }
    if (contactRecord?.id) {
      labels.push(`Контакт ${contactRecord.id}`)
    }
    if (labels.length > 0) {
      return labels.join(' · ')
    }
  }

  return item?.record_id === undefined || item?.record_id === null || item?.record_id === ''
    ? '—'
    : String(item.record_id)
}

function buildLinkedImportRunDetails(linkedRecords) {
  const companyRecord = normalizeLinkedRecord(linkedRecords?.company)
  const contactRecord = normalizeLinkedRecord(linkedRecords?.contact)
  const details = []

  if (companyRecord) {
    details.push(
      [
        'Компания:',
        companyRecord.title || 'Без названия',
      ].filter(Boolean).join(' ') + (companyRecord.id ? ` · ID ${companyRecord.id}` : ''),
    )
  }

  if (contactRecord) {
    details.push(
      [
        'Контакт:',
        contactRecord.title || 'Без имени',
      ].filter(Boolean).join(' ') + (contactRecord.id ? ` · ID ${contactRecord.id}` : ''),
    )
  }

  return details.join(' · ')
}

function buildLinkedSummaryItem(sectionId, record, index) {
  const normalizedRecord = normalizeLinkedRecord(record)
  if (!normalizedRecord) {
    return null
  }

  const statusLabelMap = {
    created: 'Создано',
    updated: 'Обновлено',
    existing: 'Найдено',
  }

  return {
    key: `${sectionId}:${normalizedRecord.id || 'none'}:${index}`,
    title: normalizedRecord.title || 'Без названия',
    recordId: normalizedRecord.id || '—',
    statusLabel: statusLabelMap[normalizedRecord.status] || 'Обработано',
  }
}

export function buildLinkedImportRunSummary(importRunData, { pageSize = 5, maxPages = 3 } = {}) {
  const cappedPageSize = Math.max(1, Number(pageSize || 0))
  const cappedMaxPages = Math.max(1, Number(maxPages || 0))
  const maxItemsPerSection = cappedPageSize * cappedMaxPages
  const results = Array.isArray(importRunData?.results) ? importRunData.results : []

  const sectionDefinitions = [
    { id: 'company', title: 'Компании' },
    { id: 'contact', title: 'Контакты' },
  ]

  const sections = sectionDefinitions
    .map((section) => {
      const allItems = results
        .map((item, index) => buildLinkedSummaryItem(section.id, item?.linked_records?.[section.id], index))
        .filter(Boolean)

      if (!allItems.length) {
        return null
      }

      return {
        id: section.id,
        title: section.title,
        total: allItems.length,
        pageSize: cappedPageSize,
        pageCount: Math.min(Math.ceil(allItems.length / cappedPageSize), cappedMaxPages),
        hasOverflow: allItems.length > maxItemsPerSection,
        items: allItems.slice(0, maxItemsPerSection),
      }
    })
    .filter(Boolean)

  const hasOverflow = sections.some((section) => section.hasOverflow)

  return {
    hasSummary: sections.length > 0,
    sections,
    hasOverflow,
    overflowMessage: hasOverflow
      ? 'Показаны первые 15 элементов. Остальные детали доступны в CSV-отчете.'
      : '',
  }
}

function formatDedupFieldLabel(fieldId) {
  const labels = {
    EMAIL: 'Email',
    PHONE: 'Телефон',
    TITLE: 'Название',
  }

  const normalizedFieldId = String(fieldId || '').trim()
  return labels[normalizedFieldId] || normalizedFieldId
}

function formatRowCountLabel(count) {
  const normalizedCount = Number(count || 0)
  const mod10 = normalizedCount % 10
  const mod100 = normalizedCount % 100

  if (mod10 === 1 && mod100 !== 11) {
    return 'строке'
  }

  if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) {
    return 'строках'
  }

  return 'строках'
}

export function buildDedupWeakeningNotice(data) {
  const warnings = (Array.isArray(data?.results) ? data.results : [])
    .map((item) => {
      const missingFields = (Array.isArray(item?.dedup_missing_fields) ? item.dedup_missing_fields : [])
        .map((field) => String(field || '').trim())
        .filter(Boolean)
      const rowNumber = Number(item?.row_number || 0)

      if (!missingFields.length || !Number.isInteger(rowNumber) || rowNumber <= 0) {
        return null
      }

      return {
        rowNumber,
        missingFields,
      }
    })
    .filter(Boolean)

  if (!warnings.length) {
    return {
      hasWarnings: false,
      count: 0,
      title: '',
      description: '',
      fieldsLabel: '',
      rowsLabel: '',
      rowNumbers: [],
    }
  }

  const uniqueFields = Array.from(new Set(warnings.flatMap((item) => item.missingFields)))
    .sort((left, right) => {
      const priority = ['EMAIL', 'PHONE', 'TITLE']
      const leftIndex = priority.indexOf(left)
      const rightIndex = priority.indexOf(right)

      if (leftIndex === -1 && rightIndex === -1) {
        return left.localeCompare(right)
      }

      if (leftIndex === -1) {
        return 1
      }

      if (rightIndex === -1) {
        return -1
      }

      return leftIndex - rightIndex
    })
  const rowNumbers = warnings.map((item) => item.rowNumber)

  return {
    hasWarnings: true,
    count: warnings.length,
    title: `Неполный поиск дублей в ${warnings.length} ${formatRowCountLabel(warnings.length)}`,
    description: 'Поиск дублей выполнен не по всем выбранным полям.',
    fieldsLabel: uniqueFields.map((field) => formatDedupFieldLabel(field)).join(', '),
    rowsLabel: rowNumbers.join(', '),
    rowNumbers,
  }
}

function buildDedupMissingDetails(item) {
  const fields = (Array.isArray(item?.dedup_missing_fields) ? item.dedup_missing_fields : [])
    .map((field) => String(field || '').trim())
    .filter(Boolean)

  if (!fields.length) {
    return ''
  }

  return `Неполный поиск дублей: ${fields.join(', ')}`
}

export function buildDryRunRows(dryRunData) {
  const statusLabels = {
    ready: 'Готово',
    ready_update: 'Готово к обновлению',
    skipped: 'Пропущено',
    skipped_duplicate: 'Дубль пропущен',
    pending_decision: 'Ожидает решения',
  }

  return (Array.isArray(dryRunData?.results) ? dryRunData.results : []).map((item) => {
    const fields = item?.fields && typeof item.fields === 'object' ? item.fields : {}
    const details = Object.entries(fields)
      .map(([key, value]) => {
        const normalizedValue = flattenFieldValue(value)
        return normalizedValue ? `${key}: ${normalizedValue}` : ''
      })
      .filter(Boolean)
      .join(' · ')
    const duplicateMatchDetails = buildDuplicateMatchDetails(item)
    const dedupMissingDetails = buildDedupMissingDetails(item)
    const errorDetails = String(item?.error || '').trim()

    return {
      key: `${Number(item?.row_number || 0)}:${String(item?.status || '')}`,
      rowNumber: Number(item?.row_number || 0),
      status: String(item?.status || ''),
      statusLabel: statusLabels[String(item?.status || '')] || String(item?.status || '') || '—',
      details: [details || errorDetails, duplicateMatchDetails, dedupMissingDetails].filter(Boolean).join(' · ') || '—',
    }
  })
}

export function buildSessionHistoryRows(sessions) {
  const statusLabels = {
    draft: 'Черновик',
    uploaded: 'Файл загружен',
    validated: 'Проверено',
    ready: 'Готово',
    running: 'В процессе',
    completed: 'Завершено',
    failed: 'Ошибка',
    cancelled: 'Отменено',
  }

  const buildResultMeta = (status) => {
    const normalizedStatus = String(status || '').trim()
    if (normalizedStatus === 'completed') {
      return {
        resultLabel: 'Успех',
        resultTone: 'success',
      }
    }
    if (normalizedStatus === 'failed') {
      return {
        resultLabel: 'Ошибка',
        resultTone: 'danger',
      }
    }
    if (normalizedStatus === 'cancelled') {
      return {
        resultLabel: 'Остановлен',
        resultTone: 'warning',
      }
    }
    if (normalizedStatus === 'running') {
      return {
        resultLabel: 'В процессе',
        resultTone: 'info',
      }
    }

    return {
      resultLabel: statusLabels[normalizedStatus] || normalizedStatus || '—',
      resultTone: 'neutral',
    }
  }

  const formatUpdatedAtLabel = (value) => {
    const normalizedValue = String(value || '').trim()
    const match = normalizedValue.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
    if (!match) {
      return normalizedValue || '—'
    }

    const [, year, month, day, hour, minute] = match
    return `${day}.${month}.${year} ${hour}:${minute}`
  }

  const buildCountersLabel = (session) => {
    const importRun = session?.summary && typeof session.summary === 'object' ? session.summary.import_run : null
    if (importRun && typeof importRun === 'object') {
      return [
        `Созд. ${Number(importRun.created_rows || 0)}`,
        `Обн. ${Number(importRun.updated_rows || 0)}`,
        `Проп. ${Number(importRun.skipped_rows || 0)}`,
        `Ош. ${Number(importRun.failed_rows || 0)}`,
      ].join(' · ')
    }

    return `${Number(session?.successful_rows || 0)} / ${Number(session?.failed_rows || 0)}`
  }

  return (Array.isArray(sessions) ? sessions : []).map((session) => {
    const status = String(session?.status || '').trim()
    const resultMeta = buildResultMeta(status)
    const updatedAt = String(session?.updated_at || '').trim() || '—'

    return {
      key: String(session?.id || ''),
      fileName: String(session?.original_filename || '').trim() || 'Без имени',
      status,
      entityType: getImportEntityLabel(session?.entity_type),
      statusLabel: statusLabels[status] || status || '—',
      resultLabel: resultMeta.resultLabel,
      resultTone: resultMeta.resultTone,
      counters: buildCountersLabel(session),
      updatedAt,
      updatedAtLabel: formatUpdatedAtLabel(updatedAt),
    }
  })
}

export function buildCollapsibleHistoryState(items, { expanded = false, collapsedCount = 2 } = {}) {
  const safeItems = Array.isArray(items) ? items : []
  const safeCollapsedCount = Math.max(1, Number(collapsedCount || 0))
  const canExpand = safeItems.length > safeCollapsedCount

  return {
    visibleItems: expanded || !canExpand ? safeItems : safeItems.slice(0, safeCollapsedCount),
    hiddenCount: canExpand ? safeItems.length - safeCollapsedCount : 0,
    canExpand,
  }
}

export function shouldRenderInlineWizardFooter(step) {
  return [2, 3].includes(Number(step || 0))
}

export function getWizardAdvanceMode(step, maxAvailableStep) {
  const normalizedStep = Number(step || 0)
  const normalizedMaxStep = Number(maxAvailableStep || 0)

  if (normalizedStep >= 7 && normalizedMaxStep >= 7) {
    return 'finish'
  }

  if (normalizedStep < normalizedMaxStep) {
    return 'next'
  }

  return 'disabled'
}

export function canAdvanceWizard(step, maxAvailableStep, { hasMissingRequiredFields = false } = {}) {
  if (getWizardAdvanceMode(step, maxAvailableStep) === 'disabled') {
    return false
  }

  if (Number(step || 0) === 4 && hasMissingRequiredFields) {
    return false
  }

  return true
}

export function getWizardNextLabel(step) {
  const normalizedStep = Number(step || 0)
  const labels = {
    2: 'Структура',
    3: 'Предпросмотр',
    4: 'Соответствие полей',
    5: 'Обработка дублей',
    6: 'Проверка данных',
    7: 'Результат импорта',
  }

  if (normalizedStep >= 7) {
    return 'Финиш'
  }

  return `Далее: ${labels[normalizedStep + 1] || 'Следующий шаг'}`
}

export function buildMigrationStatusBadge({
  sessionId,
  busyAction,
  errorMessage,
  validationIssueCount,
  importRunFailedRows,
} = {}) {
  if (
    String(errorMessage || '').trim().length > 0
    || Number(validationIssueCount || 0) > 0
    || Number(importRunFailedRows || 0) > 0
  ) {
    return {
      label: 'Ошибка',
      tone: 'error',
    }
  }

  if (String(busyAction || '').trim().length > 0) {
    return {
      label: 'В процессе',
      tone: 'busy',
    }
  }

  if (String(sessionId || '').trim().length > 0) {
    return {
      label: 'Все в порядке',
      tone: 'ok',
    }
  }

  return {
    label: 'Ожидает запуска',
    tone: 'idle',
  }
}

export function buildImporterPermissionState(payload = {}) {
  const requestedPermissions = new Set(
    (Array.isArray(payload?.permissions) ? payload.permissions : [])
      .map((permission) => String(permission || '').trim())
      .filter((permission) => IMPORTER_PERMISSION_CODES.includes(permission)),
  )

  const role = String(payload?.role || '').trim() || null
  const isPortalAdmin = Boolean(payload?.isPortalAdmin)
  const hasDeclaredAccessState = role !== null || requestedPermissions.size > 0 || isPortalAdmin
  const permissions = hasDeclaredAccessState
    ? requestedPermissions
    : new Set(IMPORTER_PERMISSION_CODES)
  const effectiveRole = hasDeclaredAccessState ? role : 'portal_admin'
  const effectiveIsPortalAdmin = hasDeclaredAccessState ? isPortalAdmin : true

  return {
    role: effectiveRole,
    isPortalAdmin: effectiveIsPortalAdmin,
    permissions: Array.from(permissions),
    canManageRoles: permissions.has('roles.manage'),
    canManageTemplates: permissions.has('templates.manage'),
    canCreateSessions: permissions.has('sessions.create'),
    canEditSessions: permissions.has('sessions.edit_own'),
    canViewSessions: permissions.has('sessions.view'),
    canRunSessions: permissions.has('sessions.run'),
    canCancelSessions: permissions.has('sessions.cancel'),
    canViewReports: permissions.has('reports.view'),
    isReadOnly: permissions.has('sessions.view') && !permissions.has('sessions.create') && !permissions.has('sessions.edit_own') && !permissions.has('sessions.run'),
  }
}

export function buildRoleAssignmentsRows(items) {
  const roleLabels = {
    operator: 'Оператор',
    viewer: 'Только просмотр',
  }

  return (Array.isArray(items) ? items : []).map((item) => {
    const role = String(item?.role || '').trim()

    return {
      key: String(item?.id || `${item?.b24_user_id || ''}:${role}`),
      userId: String(item?.b24_user_id || '').trim() || '—',
      role,
      roleLabel: roleLabels[role] || role || '—',
      grantedByUserId: String(item?.granted_by_b24_user_id || '').trim() || '—',
      updatedAt: String(item?.updated_at || '').trim() || '—',
    }
  })
}

export function buildRoleAssignmentPayload({ userId, role } = {}) {
  const normalizedUserId = String(userId || '').trim()
  const parsedUserId = Number.parseInt(normalizedUserId, 10)
  if (!normalizedUserId || !Number.isInteger(parsedUserId) || parsedUserId <= 0) {
    throw new Error('Укажите корректный Bitrix user ID')
  }

  const normalizedRole = String(role || '').trim()
  if (!ASSIGNABLE_IMPORTER_ROLES.includes(normalizedRole)) {
    throw new Error('Выберите корректную роль')
  }

  return {
    b24_user_id: parsedUserId,
    role: normalizedRole,
  }
}
