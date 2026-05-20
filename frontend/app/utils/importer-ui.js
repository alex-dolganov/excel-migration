export const EMPTY_MAPPING_SELECT_VALUE = '__skip_import__'
export const SUPPORTED_DEDUP_FIELDS = ['EMAIL', 'PHONE', 'TITLE']  // legacy list kept for reference
const _DEDUP_FIELD_RE = /^[A-Za-z][A-Za-z0-9_]*$/
export const SUPPORTED_DEDUP_STRATEGIES = ['create', 'skip', 'update', 'ask']
const IMPORT_MODE_OPTIONS = [
  {
    value: 'simple',
    label: 'Простой импорт',
    description: 'Только файл, сущность, простое сопоставление полей и запуск импорта.',
  },
  {
    value: 'advanced',
    label: 'Расширенный импорт',
    description: 'Полный сценарий с шаблонами, правилами сопоставления и расширенной настройкой дублей.',
  },
]
const IMPORT_MODE_META = {
  simple: {
    value: 'simple',
    label: 'Простой импорт',
    description: 'Только файл, сущность, простое сопоставление полей и запуск импорта.',
    hidesAdvancedTools: true,
    allowsPerRowDedupDecisions: false,
  },
  advanced: {
    value: 'advanced',
    label: 'Расширенный импорт',
    description: 'Полный сценарий с шаблонами, правилами сопоставления и расширенной настройкой дублей.',
    hidesAdvancedTools: false,
    allowsPerRowDedupDecisions: true,
  },
}
const SIMPLE_MODE_DEDUP_UNSUPPORTED_TYPES = new Set([
  'task',
  'task_comment',
  'task_checklist_item',
  'task_attachment',
  'crm_files_lead',
  'crm_files_contact',
  'crm_files_company',
  'crm_files_deal',
  'crm_activity',
  'crm_note',
])
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
  { value: 'smart_process', label: 'Смарт-процессы' },
  { value: 'crm_activity', label: 'Встречи/Звонки CRM' },
  { value: 'crm_note', label: 'Комментарии CRM' },
  { value: 'linked_company_contact', label: 'Компания + Контакт' },
  { value: 'linked_company_deal', label: 'Компания + Сделка' },
  { value: 'linked_contact_company', label: 'Контакт + Компания' },
  { value: 'linked_contact_deal', label: 'Контакт + Сделка' },
  { value: 'linked_deal_company', label: 'Сделка + Компания' },
  { value: 'linked_deal_contact', label: 'Сделка + Контакт' },
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
const CRM_IMPORT_SCENARIOS = {
  crm_activity: {
    value: 'crm_activity',
    label: 'Встречи/Звонки CRM',
    family: 'crm',
    title: 'Импорт встреч/звонков CRM',
    description: 'Каждая строка создаёт отдельную активность CRM для существующей записи.',
    minimumFields: ['OWNER_TYPE_ID', 'OWNER_ID', 'TYPE_ID', 'SUBJECT'],
    destinationLabel: 'Импортирует активность в таймлайн выбранной CRM-записи.',
    guide: {
      title: 'Импорт встреч/звонков CRM',
      description: 'Каждая строка создаёт отдельную активность CRM для существующей записи.',
      highlights: [
        'Минимум для импорта: OWNER_TYPE_ID, OWNER_ID, TYPE_ID и SUBJECT.',
        'Для звонков и email обязательно заполните COMMUNICATIONS_VALUE телефоном или email.',
        'OWNER_TYPE_ID принимает тип сущности CRM: 1 — лид, 2 — сделка, 3 — контакт, 4 — компания.',
      ],
      exampleColumns: ['OWNER_TYPE_ID', 'OWNER_ID', 'TYPE_ID', 'SUBJECT', 'COMMUNICATIONS_VALUE'],
    },
  },
  crm_note: {
    value: 'crm_note',
    label: 'Комментарии CRM',
    family: 'crm',
    title: 'Импорт комментариев CRM',
    description: 'Каждая строка добавляет комментарий в таймлайн существующей CRM-записи.',
    minimumFields: ['ENTITY_TYPE', 'ENTITY_ID', 'COMMENT'],
    destinationLabel: 'Импортирует комментарий напрямую в таймлайн выбранной CRM-сущности.',
    guide: {
      title: 'Импорт комментариев CRM',
      description: 'Каждая строка добавляет комментарий в таймлайн существующей CRM-записи.',
      highlights: [
        'Минимум для импорта: ENTITY_TYPE, ENTITY_ID и COMMENT.',
        'ENTITY_TYPE можно передавать как код сущности: lead, contact, company или deal.',
        'Комментарий попадёт в таймлайн записи как обычная заметка CRM.',
      ],
      exampleColumns: ['ENTITY_TYPE', 'ENTITY_ID', 'COMMENT', 'CREATED_TIME'],
    },
  },
}
const CRM_IMPORT_SCENARIO_GUIDES = {
  contact: {
    title: 'Импорт контактов',
    description: 'Каждая строка создаёт или обновляет отдельный контакт в CRM.',
    highlights: [
      'Название компании в обычном импорте контактов не создаёт связь автоматически.',
      'Для привязки к существующей компании используйте поле COMPANY_ID и передавайте Bitrix24 ID компании.',
      'Если в исходном файле есть только название компании, используйте сценарий «Компания + Контакт».',
    ],
    exampleColumns: ['NAME', 'LAST_NAME', 'PHONE', 'EMAIL', 'COMPANY_ID'],
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

export const LINKED_IMPORT_SCENARIOS = {
  linked_company_contact: {
    value: 'linked_company_contact',
    label: 'Компания + Контакт',
    family: 'linked',
    primaryEntityType: 'company',
    secondaryEntityType: 'contact',
    linkedEntities: [
      {
        id: 'company',
        label: 'Компания',
        sourceEntityType: 'company',
        prefix: 'COMPANY__',
      },
      {
        id: 'contact',
        label: 'Контакт',
        sourceEntityType: 'contact',
        prefix: 'CONTACT__',
      },
    ],
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
  linked_company_deal: {
    value: 'linked_company_deal',
    label: 'Компания + Сделка',
    family: 'linked',
    primaryEntityType: 'company',
    secondaryEntityType: 'deal',
    linkedEntities: [
      {
        id: 'company',
        label: 'Компания',
        sourceEntityType: 'company',
        prefix: 'COMPANY__',
      },
      {
        id: 'deal',
        label: 'Сделка',
        sourceEntityType: 'deal',
        prefix: 'DEAL__',
      },
    ],
    title: 'Связанный импорт компании и сделки',
    description: 'Каждая строка создаёт или обновляет компанию и связанную с ней сделку.',
    minimumFields: ['COMPANY__TITLE', 'DEAL__TITLE'],
    destinationLabel: 'Сначала обрабатывает компанию, затем создаёт или обновляет сделку и связывает её с компанией.',
    guide: {
      title: 'Связанный импорт компании и сделки',
      description: 'Одна строка Excel создаёт или обновляет компанию и связанную с ней сделку.',
      highlights: [
        'Компания и сделка загружаются из одной строки и связываются автоматически.',
        'Для компании используйте колонки с префиксом COMPANY__, для сделки с префиксом DEAL__.',
        'Если для сделки нужны суммы и этапы, используйте DEAL__OPPORTUNITY, DEAL__CURRENCY_ID и DEAL__STAGE_ID.',
      ],
      exampleColumns: ['COMPANY__TITLE', 'COMPANY__PHONE', 'DEAL__TITLE', 'DEAL__OPPORTUNITY', 'DEAL__CURRENCY_ID', 'DEAL__STAGE_ID'],
    },
  },
  linked_contact_company: {
    value: 'linked_contact_company',
    label: 'Контакт + Компания',
    family: 'linked',
    primaryEntityType: 'contact',
    secondaryEntityType: 'company',
    linkedEntities: [
      {
        id: 'contact',
        label: 'Контакт',
        sourceEntityType: 'contact',
        prefix: 'CONTACT__',
      },
      {
        id: 'company',
        label: 'Компания',
        sourceEntityType: 'company',
        prefix: 'COMPANY__',
      },
    ],
    title: 'Связанный импорт контакта и компании',
    description: 'Каждая строка создаёт или обновляет контакт и компанию с автоматической привязкой.',
    minimumFields: ['CONTACT__NAME или CONTACT__LAST_NAME', 'COMPANY__TITLE'],
    destinationLabel: 'Сначала обрабатывает контакт, затем создаёт или обновляет компанию и связывает её с контактом.',
    guide: {
      title: 'Связанный импорт контакта и компании',
      description: 'Одна строка Excel создаёт или обновляет контакт и связанную с ним компанию.',
      highlights: [
        'Контакт и компания загружаются из одной строки и связываются автоматически.',
        'Для контакта используйте колонки с префиксом CONTACT__, для компании с префиксом COMPANY__.',
        'Для нескольких компаний у одного контакта повторяйте строки с одним CONTACT__EXTERNAL_KEY.',
      ],
      exampleColumns: ['CONTACT__EXTERNAL_KEY', 'CONTACT__NAME', 'CONTACT__LAST_NAME', 'COMPANY__TITLE', 'COMPANY__PHONE', 'COMPANY__EMAIL'],
    },
  },
  linked_contact_deal: {
    value: 'linked_contact_deal',
    label: 'Контакт + Сделка',
    family: 'linked',
    primaryEntityType: 'contact',
    secondaryEntityType: 'deal',
    linkedEntities: [
      {
        id: 'contact',
        label: 'Контакт',
        sourceEntityType: 'contact',
        prefix: 'CONTACT__',
      },
      {
        id: 'deal',
        label: 'Сделка',
        sourceEntityType: 'deal',
        prefix: 'DEAL__',
      },
    ],
    title: 'Связанный импорт контакта и сделки',
    description: 'Каждая строка создаёт или обновляет контакт и связанную с ним сделку.',
    minimumFields: ['CONTACT__NAME или CONTACT__LAST_NAME', 'DEAL__TITLE'],
    destinationLabel: 'Сначала обрабатывает контакт, затем создаёт или обновляет сделку и связывает её с контактом.',
    guide: {
      title: 'Связанный импорт контакта и сделки',
      description: 'Одна строка Excel создаёт или обновляет контакт и связанную с ним сделку.',
      highlights: [
        'Контакт и сделка загружаются из одной строки и связываются автоматически.',
        'Для контакта используйте колонки с префиксом CONTACT__, для сделки с префиксом DEAL__.',
        'Если для сделки нужны суммы и этапы, используйте DEAL__OPPORTUNITY, DEAL__CURRENCY_ID и DEAL__STAGE_ID.',
      ],
      exampleColumns: ['CONTACT__NAME', 'CONTACT__LAST_NAME', 'CONTACT__PHONE', 'DEAL__TITLE', 'DEAL__OPPORTUNITY', 'DEAL__STAGE_ID'],
    },
  },
  linked_deal_company: {
    value: 'linked_deal_company',
    label: 'Сделка + Компания',
    family: 'linked',
    primaryEntityType: 'deal',
    secondaryEntityType: 'company',
    linkedEntities: [
      {
        id: 'deal',
        label: 'Сделка',
        sourceEntityType: 'deal',
        prefix: 'DEAL__',
      },
      {
        id: 'company',
        label: 'Компания',
        sourceEntityType: 'company',
        prefix: 'COMPANY__',
      },
    ],
    title: 'Связанный импорт сделки и компании',
    description: 'Каждая строка создаёт или обновляет сделку и связанную с ней компанию.',
    minimumFields: ['DEAL__TITLE', 'COMPANY__TITLE'],
    destinationLabel: 'Сначала обрабатывает сделку, затем создаёт или обновляет компанию и привязывает её к сделке.',
    guide: {
      title: 'Связанный импорт сделки и компании',
      description: 'Одна строка Excel создаёт или обновляет сделку и связанную с ней компанию.',
      highlights: [
        'Сделка и компания загружаются из одной строки и связываются автоматически.',
        'Для сделки используйте колонки с префиксом DEAL__, для компании с префиксом COMPANY__.',
        'У одной сделки может быть только одна компания, поэтому в шаблоне достаточно данных самой сделки и компании.',
      ],
      exampleColumns: ['DEAL__TITLE', 'DEAL__OPPORTUNITY', 'DEAL__CURRENCY_ID', 'DEAL__STAGE_ID', 'COMPANY__TITLE', 'COMPANY__PHONE', 'COMPANY__EMAIL'],
    },
  },
  linked_deal_contact: {
    value: 'linked_deal_contact',
    label: 'Сделка + Контакт',
    family: 'linked',
    primaryEntityType: 'deal',
    secondaryEntityType: 'contact',
    linkedEntities: [
      {
        id: 'deal',
        label: 'Сделка',
        sourceEntityType: 'deal',
        prefix: 'DEAL__',
      },
      {
        id: 'contact',
        label: 'Контакт',
        sourceEntityType: 'contact',
        prefix: 'CONTACT__',
      },
    ],
    title: 'Связанный импорт сделки и контакта',
    description: 'Каждая строка создаёт или обновляет сделку и привязывает к ней контакт.',
    minimumFields: ['DEAL__TITLE', 'CONTACT__NAME или CONTACT__LAST_NAME'],
    destinationLabel: 'Сначала обрабатывает сделку, затем создаёт или обновляет контакт и привязывает его к сделке.',
    guide: {
      title: 'Связанный импорт сделки и контакта',
      description: 'Одна строка Excel создаёт или обновляет сделку и связанный с ней контакт.',
      highlights: [
        'Сделка и контакт загружаются из одной строки и связываются автоматически.',
        'Для нескольких контактов к одной сделке повторяйте строки с одним DEAL__EXTERNAL_KEY.',
        'Для сделки используйте колонки с префиксом DEAL__, для контакта с префиксом CONTACT__.',
      ],
      exampleColumns: ['DEAL__EXTERNAL_KEY', 'DEAL__TITLE', 'DEAL__OPPORTUNITY', 'CONTACT__NAME', 'CONTACT__LAST_NAME', 'CONTACT__EMAIL'],
    },
  },
}

export function buildImportModeOptions() {
  return IMPORT_MODE_OPTIONS.map((item) => ({ ...item }))
}

export function getImportModeMeta(mode) {
  const normalizedMode = String(mode || '').trim().toLowerCase()
  const selectedMode = Object.hasOwn(IMPORT_MODE_META, normalizedMode) ? normalizedMode : 'advanced'
  return { ...IMPORT_MODE_META[selectedMode] }
}

export function buildSimpleDedupPreset({ entityType, mappingRows } = {}) {
  const normalizedEntityType = String(entityType || '').trim().toLowerCase()
  if (!normalizedEntityType || SIMPLE_MODE_DEDUP_UNSUPPORTED_TYPES.has(normalizedEntityType)) {
    return {
      strategy: 'create',
      condition: 'any',
      fields: [],
      available: false,
    }
  }

  const mappedFields = Array.from(new Set(
    (Array.isArray(mappingRows) ? mappingRows : [])
      .map((row) => String(row?.targetFieldId || '').trim().toUpperCase())
      .map((fieldId) => fieldId.includes('__') ? fieldId.split('__').pop() : fieldId)
      .filter(Boolean),
  ))
  const recommendedFields = SUPPORTED_DEDUP_FIELDS.filter((fieldId) => mappedFields.includes(fieldId))

  return {
    strategy: recommendedFields.length ? 'update' : 'create',
    condition: 'any',
    fields: recommendedFields,
    available: recommendedFields.length > 0,
  }
}

const LINKED_ENTITY_FIELD_PREFIXES = {
  company: 'COMPANY__',
  contact: 'CONTACT__',
  deal: 'DEAL__',
}
const LINKED_FIELD_PREFIX_LABELS = {
  COMPANY__: 'Компания',
  CONTACT__: 'Контакт',
  DEAL__: 'Сделка',
}

const LINKED_ENTITY_DISPLAY_META = {
  company: {
    singular: 'Компания',
    plural: 'Компании',
    emptyTitle: 'Без названия',
  },
  contact: {
    singular: 'Контакт',
    plural: 'Контакты',
    emptyTitle: 'Без имени',
  },
  deal: {
    singular: 'Сделка',
    plural: 'Сделки',
    emptyTitle: 'Без названия',
  },
}
const LINKED_ENTITY_OPTION_META = {
  company: { value: 'company', label: 'Компания' },
  contact: { value: 'contact', label: 'Контакт' },
  deal: { value: 'deal', label: 'Сделка' },
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

export function isLinkedImportEntityType(entityType) {
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
    .filter((entity) => !isTaskImportEntity(entity?.value) && !isLinkedImportEntityType(entity?.value) && !isHrImportEntity(entity?.value))
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

  const crmScenario = CRM_IMPORT_SCENARIOS[normalizedEntityType]
  if (crmScenario) {
    return {
      family: 'crm',
      familyLabel: CRM_IMPORT_FAMILY_LABEL,
      selectedLabel: crmScenario.label,
      title: crmScenario.title,
      description: crmScenario.description,
      minimumFields: [...crmScenario.minimumFields],
      destinationLabel: crmScenario.destinationLabel,
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

export function buildLinkedPrimaryEntityOptions() {
  return Array.from(new Set(
    Object.values(LINKED_IMPORT_SCENARIOS)
      .map((scenario) => String(scenario?.primaryEntityType || '').trim())
      .filter(Boolean),
  )).map((entityType) => ({
    value: entityType,
    label: LINKED_ENTITY_OPTION_META[entityType]?.label || entityType,
  }))
}

export function buildLinkedSecondaryEntityOptions(primaryEntityType) {
  const normalizedPrimaryEntityType = String(primaryEntityType || '').trim()
  if (!normalizedPrimaryEntityType) {
    return []
  }

  return Object.values(LINKED_IMPORT_SCENARIOS)
    .filter((scenario) => String(scenario?.primaryEntityType || '').trim() === normalizedPrimaryEntityType)
    .map((scenario) => String(scenario?.secondaryEntityType || '').trim())
    .filter(Boolean)
    .map((entityType) => ({
      value: entityType,
      label: LINKED_ENTITY_OPTION_META[entityType]?.label || entityType,
    }))
}

export function resolveLinkedStrategyEntityType(primaryEntityType, secondaryEntityType) {
  const normalizedPrimaryEntityType = String(primaryEntityType || '').trim()
  const normalizedSecondaryEntityType = String(secondaryEntityType || '').trim()

  if (!normalizedPrimaryEntityType || !normalizedSecondaryEntityType) {
    return ''
  }

  const matchedScenario = Object.values(LINKED_IMPORT_SCENARIOS).find((scenario) => (
    String(scenario?.primaryEntityType || '').trim() === normalizedPrimaryEntityType
    && String(scenario?.secondaryEntityType || '').trim() === normalizedSecondaryEntityType
  ))
  return String(matchedScenario?.value || '').trim()
}

export function resolveLinkedStrategyPair(entityType) {
  const scenario = LINKED_IMPORT_SCENARIOS[String(entityType || '').trim()]
  if (!scenario) {
    return {
      primaryEntityType: '',
      secondaryEntityType: '',
    }
  }

  return {
    primaryEntityType: String(scenario.primaryEntityType || '').trim(),
    secondaryEntityType: String(scenario.secondaryEntityType || '').trim(),
  }
}

export function buildLinkedImportEntityGroups(entityType) {
  const normalizedEntityType = String(entityType || '').trim()
  const linkedScenario = LINKED_IMPORT_SCENARIOS[normalizedEntityType]
  if (!linkedScenario || !Array.isArray(linkedScenario.linkedEntities)) {
    return []
  }

  return linkedScenario.linkedEntities.map((item) => ({
    id: String(item?.id || ''),
    label: String(item?.label || ''),
    sourceEntityType: String(item?.sourceEntityType || ''),
    prefix: String(item?.prefix || ''),
  })).filter((item) => item.id && item.sourceEntityType && item.prefix)
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
    crm_category: 'Воронка',
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

function buildAutoMatchReasonLabel(matchReason) {
  const normalizedMatchReason = String(matchReason || '').trim().toLowerCase()
  if (normalizedMatchReason === 'alias_rule') {
    return 'Пользовательское правило'
  }
  if (normalizedMatchReason === 'translit_alias') {
    return 'Транслит / синоним'
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

  if (fieldId === 'COMPANY_ID') {
    hints.push('Укажите Bitrix24 ID компании, чтобы привязать запись к существующей компании.')
    hints.push('Если у вас есть только название компании, используйте сценарий «Компания + Контакт».')
    return hints
  }

  if (
    ['enumeration', 'list', 'crm_status', 'crm_category'].includes(normalizedType)
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

export function getImportEntityLabel(entityType, entityConfig = null) {
  const normalizedEntityType = String(entityType || '').trim()
  if (normalizedEntityType === 'smart_process') {
    const smartProcessTitle = String(entityConfig?.title || '').trim()
    if (smartProcessTitle) {
      return `Смарт-процесс: ${smartProcessTitle}`
    }
  }
  return IMPORT_ENTITY_LABELS.get(normalizedEntityType) || normalizedEntityType || '—'
}

export function buildEntityScenarioGuide(entityType) {
  const normalizedEntityType = String(entityType || '').trim()
  const taskScenario = TASK_IMPORT_SCENARIOS[normalizedEntityType]
  if (taskScenario) {
    return taskScenario.guide
  }

  const crmScenario = CRM_IMPORT_SCENARIOS[normalizedEntityType]
  if (crmScenario) {
    return crmScenario.guide
  }

  const crmGuide = CRM_IMPORT_SCENARIO_GUIDES[normalizedEntityType]
  if (crmGuide) {
    return crmGuide
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

function normalizeOptionMatchValue(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u0400-\u04ff]+/g, '')
}

function resolveAutoValueMapping(sourceValue, options) {
  const normalizedSourceValue = normalizeOptionMatchValue(sourceValue)
  if (!normalizedSourceValue) {
    return ''
  }

  for (const option of Array.isArray(options) ? options : []) {
    const optionValue = String(option?.value || '').trim()
    const optionLabel = String(option?.label || '').trim()
    if (!optionValue) {
      continue
    }

    if (
      normalizeOptionMatchValue(optionValue) === normalizedSourceValue
      || normalizeOptionMatchValue(optionLabel) === normalizedSourceValue
    ) {
      return optionValue
    }
  }

  return ''
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

function normalizeCandidateSuggestions(items, fieldMap) {
  const seenSuggestions = new Set()

  return (Array.isArray(items) ? items : []).reduce((normalized, item) => {
    const targetFieldId = String(item?.target_field || '').trim()
    if (!targetFieldId || seenSuggestions.has(targetFieldId)) {
      return normalized
    }

    seenSuggestions.add(targetFieldId)
    const matchType = String(item?.match_type || '').trim().toLowerCase()
    const matchReason = String(item?.match_reason || '').trim().toLowerCase()
    normalized.push({
      targetFieldId,
      targetFieldTitle: String(item?.target_field_title || fieldMap.get(targetFieldId) || targetFieldId),
      matchType,
      matchLabel: buildAutoMatchLabel(matchType),
      matchReason,
      matchReasonLabel: buildAutoMatchReasonLabel(matchReason),
    })
    return normalized
  }, [])
}

export function buildMappingRows({ headers, columns, fields, candidateMapping, candidateSuggestions, savedMapping }) {
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
    const autoMatchReason = hasSavedMapping ? '' : String(mappingItem?.match_reason || '').trim().toLowerCase()
    const columnType = String(mappingItem?.column_type || '').trim().toLowerCase()
    const normalizedCandidateSuggestions = normalizeCandidateSuggestions(
      candidateSuggestions?.[`${column}:${sourceHeader}`],
      fieldMap,
    )

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
    }

    if (columnType) {
      row.columnType = columnType
    }

    if (autoMatchType) {
      row.autoMatchType = autoMatchType
      row.autoMatchLabel = buildAutoMatchLabel(autoMatchType)
    }

    if (autoMatchReason) {
      row.autoMatchReason = autoMatchReason
      row.autoMatchReasonLabel = buildAutoMatchReasonLabel(autoMatchReason)
    }

    if (normalizedCandidateSuggestions.length > 0) {
      row.candidateSuggestions = normalizedCandidateSuggestions
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
      selectedTargetValue: String(valueMapping[sourceValue] || resolveAutoValueMapping(sourceValue, options) || ''),
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
  const linkedEntityIds = Object.keys(LINKED_ENTITY_FIELD_PREFIXES)
  const hasLinkedEntitySettings = (
    settings
    && typeof settings === 'object'
    && linkedEntityIds.some((entityId) => settings[entityId] && typeof settings[entityId] === 'object')
  )

  if (hasLinkedEntitySettings) {
    let sharedStrategy = ''
    let sharedCondition = ''
    const linkedFields = []

    for (const entityId of linkedEntityIds) {
      const entityPayload = buildDedupPayload(settings?.[entityId] || {})
      if (!sharedStrategy) {
        sharedStrategy = entityPayload.strategy
        sharedCondition = entityPayload.condition
      }

      const prefix = LINKED_ENTITY_FIELD_PREFIXES[entityId] || ''
      for (const fieldId of entityPayload.fields) {
        linkedFields.push(prefix ? `${prefix}${fieldId}` : fieldId)
      }
    }

    return {
      strategy: sharedStrategy || 'create',
      fields: (sharedStrategy || 'create') === 'create' ? [] : Array.from(new Set(linkedFields)),
      condition: sharedCondition || 'any',
    }
  }

  const strategy = SUPPORTED_DEDUP_STRATEGIES.includes(String(settings?.strategy || ''))
    ? String(settings?.strategy || '')
    : 'create'

  const fields = Array.from(new Set(
    (Array.isArray(settings?.fields) ? settings.fields : [])
      .map((field) => String(field || '').trim())
      .filter((field) => field && _DEDUP_FIELD_RE.test(field)),
  ))

  const condition = String(settings?.condition || 'any') === 'all' ? 'all' : 'any'

  return {
    strategy,
    fields: strategy === 'create' ? [] : fields,
    condition,
  }
}

const IMPORTER_FIELD_LABELS = {
  ID: 'Bitrix24 ID',
  TITLE: 'Название / заголовок',
  NAME: 'Имя',
  LAST_NAME: 'Фамилия',
  SECOND_NAME: 'Отчество',
  EMAIL: 'Email',
  PHONE: 'Телефон',
  WEB: 'Сайт',
  IM: 'Мессенджер',
  OPPORTUNITY: 'Сумма',
  CURRENCY_ID: 'Валюта',
  STAGE_ID: 'Стадия',
  STATUS_ID: 'Статус',
  SOURCE_ID: 'Источник',
  TYPE_ID: 'Тип',
  CATEGORY_ID: 'Направление',
  ASSIGNED_BY_ID: 'Ответственный',
  RESPONSIBLE_ID: 'Ответственный',
  CREATED_BY: 'Постановщик',
  DATE_CREATE: 'Дата создания',
  DATE_MODIFY: 'Дата изменения',
  CREATED_TIME: 'Дата создания',
  UPDATED_TIME: 'Дата изменения',
  GROUP_ID: 'Рабочая группа',
  COMPANY_ID: 'Компания',
  CONTACT_ID: 'Контакт',
  COMMENTS: 'Комментарий',
}

const IMPORTER_FIELD_TITLE_LABELS = {
  DATECREATE: 'Дата создания',
  CREATEDTIME: 'Дата создания',
  DATEMODIFY: 'Дата изменения',
  UPDATEDTIME: 'Дата изменения',
}

function containsCyrillic(value) {
  return /[А-Яа-яЁё]/.test(String(value || ''))
}

function normalizeImporterFieldTitleKey(value) {
  return String(value || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '')
}

export function formatImporterFieldLabel(fieldId, fieldTitle = '') {
  const normalizedFieldId = String(fieldId || '').trim().toUpperCase()
  if (!normalizedFieldId) {
    return ''
  }

  for (const [prefix, entityLabel] of Object.entries(LINKED_FIELD_PREFIX_LABELS)) {
    if (normalizedFieldId.startsWith(prefix) && normalizedFieldId.length > prefix.length) {
      return `${entityLabel}: ${formatImporterFieldLabel(normalizedFieldId.slice(prefix.length), fieldTitle)}`
    }
  }

  if (Object.hasOwn(IMPORTER_FIELD_LABELS, normalizedFieldId)) {
    return IMPORTER_FIELD_LABELS[normalizedFieldId]
  }

  const normalizedFieldTitle = String(fieldTitle || '').trim()
  if (normalizedFieldTitle && containsCyrillic(normalizedFieldTitle)) {
    return normalizedFieldTitle
  }

  const normalizedFieldTitleKey = normalizeImporterFieldTitleKey(normalizedFieldTitle)
  if (normalizedFieldTitleKey && Object.hasOwn(IMPORTER_FIELD_TITLE_LABELS, normalizedFieldTitleKey)) {
    return IMPORTER_FIELD_TITLE_LABELS[normalizedFieldTitleKey]
  }

  return normalizedFieldTitle || normalizedFieldId
}

export function buildDedupFieldOptions(mappingRows, fields) {
  const fieldPattern = /^[A-Z][A-Z0-9_]*$/
  const fieldIndex = new Map(
    (Array.isArray(fields) ? fields : [])
      .filter((field) => field && typeof field === 'object')
      .map((field) => [String(field.id || '').trim().toUpperCase(), field]),
  )
  const selectedFields = new Set(
    (Array.isArray(mappingRows) ? mappingRows : [])
      .map((row) => normalizeMappingSelectValue(row?.targetFieldId))
      .map((fieldId) => String(fieldId || '').trim().toUpperCase())
      .filter((fieldId) => fieldId && fieldPattern.test(fieldId)),
  )

  return Array.from(selectedFields).map((fieldId) => {
    const field = fieldIndex.get(fieldId)
    return {
      id: fieldId,
      label: formatImporterFieldLabel(fieldId, field?.title),
      hint: fieldId === 'ID' ? 'Прямой поиск по ID записи Bitrix24' : undefined,
    }
  })
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
      createdAt: buildImportRunCreatedAt(item),
      entityLabel: buildImportRunEntityLabel(item, linkedRecords),
      title: buildImportRunTitle(item, linkedRecords),
      recordId,
      details: [
        errorDetails || linkedDetails,
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

function buildImportRunCreatedAt(item) {
  return String(item?.report_date_time || '').trim() || '—'
}

function getLinkedRecordSectionIds(linkedRecords) {
  if (!linkedRecords || typeof linkedRecords !== 'object') {
    return []
  }

  return Object.keys(linkedRecords)
    .filter((sectionId) => normalizeLinkedRecord(linkedRecords?.[sectionId]))
}

function getLinkedEntityDisplayMeta(sectionId) {
  const normalizedSectionId = String(sectionId || '').trim()
  return LINKED_ENTITY_DISPLAY_META[normalizedSectionId] || {
    singular: normalizedSectionId || 'Связанная запись',
    plural: normalizedSectionId || 'Связанные записи',
    emptyTitle: 'Без названия',
  }
}

function buildLinkedEntitySummaryLabel(linkedRecords) {
  const sectionIds = getLinkedRecordSectionIds(linkedRecords)
  if (!sectionIds.length) {
    return '—'
  }

  return sectionIds.map((sectionId) => getLinkedEntityDisplayMeta(sectionId).singular).join(' + ')
}

function buildImportRunEntityLabel(item, linkedRecords) {
  const reportEntity = String(item?.report_entity || '').trim()
  if (reportEntity) {
    return reportEntity
  }

  return buildLinkedEntitySummaryLabel(linkedRecords)
}

function buildImportRunTitle(item, linkedRecords) {
  const reportTitle = String(item?.report_title || '').trim()
  if (reportTitle) {
    return reportTitle
  }

  const linkedTitles = getLinkedRecordSectionIds(linkedRecords)
    .map((sectionId) => normalizeLinkedRecord(linkedRecords?.[sectionId])?.title)
    .filter(Boolean)
  return linkedTitles.join(' / ') || '—'
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

  return `Совпадение: ${fields.map((field) => formatImporterFieldLabel(field)).join(', ')}`
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
  const reportRecordId = String(item?.report_record_id || '').trim()
  if (reportRecordId) {
    return reportRecordId
  }

  const labels = getLinkedRecordSectionIds(linkedRecords)
    .map((sectionId) => {
      const linkedRecord = normalizeLinkedRecord(linkedRecords?.[sectionId])
      if (!linkedRecord?.id) {
        return ''
      }

      return `${getLinkedEntityDisplayMeta(sectionId).singular} ${linkedRecord.id}`
    })
    .filter(Boolean)

  if (labels.length > 0) {
    return labels.join(' · ')
  }

  return item?.record_id === undefined || item?.record_id === null || item?.record_id === ''
    ? '—'
    : String(item.record_id)
}

function buildLinkedImportRunDetails(linkedRecords) {
  return getLinkedRecordSectionIds(linkedRecords)
    .map((sectionId) => {
      const linkedRecord = normalizeLinkedRecord(linkedRecords?.[sectionId])
      if (!linkedRecord) {
        return ''
      }

      const displayMeta = getLinkedEntityDisplayMeta(sectionId)
      return [
        `${displayMeta.singular}:`,
        linkedRecord.title || displayMeta.emptyTitle,
      ].filter(Boolean).join(' ') + (linkedRecord.id ? ` · ID ${linkedRecord.id}` : '')
    })
    .filter(Boolean)
    .join(' · ')
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

function buildDerivedImportRunSummary(results) {
  const safeResults = Array.isArray(results) ? results : []
  const createdIds = []
  const updatedIds = []
  let checkedRows = 0
  let createdRows = 0
  let updatedRows = 0
  let failedRows = 0
  let skippedRows = 0
  let cancelledRows = 0

  safeResults.forEach((item) => {
    const status = String(item?.status || '').trim()
    const recordId = item?.record_id

    if (status !== 'cancelled') {
      checkedRows += 1
    }

    if (status === 'created') {
      createdRows += 1
      if (recordId !== undefined && recordId !== null && recordId !== '') {
        createdIds.push(recordId)
      }
    } else if (status === 'updated') {
      updatedRows += 1
      if (recordId !== undefined && recordId !== null && recordId !== '') {
        updatedIds.push(recordId)
      }
    } else if (status === 'cancelled') {
      cancelledRows += 1
    }

    if (['failed', 'skipped'].includes(status)) {
      failedRows += 1
    }

    if (['skipped', 'skipped_duplicate'].includes(status)) {
      skippedRows += 1
    }
  })

  return {
    checked_rows: checkedRows,
    created_rows: createdRows,
    updated_rows: updatedRows,
    failed_rows: failedRows,
    skipped_rows: skippedRows,
    cancelled: cancelledRows > 0,
    cancelled_rows: cancelledRows,
    remaining_rows: cancelledRows,
    created_ids: createdIds,
    updated_ids: updatedIds,
  }
}

function hasOwnImportRunField(importRun, fieldName) {
  return Boolean(importRun) && Object.prototype.hasOwnProperty.call(importRun, fieldName)
}

export function shouldWaitForImportExecutionSnapshot(snapshot) {
  const status = String(snapshot?.status || '').trim().toLowerCase()

  return ['draft', 'uploaded', 'validated', 'ready', 'running'].includes(status)
}

export function shouldWaitForDryRunExecutionSnapshot(snapshot) {
  const summary = snapshot?.summary && typeof snapshot.summary === 'object' ? snapshot.summary : {}
  const job = summary?.job && typeof summary.job === 'object' ? summary.job : {}
  const jobMode = String(job?.mode || '').trim().toLowerCase()
  const jobState = String(job?.state || '').trim().toLowerCase()

  return jobMode === 'dry_run' && ['queued', 'running'].includes(jobState)
}

export function buildDryRunSummaryFromSessionSnapshot(snapshot) {
  const summary = snapshot?.summary && typeof snapshot.summary === 'object' ? snapshot.summary : {}
  const rawDryRun = summary?.dry_run
  const dryRun = rawDryRun && typeof rawDryRun === 'object' ? rawDryRun : null

  if (!dryRun) {
    return null
  }

  return {
    session_id: String(snapshot?.session_id || snapshot?.id || ''),
    status: String(snapshot?.status || ''),
    ...dryRun,
  }
}

export function buildImportRunSummaryFromSessionSnapshot(snapshot) {
  const summary = snapshot?.summary && typeof snapshot.summary === 'object' ? snapshot.summary : {}
  const rawImportRun = summary?.import_run
  const importRun = rawImportRun && typeof rawImportRun === 'object' ? rawImportRun : {}
  const results = Array.isArray(importRun.results) ? importRun.results : []
  const derivedSummary = buildDerivedImportRunSummary(results)
  const retryRuns = Array.isArray(summary?.retry_runs) ? summary.retry_runs : []
  const latestRetryRun = retryRuns.length > 0 && retryRuns[retryRuns.length - 1] && typeof retryRuns[retryRuns.length - 1] === 'object'
    ? retryRuns[retryRuns.length - 1]
    : null
  const processedRows = Number(snapshot?.processed_rows || 0)
  const successfulRows = Number(snapshot?.successful_rows || 0)
  const failedRows = Number(snapshot?.failed_rows || 0)
  const hasSessionLevelCounters = processedRows > 0 || successfulRows > 0 || failedRows > 0

  if (!rawImportRun && !hasSessionLevelCounters) {
    return null
  }

  const updatedRows = hasOwnImportRunField(importRun, 'updated_rows')
    ? Number(importRun.updated_rows || 0)
    : results.length > 0
      ? derivedSummary.updated_rows
      : 0
  const createdRowsFallback = Math.max(0, successfulRows - updatedRows)

  return {
    ...importRun,
    session_id: String(snapshot?.session_id || snapshot?.id || ''),
    status: String(snapshot?.status || ''),
    retried_rows: Array.isArray(latestRetryRun?.results) ? latestRetryRun.results.length : 0,
    retry_result: latestRetryRun,
    checked_rows: hasOwnImportRunField(importRun, 'checked_rows')
      ? Number(importRun.checked_rows || 0)
      : results.length > 0
        ? derivedSummary.checked_rows
        : processedRows,
    created_rows: hasOwnImportRunField(importRun, 'created_rows')
      ? Number(importRun.created_rows || 0)
      : results.length > 0
        ? derivedSummary.created_rows
        : createdRowsFallback,
    updated_rows: updatedRows,
    failed_rows: hasOwnImportRunField(importRun, 'failed_rows')
      ? Number(importRun.failed_rows || 0)
      : results.length > 0
        ? derivedSummary.failed_rows
        : failedRows,
    skipped_rows: hasOwnImportRunField(importRun, 'skipped_rows')
      ? Number(importRun.skipped_rows || 0)
      : results.length > 0
        ? derivedSummary.skipped_rows
        : 0,
    cancelled: hasOwnImportRunField(importRun, 'cancelled')
      ? Boolean(importRun.cancelled)
      : derivedSummary.cancelled,
    cancelled_rows: hasOwnImportRunField(importRun, 'cancelled_rows')
      ? Number(importRun.cancelled_rows || 0)
      : derivedSummary.cancelled_rows,
    remaining_rows: hasOwnImportRunField(importRun, 'remaining_rows')
      ? Number(importRun.remaining_rows || 0)
      : derivedSummary.remaining_rows,
    created_ids: Array.isArray(importRun.created_ids) ? importRun.created_ids : derivedSummary.created_ids,
    updated_ids: Array.isArray(importRun.updated_ids) ? importRun.updated_ids : derivedSummary.updated_ids,
    results,
  }
}

export function buildLinkedImportRunSummary(importRunData, { pageSize = 5, maxPages = 3 } = {}) {
  const cappedPageSize = Math.max(1, Number(pageSize || 0))
  const cappedMaxPages = Math.max(1, Number(maxPages || 0))
  const maxItemsPerSection = cappedPageSize * cappedMaxPages
  const results = Array.isArray(importRunData?.results) ? importRunData.results : []

  const sectionIds = Array.from(new Set(results.flatMap((item) => getLinkedRecordSectionIds(item?.linked_records))))
  const sectionDefinitions = sectionIds.map((sectionId) => ({
    id: sectionId,
    title: getLinkedEntityDisplayMeta(sectionId).plural,
  }))

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
  return formatImporterFieldLabel(fieldId)
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

  return `Неполный поиск дублей: ${fields.map((field) => formatImporterFieldLabel(field)).join(', ')}`
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

  const buildActionLabel = (status) => {
    const normalizedStatus = String(status || '').trim()

    if (['draft', 'uploaded', 'validated', 'ready', 'running'].includes(normalizedStatus)) {
      return 'Продолжить'
    }

    return 'Открыть'
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
      entityType: getImportEntityLabel(session?.entity_type, session?.entity_config),
      statusLabel: statusLabels[status] || status || '—',
      resultLabel: resultMeta.resultLabel,
      resultTone: resultMeta.resultTone,
      actionLabel: buildActionLabel(status),
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
