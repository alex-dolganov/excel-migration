import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  EMPTY_MAPPING_SELECT_VALUE,
  SUPPORTED_IMPORT_ENTITIES,
  buildExampleTemplateDownloadMeta,
  buildImportScenarioSections,
  buildImportModeOptions,
  getImportModeMeta,
  buildFileAttachEntityOptions,
  buildScenarioSelectionSummary,
  buildRoleAssignmentPayload,
  buildRoleAssignmentsRows,
  buildImporterPermissionState,
  buildMigrationStatusBadge,
  buildCollapsibleHistoryState,
  buildDryRunRows,
  buildMappingFieldItems,
  buildFieldGuidanceHints,
  buildEntityScenarioGuide,
  buildTaskScenarioQuickStart,
  buildRequiredFieldSummary,
  buildSessionHistoryRows,
  canAdvanceWizard,
  getWizardAdvanceMode,
  getWizardNextLabel,
  buildMappingRows,
  buildMappingPayload,
  buildValueMappingRows,
  buildDedupPayload,
  buildDedupWeakeningNotice,
  buildImportRunProblemGroups,
  buildImportRunRows,
  setImporterUiTranslator,
  buildImportRunCompletionNotice,
  buildImportRunSummaryFromSessionSnapshot,
  buildImportRunStatusFilters,
  buildImportRunRetryState,
  buildDryRunSummaryFromSessionSnapshot,
  buildResolvedDryRunSummary,
  buildLinkedImportRunSummary,
  shouldWaitForDryRunExecutionSnapshot,
  shouldWaitForImportExecutionSnapshot,
  filterImportRunRows,
  resolveImportRunFilterId,
  buildUnmappedValueSummary,
  buildValueMappingStatus,
  buildValidationIssueRows,
  detectSourceFormat,
  normalizeMappingSelectValue,
  resolveMappingSelectValue,
} from '../app/utils/importer-ui.js'

test('detects source format from uploaded filename', () => {
  assert.equal(detectSourceFormat('contacts.xlsx'), 'xlsx')
  assert.equal(detectSourceFormat('contacts.csv'), 'csv')
  assert.equal(detectSourceFormat('contacts.unknown'), '')
})

test('builds error completion notice when import stops on fatal Bitrix limit', () => {
  assert.deepEqual(
    buildImportRunCompletionNotice({
      status: 'cancelled',
      fatal_error: 'Превышен дневной лимит приглашений по e-mail.',
      failed_rows: 1,
      remaining_rows: 24,
    }),
    {
      type: 'error',
      message: 'Превышен дневной лимит приглашений по e-mail.',
    },
  )
})

test('includes task attachments in supported import entities', () => {
  assert.equal(
    SUPPORTED_IMPORT_ENTITIES.some((entity) => entity.value === 'task_attachment' && entity.label === 'Вложения задач'),
    true,
  )
})

test('builds linked-aware scenario-first sections for crm and task imports', () => {
  assert.deepEqual(buildImportScenarioSections(), [
    {
      id: 'crm',
      title: 'CRM-сущности',
      description: 'Прямой импорт в стандартные CRM-разделы.',
      items: [
        { value: 'lead', label: 'Лиды', family: 'crm' },
        { value: 'contact', label: 'Контакты', family: 'crm' },
        { value: 'company', label: 'Компании', family: 'crm' },
        { value: 'deal', label: 'Сделки', family: 'crm' },
        { value: 'smart_process', label: 'Смарт-процессы', family: 'crm' },
        { value: 'crm_activity', label: 'Встречи/Звонки CRM', family: 'crm' },
        { value: 'crm_note', label: 'Комментарии CRM', family: 'crm' },
      ],
    },
    {
      id: 'task',
      title: 'Импорт в задачи',
      description: 'Выберите, что импортировать в задачи.',
      items: [
        { value: 'task', label: 'Задачи', family: 'task' },
        { value: 'task_comment', label: 'Комментарии задач', family: 'task' },
        { value: 'task_checklist_item', label: 'Чек-листы задач', family: 'task' },
        { value: 'task_attachment', label: 'Вложения задач', family: 'task' },
      ],
    },
    {
      id: 'linked',
      title: 'Связанный импорт',
      description: 'Одна строка Excel создаёт и связывает несколько сущностей.',
      items: [
        { value: 'linked_company_contact', label: 'Компания + Контакт', family: 'linked' },
        { value: 'linked_company_deal', label: 'Компания + Сделка', family: 'linked' },
        { value: 'linked_contact_company', label: 'Контакт + Компания', family: 'linked' },
        { value: 'linked_contact_deal', label: 'Контакт + Сделка', family: 'linked' },
        { value: 'linked_deal_company', label: 'Сделка + Компания', family: 'linked' },
        { value: 'linked_deal_contact', label: 'Сделка + Контакт', family: 'linked' },
      ],
    },
    {
      id: 'hr',
      title: 'Пользователи и отделы',
      description: 'Импорт пользователей и организационной структуры.',
      items: [
        { value: 'user', label: 'Пользователи', family: 'hr' },
        { value: 'department', label: 'Отделы', family: 'hr' },
      ],
    },
  ])
})

test('builds scenario selection summary for linked company contact import', () => {
  assert.deepEqual(buildScenarioSelectionSummary('linked_company_contact'), {
    family: 'linked',
    familyLabel: 'Связанный импорт',
    selectedLabel: 'Компания + Контакт',
    title: 'Связанный импорт компании и контакта',
    description: 'Каждая строка создаёт или обновляет компанию и контакт с автоматической привязкой.',
    minimumFields: ['COMPANY__TITLE', 'CONTACT__NAME или CONTACT__LAST_NAME'],
    destinationLabel: 'Сначала обрабатывает компанию, затем контакт и связывает их автоматически.',
  })
})

test('builds scenario selection summary for linked company deal import', () => {
  assert.deepEqual(buildScenarioSelectionSummary('linked_company_deal'), {
    family: 'linked',
    familyLabel: 'Связанный импорт',
    selectedLabel: 'Компания + Сделка',
    title: 'Связанный импорт компании и сделки',
    description: 'Каждая строка создаёт или обновляет компанию и связанную с ней сделку.',
    minimumFields: ['COMPANY__TITLE', 'DEAL__TITLE'],
    destinationLabel: 'Сначала обрабатывает компанию, затем создаёт или обновляет сделку и связывает её с компанией.',
  })
})

test('builds scenario selection summary for linked contact deal import', () => {
  assert.deepEqual(buildScenarioSelectionSummary('linked_contact_deal'), {
    family: 'linked',
    familyLabel: 'Связанный импорт',
    selectedLabel: 'Контакт + Сделка',
    title: 'Связанный импорт контакта и сделки',
    description: 'Каждая строка создаёт или обновляет контакт и связанную с ним сделку.',
    minimumFields: ['CONTACT__NAME или CONTACT__LAST_NAME', 'DEAL__TITLE'],
    destinationLabel: 'Сначала обрабатывает контакт, затем создаёт или обновляет сделку и связывает её с контактом.',
  })
})

test('builds scenario selection summary for crm activity import', () => {
  assert.deepEqual(buildScenarioSelectionSummary('crm_activity'), {
    family: 'crm',
    familyLabel: 'CRM-сущности',
    selectedLabel: 'Встречи/Звонки CRM',
    title: 'Импорт встреч/звонков CRM',
    description: 'Каждая строка создаёт отдельную активность CRM для существующей записи.',
    minimumFields: ['OWNER_TYPE_ID', 'OWNER_ID', 'TYPE_ID', 'SUBJECT'],
    destinationLabel: 'Импортирует активность в таймлайн выбранной CRM-записи.',
  })
})

test('builds scenario selection summary for crm note import', () => {
  assert.deepEqual(buildScenarioSelectionSummary('crm_note'), {
    family: 'crm',
    familyLabel: 'CRM-сущности',
    selectedLabel: 'Комментарии CRM',
    title: 'Импорт комментариев CRM',
    description: 'Каждая строка добавляет комментарий в таймлайн существующей CRM-записи.',
    minimumFields: ['ENTITY_TYPE', 'ENTITY_ID', 'COMMENT'],
    destinationLabel: 'Импортирует комментарий напрямую в таймлайн выбранной CRM-сущности.',
  })
})

test('builds scenario guide for linked company deal import', () => {
  assert.deepEqual(buildEntityScenarioGuide('linked_company_deal'), {
    title: 'Связанный импорт компании и сделки',
    description: 'Одна строка Excel создаёт или обновляет компанию и связанную с ней сделку.',
    highlights: [
      'Компания и сделка загружаются из одной строки и связываются автоматически.',
      'Для компании используйте колонки с префиксом COMPANY__, для сделки с префиксом DEAL__.',
      'Если для сделки нужны суммы и этапы, используйте DEAL__OPPORTUNITY, DEAL__CURRENCY_ID и DEAL__STAGE_ID.',
    ],
    exampleColumns: ['COMPANY__TITLE', 'COMPANY__PHONE', 'DEAL__TITLE', 'DEAL__OPPORTUNITY', 'DEAL__CURRENCY_ID', 'DEAL__STAGE_ID'],
  })
})

test('builds scenario guide for linked contact deal import', () => {
  assert.deepEqual(buildEntityScenarioGuide('linked_contact_deal'), {
    title: 'Связанный импорт контакта и сделки',
    description: 'Одна строка Excel создаёт или обновляет контакт и связанную с ним сделку.',
    highlights: [
      'Контакт и сделка загружаются из одной строки и связываются автоматически.',
      'Для контакта используйте колонки с префиксом CONTACT__, для сделки с префиксом DEAL__.',
      'Если для сделки нужны суммы и этапы, используйте DEAL__OPPORTUNITY, DEAL__CURRENCY_ID и DEAL__STAGE_ID.',
    ],
    exampleColumns: ['CONTACT__NAME', 'CONTACT__LAST_NAME', 'CONTACT__PHONE', 'DEAL__TITLE', 'DEAL__OPPORTUNITY', 'DEAL__STAGE_ID'],
  })
})

test('builds scenario guide for linked deal company import without external key example', () => {
  assert.deepEqual(buildEntityScenarioGuide('linked_deal_company'), {
    title: 'Связанный импорт сделки и компании',
    description: 'Одна строка Excel создаёт или обновляет сделку и связанную с ней компанию.',
    highlights: [
      'Сделка и компания загружаются из одной строки и связываются автоматически.',
      'Для сделки используйте колонки с префиксом DEAL__, для компании с префиксом COMPANY__.',
      'У одной сделки может быть только одна компания, поэтому в шаблоне достаточно данных самой сделки и компании.',
    ],
    exampleColumns: ['DEAL__TITLE', 'DEAL__OPPORTUNITY', 'DEAL__CURRENCY_ID', 'DEAL__STAGE_ID', 'COMPANY__TITLE', 'COMPANY__PHONE', 'COMPANY__EMAIL'],
  })
})

test('builds scenario guide for crm activity import', () => {
  assert.deepEqual(buildEntityScenarioGuide('crm_activity'), {
    title: 'Импорт встреч/звонков CRM',
    description: 'Каждая строка создаёт отдельную активность CRM для существующей записи.',
    highlights: [
      'Минимум для импорта: OWNER_TYPE_ID, OWNER_ID, TYPE_ID и SUBJECT.',
      'Для звонков и email обязательно заполните COMMUNICATIONS_VALUE телефоном или email.',
      'OWNER_TYPE_ID принимает тип сущности CRM: 1 — лид, 2 — сделка, 3 — контакт, 4 — компания.',
    ],
    exampleColumns: ['OWNER_TYPE_ID', 'OWNER_ID', 'TYPE_ID', 'SUBJECT', 'COMMUNICATIONS_VALUE'],
  })
})

test('builds scenario guide for crm note import', () => {
  assert.deepEqual(buildEntityScenarioGuide('crm_note'), {
    title: 'Импорт комментариев CRM',
    description: 'Каждая строка добавляет комментарий в таймлайн существующей CRM-записи.',
    highlights: [
      'Минимум для импорта: ENTITY_TYPE, ENTITY_ID и COMMENT.',
      'ENTITY_TYPE можно передавать как код сущности: lead, contact, company или deal.',
      'Комментарий попадёт в таймлайн записи как обычная заметка CRM.',
    ],
    exampleColumns: ['ENTITY_TYPE', 'ENTITY_ID', 'COMMENT', 'CREATED_TIME'],
  })
})

test('builds scenario selection summary for task checklist import', () => {
  assert.deepEqual(buildScenarioSelectionSummary('task_checklist_item'), {
    family: 'task',
    familyLabel: 'Импорт в задачи',
    selectedLabel: 'Чек-листы задач',
    title: 'Чек-листы в задачи',
    description: 'Каждая строка создаёт один пункт чек-листа в выбранной задаче.',
    minimumFields: ['TASK_ID', 'TITLE'],
    destinationLabel: 'Добавляет пункт чек-листа в существующую задачу по TASK_ID.',
  })
})

test('builds scenario guide for task comment chat import', () => {
  assert.deepEqual(buildEntityScenarioGuide('task_comment'), {
    title: 'Импорт сообщений в чат задачи',
    description: 'Каждая строка отправляет одно сообщение в чат выбранной задачи.',
    highlights: [
      'Минимум для импорта: TASK_ID, POST_MESSAGE и AUTHOR_ID или выбранный пользователь по умолчанию.',
      'TASK_ID можно передавать как Bitrix ID задачи или XML_ID.',
      'Если AUTHOR_ID указан в файле, он имеет приоритет над пользователем по умолчанию.',
    ],
    exampleColumns: ['TASK_ID', 'AUTHOR_ID', 'POST_MESSAGE'],
  })
})

test('builds scenario selection summary for task import with responsible field in minimum set', () => {
  assert.deepEqual(buildScenarioSelectionSummary('task'), {
    family: 'task',
    familyLabel: 'Импорт в задачи',
    selectedLabel: 'Задачи',
    title: 'Задачи и подзадачи',
    description: 'Каждая строка создаёт задачу или подзадачу.',
    minimumFields: ['TITLE', 'RESPONSIBLE_ID или исполнитель по умолчанию'],
    destinationLabel: 'Создаёт отдельную задачу. Для подзадач используйте PARENT_ID.',
  })
})

test('builds scenario selection summary for task attachment bulk mode', () => {
  assert.deepEqual(buildScenarioSelectionSummary('task_attachment'), {
    family: 'task',
    familyLabel: 'Импорт в задачи',
    selectedLabel: 'Вложения задач',
    title: 'Массовые вложения в задачи',
    description: 'Один файл прикрепляется ко всем найденным задачам по выбранному фильтру.',
    minimumFields: ['Фильтр задач', 'Файл-вложение'],
    destinationLabel: 'Находит задачи по фильтру и прикрепляет к каждой выбранный файл.',
  })
})

test('builds example template download meta for deal and task attachment', () => {
  assert.deepEqual(buildExampleTemplateDownloadMeta('deal'), {
    title: 'Шаблон для «Сделки»',
    description: 'Скачайте пример Excel с заголовками и одной тестовой строкой под выбранный импорт.',
    filename: 'deal-import-example.xlsx',
  })

  assert.deepEqual(buildExampleTemplateDownloadMeta('task_attachment'), {
    title: 'Файл для «Вложения задач»',
    description: 'В этом режиме Excel-шаблон не нужен: настройте фильтр задач и загрузите один файл-вложение.',
    filename: 'task_attachment-import-example.xlsx',
  })

  assert.deepEqual(buildExampleTemplateDownloadMeta('linked_company_contact'), {
    title: 'Шаблон для «Компания + Контакт»',
    description: 'Скачайте пример Excel с заголовками и одной тестовой строкой под выбранный импорт.',
    filename: 'linked_company_contact-import-example.xlsx',
  })

  assert.deepEqual(buildExampleTemplateDownloadMeta('linked_company_deal'), {
    title: 'Шаблон для «Компания + Сделка»',
    description: 'Скачайте пример Excel с заголовками и одной тестовой строкой под выбранный импорт.',
    filename: 'linked_company_deal-import-example.xlsx',
  })

  assert.deepEqual(buildExampleTemplateDownloadMeta('linked_contact_deal'), {
    title: 'Шаблон для «Контакт + Сделка»',
    description: 'Скачайте пример Excel с заголовками и одной тестовой строкой под выбранный импорт.',
    filename: 'linked_contact_deal-import-example.xlsx',
  })
})

test('builds mapping rows with saved mapping taking priority over candidates', () => {
  const rows = buildMappingRows({
    headers: ['Lead title', 'Phone'],
    columns: ['A', 'B'],
    fields: [
      { id: 'TITLE', title: 'Lead title' },
      { id: 'PHONE', title: 'Phone' },
    ],
    candidateMapping: {
      TITLE: {
        source_header: 'Lead title',
        column: 'A',
        target_field: 'TITLE',
      },
      PHONE: {
        source_header: 'Phone',
        column: 'B',
        target_field: 'PHONE',
      },
    },
    savedMapping: {
      PHONE: {
        source_header: 'Phone',
        column: 'B',
        target_field: 'PHONE',
      },
    },
  })

  assert.deepEqual(rows, [
    {
      key: 'A:Lead title',
      column: 'A',
      sourceHeader: 'Lead title',
      targetFieldId: '',
      targetFieldTitle: '',
      targetFieldType: '',
      targetFieldTypeLabel: '',
      targetFieldRequired: false,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
    {
      key: 'B:Phone',
      column: 'B',
      sourceHeader: 'Phone',
      targetFieldId: 'PHONE',
      targetFieldTitle: 'Phone',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: false,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
  ])
})

test('builds mapping rows from candidate mapping when simple mode disables saved rules', () => {
  const rows = buildMappingRows({
    headers: ['Название'],
    columns: ['A'],
    fields: [
      { id: 'TITLE', title: 'Название сделки', required: true },
      { id: 'STAGE_ID', title: 'Стадия', required: false },
    ],
    candidateMapping: {
      TITLE: {
        source_header: 'Название',
        column: 'A',
        target_field: 'TITLE',
        match_type: 'exact',
      },
    },
    savedMapping: {
      STAGE_ID: {
        source_header: 'Название',
        column: 'A',
        target_field: 'STAGE_ID',
      },
    },
    preferSavedMapping: false,
  })

  assert.deepEqual(rows, [
    {
      key: 'A:Название',
      column: 'A',
      sourceHeader: 'Название',
      targetFieldId: 'TITLE',
      targetFieldTitle: 'Название сделки',
      autoMatchType: 'exact',
      autoMatchLabel: 'Точное',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: true,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
  ])
})

test('builds mapping rows with field type metadata for custom and multiple fields', () => {
  const rows = buildMappingRows({
    headers: ['Tags'],
    columns: ['A'],
    fields: [
      {
        id: 'UF_CRM_TAGS',
        title: 'Tags',
        type: 'enumeration',
        required: true,
        is_custom: true,
        multiple: true,
      },
    ],
    candidateMapping: {
      UF_CRM_TAGS: {
        source_header: 'Tags',
        column: 'A',
        target_field: 'UF_CRM_TAGS',
      },
    },
    savedMapping: {},
  })

  assert.deepEqual(rows, [
    {
      key: 'A:Tags',
      column: 'A',
      sourceHeader: 'Tags',
      targetFieldId: 'UF_CRM_TAGS',
      targetFieldTitle: 'Tags',
      targetFieldType: 'enumeration',
      targetFieldTypeLabel: 'Список',
      targetFieldRequired: true,
      targetFieldIsCustom: true,
      targetFieldIsMultiple: true,
      targetFieldGuidanceHints: [
        'Выберите соответствие значений в блоке маппинга списков ниже.',
        'Несколько значений можно передавать через ";" или с новой строки.',
      ],
    },
  ])
})

test('builds mapping rows with required metadata for mapped fields', () => {
  const rows = buildMappingRows({
    headers: ['Lead title', 'Phone'],
    columns: ['A', 'B'],
    fields: [
      { id: 'TITLE', title: 'Lead title', required: true },
      { id: 'PHONE', title: 'Phone', required: false },
    ],
    candidateMapping: {
      TITLE: {
        source_header: 'Lead title',
        column: 'A',
        target_field: 'TITLE',
      },
      PHONE: {
        source_header: 'Phone',
        column: 'B',
        target_field: 'PHONE',
      },
    },
    savedMapping: {},
  })

  assert.deepEqual(rows, [
    {
      key: 'A:Lead title',
      column: 'A',
      sourceHeader: 'Lead title',
      targetFieldId: 'TITLE',
      targetFieldTitle: 'Lead title',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: true,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
    {
      key: 'B:Phone',
      column: 'B',
      sourceHeader: 'Phone',
      targetFieldId: 'PHONE',
      targetFieldTitle: 'Phone',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: false,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
  ])
})

test('keeps exact and fuzzy auto-match metadata only for candidate mapping', () => {
  const rows = buildMappingRows({
    headers: ['Lead Name', 'Phone'],
    columns: ['A', 'B'],
    fields: [
      { id: 'TITLE', title: 'Lead title', required: true },
      { id: 'PHONE', title: 'Phone', required: false },
    ],
    candidateMapping: {
      TITLE: {
        source_header: 'Lead Name',
        column: 'A',
        target_field: 'TITLE',
        match_type: 'fuzzy',
      },
      PHONE: {
        source_header: 'Phone',
        column: 'B',
        target_field: 'PHONE',
        match_type: 'exact',
      },
    },
    savedMapping: {},
  })

  assert.deepEqual(rows, [
    {
      key: 'A:Lead Name',
      column: 'A',
      sourceHeader: 'Lead Name',
      targetFieldId: 'TITLE',
      targetFieldTitle: 'Lead title',
      autoMatchType: 'fuzzy',
      autoMatchLabel: 'Похожее',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: true,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
    {
      key: 'B:Phone',
      column: 'B',
      sourceHeader: 'Phone',
      targetFieldId: 'PHONE',
      targetFieldTitle: 'Phone',
      autoMatchType: 'exact',
      autoMatchLabel: 'Точное',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: false,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
  ])

  const savedRows = buildMappingRows({
    headers: ['Lead Name'],
    columns: ['A'],
    fields: [
      { id: 'TITLE', title: 'Lead title', required: true },
    ],
    candidateMapping: {
      TITLE: {
        source_header: 'Lead Name',
        column: 'A',
        target_field: 'TITLE',
        match_type: 'fuzzy',
      },
    },
    savedMapping: {
      TITLE: {
        source_header: 'Lead Name',
        column: 'A',
        target_field: 'TITLE',
      },
    },
  })

  assert.deepEqual(savedRows, [
    {
      key: 'A:Lead Name',
      column: 'A',
      sourceHeader: 'Lead Name',
      targetFieldId: 'TITLE',
      targetFieldTitle: 'Lead title',
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: true,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
  ])
})

test('builds mapping rows with match reasons and alternative candidate suggestions', () => {
  const rows = buildMappingRows({
    headers: ['Nazvanie'],
    columns: ['A'],
    fields: [
      { id: 'TITLE', title: 'Lead title', required: true },
      { id: 'COMMENTS', title: 'Comments', required: false },
    ],
    candidateMapping: {
      TITLE: {
        source_header: 'Nazvanie',
        column: 'A',
        target_field: 'TITLE',
        match_type: 'fuzzy',
        match_reason: 'translit_alias',
      },
    },
    candidateSuggestions: {
      'A:Nazvanie': [
        {
          target_field: 'TITLE',
          target_field_title: 'Lead title',
          match_type: 'fuzzy',
          match_reason: 'translit_alias',
        },
        {
          target_field: 'COMMENTS',
          target_field_title: 'Comments',
          match_type: 'fuzzy',
        },
      ],
    },
    savedMapping: {},
  })

  assert.deepEqual(rows, [
    {
      key: 'A:Nazvanie',
      column: 'A',
      sourceHeader: 'Nazvanie',
      targetFieldId: 'TITLE',
      targetFieldTitle: 'Lead title',
      autoMatchType: 'fuzzy',
      autoMatchLabel: 'Похожее',
      autoMatchReason: 'translit_alias',
      autoMatchReasonLabel: 'Транслит / синоним',
      candidateSuggestions: [
        {
          targetFieldId: 'TITLE',
          targetFieldTitle: 'Lead title',
          matchType: 'fuzzy',
          matchLabel: 'Похожее',
          matchReason: 'translit_alias',
          matchReasonLabel: 'Транслит / синоним',
        },
        {
          targetFieldId: 'COMMENTS',
          targetFieldTitle: 'Comments',
          matchType: 'fuzzy',
          matchLabel: 'Похожее',
          matchReason: '',
          matchReasonLabel: '',
        },
      ],
      targetFieldType: 'string',
      targetFieldTypeLabel: 'Текст',
      targetFieldRequired: true,
      targetFieldIsCustom: false,
      targetFieldIsMultiple: false,
      targetFieldGuidanceHints: [],
    },
  ])
})

test('builds summary for required fields based on current mapping', () => {
  const summary = buildRequiredFieldSummary({
    fields: [
      { id: 'TITLE', title: 'Lead title', required: true },
      { id: 'PHONE', title: 'Phone', required: true },
      { id: 'COMMENTS', title: 'Comments', required: false },
    ],
    mappingRows: [
      { targetFieldId: 'TITLE' },
      { targetFieldId: 'COMMENTS' },
    ],
  })

  assert.deepEqual(summary, {
    totalRequired: 2,
    mappedRequired: 1,
    missingRequiredCount: 1,
    hasRequiredFields: true,
    hasMissingRequired: true,
    requiredFields: [
      { id: 'TITLE', title: 'Lead title' },
      { id: 'PHONE', title: 'Phone' },
    ],
    missingRequired: [
      { id: 'PHONE', title: 'Phone' },
    ],
  })
})

test('builds summary for required fields with default task responsible satisfying missing mapping', () => {
  const summary = buildRequiredFieldSummary({
    fields: [
      { id: 'TITLE', title: 'Task title', required: true },
      { id: 'RESPONSIBLE_ID', title: 'Responsible user ID', required: true },
    ],
    mappingRows: [
      { targetFieldId: 'TITLE' },
    ],
    defaultFieldIds: ['RESPONSIBLE_ID'],
  })

  assert.deepEqual(summary, {
    totalRequired: 2,
    mappedRequired: 2,
    missingRequiredCount: 0,
    hasRequiredFields: true,
    hasMissingRequired: false,
    requiredFields: [
      { id: 'TITLE', title: 'Task title' },
      { id: 'RESPONSIBLE_ID', title: 'Responsible user ID' },
    ],
    missingRequired: [],
  })
})

test('builds summary for required fields with default task creator satisfying missing mapping', () => {
  const summary = buildRequiredFieldSummary({
    fields: [
      { id: 'TITLE', title: 'Task title', required: true },
      { id: 'CREATED_BY', title: 'Creator user ID', required: true },
    ],
    mappingRows: [
      { targetFieldId: 'TITLE' },
    ],
    defaultFieldIds: ['CREATED_BY'],
  })

  assert.deepEqual(summary, {
    totalRequired: 2,
    mappedRequired: 2,
    missingRequiredCount: 0,
    hasRequiredFields: true,
    hasMissingRequired: false,
    requiredFields: [
      { id: 'TITLE', title: 'Task title' },
      { id: 'CREATED_BY', title: 'Creator user ID' },
    ],
    missingRequired: [],
  })
})

test('builds summary for required fields with ignored contact fields', () => {
  const summary = buildRequiredFieldSummary({
    fields: [
      { id: 'NAME', title: 'Имя', required: true },
      { id: 'SECOND_NAME', title: 'Отчество', required: true },
      { id: 'LAST_NAME', title: 'Фамилия', required: true },
    ],
    mappingRows: [
      { targetFieldId: 'NAME' },
      { targetFieldId: 'LAST_NAME' },
    ],
    ignoreFieldIds: ['SECOND_NAME'],
  })

  assert.deepEqual(summary, {
    totalRequired: 2,
    mappedRequired: 2,
    missingRequiredCount: 0,
    hasRequiredFields: true,
    hasMissingRequired: false,
    requiredFields: [
      { id: 'NAME', title: 'Имя' },
      { id: 'LAST_NAME', title: 'Фамилия' },
    ],
    missingRequired: [],
  })
})

test('builds mapping select items with type and custom field hints', () => {
  const items = buildMappingFieldItems([
    {
      id: 'TITLE',
      title: 'Lead title',
      type: 'string',
      is_custom: false,
      multiple: false,
    },
    {
      id: 'UF_CRM_TAGS',
      title: 'Tags',
      type: 'enumeration',
      is_custom: true,
      multiple: true,
    },
  ])

  assert.deepEqual(items, [
    { value: EMPTY_MAPPING_SELECT_VALUE, label: 'Не импортировать' },
    { value: 'TITLE', label: 'Lead title (Текст)', description: 'TITLE' },
    { value: 'UF_CRM_TAGS', label: 'Tags (Список)', description: 'UF_CRM_TAGS' },
  ])
})

test('marks required mapping select items with star prefix and tag', () => {
  const items = buildMappingFieldItems([
    {
      id: 'POST_MESSAGE',
      title: 'Comment text',
      type: 'text',
      required: true,
      is_custom: false,
      multiple: false,
    },
    {
      id: 'TASK_ID',
      title: 'Task ID',
      type: 'integer',
      required: true,
      is_custom: false,
      multiple: false,
    },
  ])

  assert.deepEqual(items, [
    { value: EMPTY_MAPPING_SELECT_VALUE, label: 'Не импортировать' },
    { value: 'POST_MESSAGE', label: '★ Comment text (Текст)', description: 'POST_MESSAGE' },
    { value: 'TASK_ID', label: '★ Task ID (Число)', description: 'TASK_ID' },
  ])
})

test('builds field guidance hints for multiple, list, date and boolean fields', () => {
  assert.deepEqual(buildFieldGuidanceHints({
    type: 'enumeration',
    multiple: true,
  }), [
    'Выберите соответствие значений в блоке маппинга списков ниже.',
    'Несколько значений можно передавать через ";" или с новой строки.',
  ])

  assert.deepEqual(buildFieldGuidanceHints({
    type: 'date',
    multiple: false,
  }), [
    'Поддерживаются форматы: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, MM/DD/YYYY.',
  ])

  assert.deepEqual(buildFieldGuidanceHints({
    type: 'boolean',
    multiple: false,
  }), [
    'Допустимые значения: 1, 0, true, false, yes, no, да, нет.',
  ])

  assert.deepEqual(buildFieldGuidanceHints({
    type: 'file',
    multiple: false,
  }), [
    'Вставьте ссылку на файл (http/https).',
    'Поддерживаются: прямая ссылка, ссылка «Поделиться» из Яндекс Диска, Google Drive, Dropbox, OneDrive.',
  ])

  assert.deepEqual(buildFieldGuidanceHints({
    type: 'disk_file',
    multiple: false,
  }), [
    'Вставьте ссылку на файл (http/https).',
    'Поддерживаются: прямая ссылка, ссылка «Поделиться» из Яндекс Диска, Google Drive, Dropbox, OneDrive.',
  ])
})

test('builds task reference guidance hints for checklist and parent task fields', () => {
  assert.deepEqual(buildFieldGuidanceHints({
    id: 'TASK_ID',
    type: 'integer',
    multiple: false,
  }), [
    'Укажите задачу, в которую нужно импортировать запись.',
    'Поддерживаются Bitrix ID задачи и внешний ключ XML_ID.',
  ])

  assert.deepEqual(buildFieldGuidanceHints({
    id: 'PARENT_ID',
    type: 'integer',
    multiple: false,
  }), [
    'Используйте поле для импорта подзадач с привязкой к родительской задаче.',
    'Поддерживаются Bitrix ID задачи и внешний ключ XML_ID.',
  ])

  assert.deepEqual(buildFieldGuidanceHints({
    id: 'COMPANY_ID',
    type: 'integer',
    multiple: false,
  }), [
    'Укажите Bitrix24 ID компании, чтобы привязать запись к существующей компании.',
    'Если у вас есть только название компании, используйте тип импорта «Компания + Контакт».',
  ])
})

test('builds scenario guide for task checklist import', () => {
  assert.deepEqual(buildEntityScenarioGuide('task_checklist_item'), {
    title: 'Импорт чек-листов в задачи',
    description: 'Каждая строка создаёт один пункт чек-листа в выбранной задаче.',
    highlights: [
      'Минимум для импорта: TASK_ID и TITLE.',
      'TASK_ID можно передавать как Bitrix ID задачи или XML_ID.',
      'IS_COMPLETE позволяет сразу отметить пункт выполненным.',
    ],
    exampleColumns: ['TASK_ID', 'TITLE', 'IS_COMPLETE'],
  })
})

test('builds scenario guide for contact import with explicit company linking rules', () => {
  assert.deepEqual(buildEntityScenarioGuide('contact'), {
    title: 'Импорт контактов',
    description: 'Каждая строка создаёт или обновляет отдельный контакт в CRM.',
    highlights: [
      'Название компании в обычном импорте контактов не создаёт связь автоматически.',
      'Для привязки к существующей компании используйте поле COMPANY_ID и передавайте Bitrix24 ID компании.',
      'Если в исходном файле есть только название компании, используйте тип импорта «Компания + Контакт».',
    ],
    exampleColumns: ['NAME', 'LAST_NAME', 'PHONE', 'EMAIL', 'COMPANY_ID'],
  })
})

test('builds scenario guide for task import with responsible requirement', () => {
  assert.deepEqual(buildEntityScenarioGuide('task'), {
    title: 'Импорт задач и подзадач',
    description: 'Каждая строка создаёт отдельную задачу. Для подзадач можно указать родительскую задачу через PARENT_ID.',
    highlights: [
      'Минимум для импорта: TITLE и RESPONSIBLE_ID или выбранный исполнитель по умолчанию.',
      'Если нужен внешний ключ для последующих связей, добавьте XML_ID.',
      'PARENT_ID принимает Bitrix ID задачи или XML_ID.',
    ],
    exampleColumns: ['TITLE', 'RESPONSIBLE_ID', 'XML_ID', 'PARENT_ID'],
  })
})

test('no longer builds quick start checklist for task scenarios', () => {
  assert.equal(buildTaskScenarioQuickStart('task'), null)
  assert.equal(buildTaskScenarioQuickStart('task_comment'), null)
  assert.equal(buildTaskScenarioQuickStart('task_checklist_item'), null)
  assert.equal(buildTaskScenarioQuickStart('task_attachment'), null)
})

test('builds mapping payload only from mapped rows', () => {
  const payload = buildMappingPayload([
    {
      column: 'A',
      sourceHeader: 'Lead title',
      targetFieldId: 'TITLE',
    },
    {
      column: 'B',
      sourceHeader: 'Phone',
      targetFieldId: '',
    },
    {
      column: 'C',
      sourceHeader: 'Stage',
      targetFieldId: 'STAGE_ID',
      valueMapping: {
        Queued: 'IN_PROGRESS',
      },
    },
  ])

  assert.deepEqual(payload, {
    TITLE: {
      source_header: 'Lead title',
      column: 'A',
      target_field: 'TITLE',
    },
    STAGE_ID: {
      source_header: 'Stage',
      column: 'C',
      target_field: 'STAGE_ID',
      value_mapping: {
        Queued: 'IN_PROGRESS',
      },
    },
  })
})

test('builds value-mapping rows for stage field from preview sample and saved mapping', () => {
  const rows = buildValueMappingRows({
    previewRows: [
      ['Title', 'Stage'],
      ['Lead A', 'Queued'],
      ['Lead B', 'Paused'],
      ['Lead C', 'Queued'],
    ],
    headerRow: 1,
    dataStartRow: 2,
    mappingRows: [
      {
        column: 'B',
        sourceHeader: 'Stage',
        targetFieldId: 'STAGE_ID',
      },
    ],
    fields: [
      {
        id: 'STAGE_ID',
        title: 'Stage',
        items: [
          { id: 'NEW', title: 'New' },
          { id: 'IN_PROGRESS', title: 'In progress' },
        ],
      },
    ],
    savedMapping: {
      STAGE_ID: {
        source_header: 'Stage',
        column: 'B',
        target_field: 'STAGE_ID',
        value_mapping: {
          Queued: 'IN_PROGRESS',
        },
      },
    },
  })

  assert.deepEqual(rows, [
    {
      key: 'STAGE_ID:Queued',
      targetFieldId: 'STAGE_ID',
      targetFieldTitle: 'Stage',
      sourceValue: 'Queued',
      selectedTargetValue: 'IN_PROGRESS',
      options: [
        { value: 'NEW', label: 'New' },
        { value: 'IN_PROGRESS', label: 'In progress' },
      ],
    },
    {
      key: 'STAGE_ID:Paused',
      targetFieldId: 'STAGE_ID',
      targetFieldTitle: 'Stage',
      sourceValue: 'Paused',
      selectedTargetValue: '',
      options: [
        { value: 'NEW', label: 'New' },
        { value: 'IN_PROGRESS', label: 'In progress' },
      ],
    },
  ])
})

test('builds value-mapping rows from backend observed values when they are provided', () => {
  const rows = buildValueMappingRows({
    previewRows: [
      ['Title', 'Stage'],
      ['Lead A', 'Queued'],
      ['Lead B', 'Paused'],
    ],
    headerRow: 1,
    dataStartRow: 2,
    observedValues: {
      STAGE_ID: ['Queued', 'Paused', 'Won'],
    },
    mappingRows: [
      {
        column: 'B',
        sourceHeader: 'Stage',
        targetFieldId: 'STAGE_ID',
      },
    ],
    fields: [
      {
        id: 'STAGE_ID',
        title: 'Stage',
        items: [
          { id: 'NEW', title: 'New' },
          { id: 'IN_PROGRESS', title: 'In progress' },
          { id: 'WON', title: 'Won' },
        ],
      },
    ],
    savedMapping: {
      STAGE_ID: {
        source_header: 'Stage',
        column: 'B',
        target_field: 'STAGE_ID',
        value_mapping: {
          Won: 'WON',
        },
      },
    },
  })

  assert.deepEqual(rows, [
    {
      key: 'STAGE_ID:Queued',
      targetFieldId: 'STAGE_ID',
      targetFieldTitle: 'Stage',
      sourceValue: 'Queued',
      selectedTargetValue: '',
      options: [
        { value: 'NEW', label: 'New' },
        { value: 'IN_PROGRESS', label: 'In progress' },
        { value: 'WON', label: 'Won' },
      ],
    },
    {
      key: 'STAGE_ID:Paused',
      targetFieldId: 'STAGE_ID',
      targetFieldTitle: 'Stage',
      sourceValue: 'Paused',
      selectedTargetValue: '',
      options: [
        { value: 'NEW', label: 'New' },
        { value: 'IN_PROGRESS', label: 'In progress' },
        { value: 'WON', label: 'Won' },
      ],
    },
    {
      key: 'STAGE_ID:Won',
      targetFieldId: 'STAGE_ID',
      targetFieldTitle: 'Stage',
      sourceValue: 'Won',
      selectedTargetValue: 'WON',
      options: [
        { value: 'NEW', label: 'New' },
        { value: 'IN_PROGRESS', label: 'In progress' },
        { value: 'WON', label: 'Won' },
      ],
    },
  ])
})

test('auto-selects exact cyrillic enum values for source and deal type fields', () => {
  const rows = buildValueMappingRows({
    observedValues: {
      SOURCE_ID: ['Реклама'],
      TYPE_ID: ['Сделка'],
    },
    mappingRows: [
      {
        column: 'B',
        sourceHeader: 'Источник',
        targetFieldId: 'SOURCE_ID',
      },
      {
        column: 'C',
        sourceHeader: 'Тип сделки',
        targetFieldId: 'TYPE_ID',
      },
    ],
    fields: [
      {
        id: 'SOURCE_ID',
        title: 'Источник',
        items: [
          { id: 'SALE', title: 'Продажа' },
          { id: 'ADVERTISING', title: 'Реклама' },
        ],
      },
      {
        id: 'TYPE_ID',
        title: 'Тип сделки',
        items: [
          { id: 'SALE', title: 'Продажа' },
          { id: 'DEAL', title: 'Сделка' },
        ],
      },
    ],
    savedMapping: {},
  })

  assert.deepEqual(rows, [
    {
      key: 'SOURCE_ID:Реклама',
      targetFieldId: 'SOURCE_ID',
      targetFieldTitle: 'Источник',
      sourceValue: 'Реклама',
      selectedTargetValue: 'ADVERTISING',
      options: [
        { value: 'SALE', label: 'Продажа' },
        { value: 'ADVERTISING', label: 'Реклама' },
      ],
    },
    {
      key: 'TYPE_ID:Сделка',
      targetFieldId: 'TYPE_ID',
      targetFieldTitle: 'Тип сделки',
      sourceValue: 'Сделка',
      selectedTargetValue: 'DEAL',
      options: [
        { value: 'SALE', label: 'Продажа' },
        { value: 'DEAL', label: 'Сделка' },
      ],
    },
  ])
})

test('builds value-mapping status with unmapped values count', () => {
  const status = buildValueMappingStatus([
    {
      key: 'STAGE_ID:Queued',
      selectedTargetValue: 'IN_PROGRESS',
    },
    {
      key: 'STAGE_ID:Paused',
      selectedTargetValue: '',
    },
    {
      key: 'UF_CRM_STAGE:Won',
      selectedTargetValue: 'WON',
    },
  ])

  assert.deepEqual(status, {
    totalValues: 3,
    mappedValues: 2,
    unmappedValues: 1,
    hasUnmappedValues: true,
  })
})

test('builds summary for backend unmapped list and status values', () => {
  const summary = buildUnmappedValueSummary({
    unmappedValues: {
      STAGE_ID: ['Queued', 'Paused'],
      UF_CRM_STAGE: ['On hold'],
    },
    fields: [
      { id: 'STAGE_ID', title: 'Stage' },
      { id: 'UF_CRM_STAGE', title: 'Pipeline stage' },
    ],
  })

  assert.deepEqual(summary, {
    totalValues: 3,
    fieldCount: 2,
    hasUnmappedValues: true,
    groups: [
      {
        fieldId: 'STAGE_ID',
        fieldTitle: 'Stage',
        values: ['Queued', 'Paused'],
        count: 2,
      },
      {
        fieldId: 'UF_CRM_STAGE',
        fieldTitle: 'Pipeline stage',
        values: ['On hold'],
        count: 1,
      },
    ],
  })
})

test('builds dedup payload with supported strategy and normalized fields', () => {
  const payload = buildDedupPayload({
    strategy: 'update',
    fields: ['phone', 'EMAIL', 'PHONE', 'UNKNOWN'],
  })

  assert.deepEqual(payload, {
    strategy: 'update',
    fields: ['phone', 'EMAIL', 'PHONE', 'UNKNOWN'],
    condition: 'any',
  })

  assert.deepEqual(buildDedupPayload({ strategy: 'create', fields: ['PHONE'] }), {
    strategy: 'create',
    fields: [],
    condition: 'any',
  })
})

test('builds nested dedup payload for linked imports without flattening entity rules', () => {
  const payload = buildDedupPayload({
    company: {
      strategy: 'update',
      fields: ['TITLE'],
      condition: 'all',
    },
    contact: {
      strategy: 'skip',
      fields: ['EMAIL'],
      condition: 'any',
    },
  })

  assert.deepEqual(payload, {
    company: {
      strategy: 'update',
      fields: ['TITLE'],
      condition: 'all',
    },
    contact: {
      strategy: 'skip',
      fields: ['EMAIL'],
      condition: 'any',
    },
  })
})

test('builds dedup payload for smart process fields without uppercasing camelCase ids', () => {
  const payload = buildDedupPayload({
    strategy: 'update',
    fields: ['title', 'stageId', 'ufCrmSmartCode'],
    condition: 'all',
  })

  assert.deepEqual(payload, {
    strategy: 'update',
    fields: ['title', 'stageId', 'ufCrmSmartCode'],
    condition: 'all',
  })
})

test('uses a non-empty select value for unmapped fields and normalizes it back to empty', () => {
  assert.equal(resolveMappingSelectValue(''), EMPTY_MAPPING_SELECT_VALUE)
  assert.equal(resolveMappingSelectValue('PHONE'), 'PHONE')
  assert.equal(normalizeMappingSelectValue(EMPTY_MAPPING_SELECT_VALUE), '')
  assert.equal(normalizeMappingSelectValue('PHONE'), 'PHONE')

  const payload = buildMappingPayload([
    {
      column: 'A',
      sourceHeader: 'Lead title',
      targetFieldId: EMPTY_MAPPING_SELECT_VALUE,
    },
    {
      column: 'B',
      sourceHeader: 'Phone',
      targetFieldId: 'PHONE',
    },
  ])

  assert.deepEqual(payload, {
    PHONE: {
      source_header: 'Phone',
      column: 'B',
      target_field: 'PHONE',
    },
  })
})

test('builds validation issue rows for the validation step table', () => {
  const rows = buildValidationIssueRows({
    issues: [
      {
        row_number: 3,
        column: 'B',
        source_header: 'Email',
        target_field: 'EMAIL',
        message: 'Field "Email" must contain a valid email',
        value: 'broken-email',
      },
      {
        row_number: 4,
        column: 'A',
        source_header: 'Lead title',
        target_field: 'TITLE',
        message: 'Field "Lead title" is required',
        value: '',
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '3:B:EMAIL',
      rowNumber: 3,
      column: 'B',
      sourceHeader: 'Email',
      targetField: 'EMAIL',
      message: 'Field "Email" must contain a valid email',
      value: 'broken-email',
    },
    {
      key: '4:A:TITLE',
      rowNumber: 4,
      column: 'A',
      sourceHeader: 'Lead title',
      targetField: 'TITLE',
      message: 'Field "Lead title" is required',
      value: '—',
    },
  ])
})

test('builds import result rows for the final import summary table', () => {
  const rows = buildImportRunRows({
    results: [
      {
        row_number: 2,
        status: 'created',
        record_id: 501,
        report_date_time: '14.05.2026 09:30:45',
        report_entity: 'Сделка',
        report_title: 'Сделка Альфа',
        report_record_id: '501',
      },
      {
        row_number: 3,
        status: 'updated',
        record_id: 912,
        duplicate_match_fields: ['PHONE'],
        report_date_time: '14.05.2026 09:31:12',
        report_entity: 'Контакт',
        report_title: 'Анна Иванова',
        report_record_id: '912',
      },
      {
        row_number: 4,
        status: 'failed',
        error: 'Bitrix create failed for "Bob"',
        report_date_time: '14.05.2026 09:31:40',
        report_entity: 'Сделка',
        report_title: 'Сделка Бета',
      },
      {
        row_number: 5,
        status: 'skipped_duplicate',
        record_id: 901,
        duplicate_match_fields: ['EMAIL', 'PHONE'],
        error: 'Duplicate matched existing record',
        report_date_time: '14.05.2026 09:32:01',
        report_entity: 'Контакт',
        report_title: 'Боб Смирнов',
        report_record_id: '901',
      },
      {
        row_number: 6,
        status: 'skipped',
        error: 'Row has validation issues',
        report_date_time: '14.05.2026 09:32:30',
        report_entity: 'Задача',
        report_title: 'Подготовить КП',
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '2:created',
      rowNumber: 2,
      status: 'created',
      statusLabel: 'Создано',
      createdAt: '14.05.2026 09:30:45',
      entityLabel: 'Сделка',
      title: 'Сделка Альфа',
      recordId: '501',
      details: '—',
    },
    {
      key: '3:updated',
      rowNumber: 3,
      status: 'updated',
      statusLabel: 'Обновлено',
      createdAt: '14.05.2026 09:31:12',
      entityLabel: 'Контакт',
      title: 'Анна Иванова',
      recordId: '912',
      details: 'Совпадение: Телефон',
    },
    {
      key: '4:failed',
      rowNumber: 4,
      status: 'failed',
      statusLabel: 'Ошибка',
      createdAt: '14.05.2026 09:31:40',
      entityLabel: 'Сделка',
      title: 'Сделка Бета',
      recordId: '—',
      details: 'Bitrix create failed for "Bob"',
    },
    {
      key: '5:skipped_duplicate',
      rowNumber: 5,
      status: 'skipped_duplicate',
      statusLabel: 'Дубль пропущен',
      createdAt: '14.05.2026 09:32:01',
      entityLabel: 'Контакт',
      title: 'Боб Смирнов',
      recordId: '901',
      details: 'Duplicate matched existing record · Совпадение: Email, Телефон',
    },
    {
      key: '6:skipped',
      rowNumber: 6,
      status: 'skipped',
      statusLabel: 'Пропущено',
      createdAt: '14.05.2026 09:32:30',
      entityLabel: 'Задача',
      title: 'Подготовить КП',
      recordId: '—',
      details: 'Row has validation issues',
    },
  ])
})

test('builds dedup weakening warning in import result rows', () => {
  const rows = buildImportRunRows({
    results: [
      {
        row_number: 2,
        status: 'updated',
        record_id: 912,
        duplicate_match_fields: ['EMAIL'],
        dedup_missing_fields: ['PHONE'],
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '2:updated',
      rowNumber: 2,
      status: 'updated',
      statusLabel: 'Обновлено',
      createdAt: '—',
      entityLabel: '—',
      title: '—',
      recordId: '912',
      details: 'Совпадение: Email · Неполный поиск дублей: Телефон',
    },
  ])
})

test('builds clearer linked import result rows with company and contact details', () => {
  const rows = buildImportRunRows({
    results: [
      {
        row_number: 2,
        status: 'created',
        record_id: 73,
        linked_records: {
          company: {
            id: 71,
            title: 'ООО Альфа',
            status: 'created',
          },
          contact: {
            id: 73,
            title: 'Алиса Иванова',
            status: 'created',
          },
        },
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '2:created',
      rowNumber: 2,
      status: 'created',
      statusLabel: 'Создано',
      createdAt: '—',
      entityLabel: 'Компания + Контакт',
      title: 'ООО Альфа / Алиса Иванова',
      recordId: 'Компания 71 · Контакт 73',
      details: 'Компания: ООО Альфа · ID 71 · Контакт: Алиса Иванова · ID 73',
    },
  ])
})

test('builds grouped linked import result rows with primary entity first and nested linked statuses', () => {
  const rows = buildImportRunRows({
    results: [
      {
        row_number: 2,
        status: 'created',
        linked_records: {
          deal: {
            id: 401,
            title: 'Сделка 1',
            status: 'created',
          },
          contact: {
            id: 701,
            title: 'Алиса Иванова',
            status: 'created',
          },
        },
      },
      {
        row_number: 3,
        status: 'updated',
        linked_records: {
          deal: {
            id: 401,
            title: 'Сделка 1',
            status: 'existing',
          },
          contact: {
            id: 702,
            title: 'Борис Петров',
            status: 'created',
          },
        },
      },
    ],
  }, 'linked_deal_contact')

  assert.deepEqual(rows, [
    {
      key: 'deal:401',
      rowNumber: 2,
      rowNumberLabel: '2, 3',
      status: 'created',
      statusLabel: 'Создано',
      createdAt: '—',
      entityLabel: 'Сделка',
      title: 'Сделка 1',
      recordId: '401',
      details: '—',
      hasProblem: false,
      hasDedupRisk: false,
      entityTree: {
        primary: {
          key: 'deal:401:primary',
          entityId: 'deal',
          entityLabel: 'Сделка',
          title: 'Сделка 1',
          recordId: '401',
          status: 'created',
          statusLabel: 'Создано',
          rowNumbers: [2, 3],
          details: '',
        },
        linkedItems: [
          {
            key: 'deal:401:contact:701:0',
            entityId: 'contact',
            entityLabel: 'Контакт',
            title: 'Алиса Иванова',
            recordId: '701',
            status: 'created',
            statusLabel: 'Создано',
            rowNumbers: [2],
            details: '',
          },
          {
            key: 'deal:401:contact:702:1',
            entityId: 'contact',
            entityLabel: 'Контакт',
            title: 'Борис Петров',
            recordId: '702',
            status: 'created',
            statusLabel: 'Создано',
            rowNumbers: [3],
            details: '',
          },
        ],
      },
    },
  ])
})

test('builds clearer linked import result rows with company and deal details', () => {
  const rows = buildImportRunRows({
    results: [
      {
        row_number: 2,
        status: 'created',
        record_id: 91,
        linked_records: {
          company: {
            id: 77,
            title: 'ООО Бета',
            status: 'created',
          },
          deal: {
            id: 91,
            title: 'Внедрение CRM',
            status: 'created',
          },
        },
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '2:created',
      rowNumber: 2,
      status: 'created',
      statusLabel: 'Создано',
      createdAt: '—',
      entityLabel: 'Компания + Сделка',
      title: 'ООО Бета / Внедрение CRM',
      recordId: 'Компания 77 · Сделка 91',
      details: 'Компания: ООО Бета · ID 77 · Сделка: Внедрение CRM · ID 91',
    },
  ])
})

test('builds compact linked import summary with 5 items per page and report overflow note', () => {
  const summary = buildLinkedImportRunSummary({
    results: [
      ...Array.from({ length: 16 }, (_, index) => ({
        row_number: index + 2,
        status: 'created',
        linked_records: {
          company: {
            id: 100 + index,
            title: `Компания ${index + 1}`,
            status: 'created',
          },
          contact: {
            id: 200 + index,
            title: `Контакт ${index + 1}`,
            status: 'created',
          },
        },
      })),
    ],
  })

  assert.deepEqual(summary, {
    hasSummary: true,
    sections: [
      {
        id: 'company',
        title: 'Компании',
        total: 16,
        pageSize: 5,
        pageCount: 3,
        hasOverflow: true,
        items: [
          { key: 'company:100:0', title: 'Компания 1', recordId: '100', statusLabel: 'Создано' },
          { key: 'company:101:1', title: 'Компания 2', recordId: '101', statusLabel: 'Создано' },
          { key: 'company:102:2', title: 'Компания 3', recordId: '102', statusLabel: 'Создано' },
          { key: 'company:103:3', title: 'Компания 4', recordId: '103', statusLabel: 'Создано' },
          { key: 'company:104:4', title: 'Компания 5', recordId: '104', statusLabel: 'Создано' },
          { key: 'company:105:5', title: 'Компания 6', recordId: '105', statusLabel: 'Создано' },
          { key: 'company:106:6', title: 'Компания 7', recordId: '106', statusLabel: 'Создано' },
          { key: 'company:107:7', title: 'Компания 8', recordId: '107', statusLabel: 'Создано' },
          { key: 'company:108:8', title: 'Компания 9', recordId: '108', statusLabel: 'Создано' },
          { key: 'company:109:9', title: 'Компания 10', recordId: '109', statusLabel: 'Создано' },
          { key: 'company:110:10', title: 'Компания 11', recordId: '110', statusLabel: 'Создано' },
          { key: 'company:111:11', title: 'Компания 12', recordId: '111', statusLabel: 'Создано' },
          { key: 'company:112:12', title: 'Компания 13', recordId: '112', statusLabel: 'Создано' },
          { key: 'company:113:13', title: 'Компания 14', recordId: '113', statusLabel: 'Создано' },
          { key: 'company:114:14', title: 'Компания 15', recordId: '114', statusLabel: 'Создано' },
        ],
      },
      {
        id: 'contact',
        title: 'Контакты',
        total: 16,
        pageSize: 5,
        pageCount: 3,
        hasOverflow: true,
        items: [
          { key: 'contact:200:0', title: 'Контакт 1', recordId: '200', statusLabel: 'Создано' },
          { key: 'contact:201:1', title: 'Контакт 2', recordId: '201', statusLabel: 'Создано' },
          { key: 'contact:202:2', title: 'Контакт 3', recordId: '202', statusLabel: 'Создано' },
          { key: 'contact:203:3', title: 'Контакт 4', recordId: '203', statusLabel: 'Создано' },
          { key: 'contact:204:4', title: 'Контакт 5', recordId: '204', statusLabel: 'Создано' },
          { key: 'contact:205:5', title: 'Контакт 6', recordId: '205', statusLabel: 'Создано' },
          { key: 'contact:206:6', title: 'Контакт 7', recordId: '206', statusLabel: 'Создано' },
          { key: 'contact:207:7', title: 'Контакт 8', recordId: '207', statusLabel: 'Создано' },
          { key: 'contact:208:8', title: 'Контакт 9', recordId: '208', statusLabel: 'Создано' },
          { key: 'contact:209:9', title: 'Контакт 10', recordId: '209', statusLabel: 'Создано' },
          { key: 'contact:210:10', title: 'Контакт 11', recordId: '210', statusLabel: 'Создано' },
          { key: 'contact:211:11', title: 'Контакт 12', recordId: '211', statusLabel: 'Создано' },
          { key: 'contact:212:12', title: 'Контакт 13', recordId: '212', statusLabel: 'Создано' },
          { key: 'contact:213:13', title: 'Контакт 14', recordId: '213', statusLabel: 'Создано' },
          { key: 'contact:214:14', title: 'Контакт 15', recordId: '214', statusLabel: 'Создано' },
        ],
      },
    ],
    hasOverflow: true,
    overflowMessage: 'Показаны первые 15 элементов. Остальные детали доступны в CSV-отчете.',
  })
})

test('builds compact linked import summary for company and deal sections', () => {
  const summary = buildLinkedImportRunSummary({
    results: [
      {
        row_number: 2,
        status: 'created',
        linked_records: {
          company: {
            id: 301,
            title: 'Компания 1',
            status: 'created',
          },
          deal: {
            id: 401,
            title: 'Сделка 1',
            status: 'created',
          },
        },
      },
      {
        row_number: 3,
        status: 'updated',
        linked_records: {
          company: {
            id: 302,
            title: 'Компания 2',
            status: 'updated',
          },
          deal: {
            id: 402,
            title: 'Сделка 2',
            status: 'updated',
          },
        },
      },
    ],
  })

  assert.deepEqual(summary, {
    hasSummary: true,
    sections: [
      {
        id: 'company',
        title: 'Компании',
        total: 2,
        pageSize: 5,
        pageCount: 1,
        hasOverflow: false,
        items: [
          { key: 'company:301:0', title: 'Компания 1', recordId: '301', statusLabel: 'Создано' },
          { key: 'company:302:1', title: 'Компания 2', recordId: '302', statusLabel: 'Обновлено' },
        ],
      },
      {
        id: 'deal',
        title: 'Сделки',
        total: 2,
        pageSize: 5,
        pageCount: 1,
        hasOverflow: false,
        items: [
          { key: 'deal:401:0', title: 'Сделка 1', recordId: '401', statusLabel: 'Создано' },
          { key: 'deal:402:1', title: 'Сделка 2', recordId: '402', statusLabel: 'Обновлено' },
        ],
      },
    ],
    hasOverflow: false,
    overflowMessage: '',
  })
})

test('builds compact linked import summary for deal and contact sections in schema order', () => {
  const summary = buildLinkedImportRunSummary({
    results: [
      {
        row_number: 2,
        status: 'created',
        linked_records: {
          deal: {
            id: 401,
            title: 'Сделка 1',
            status: 'created',
          },
          contact: {
            id: 701,
            title: 'Алиса Иванова',
            status: 'created',
          },
        },
      },
      {
        row_number: 3,
        status: 'updated',
        linked_records: {
          deal: {
            id: 401,
            title: 'Сделка 1',
            status: 'existing',
          },
          contact: {
            id: 702,
            title: 'Борис Петров',
            status: 'created',
          },
        },
      },
    ],
  })

  assert.deepEqual(summary, {
    hasSummary: true,
    sections: [
      {
        id: 'deal',
        title: 'Сделки',
        total: 2,
        pageSize: 5,
        pageCount: 1,
        hasOverflow: false,
        items: [
          { key: 'deal:401:0', title: 'Сделка 1', recordId: '401', statusLabel: 'Создано' },
          { key: 'deal:401:1', title: 'Сделка 1', recordId: '401', statusLabel: 'Найдено' },
        ],
      },
      {
        id: 'contact',
        title: 'Контакты',
        total: 2,
        pageSize: 5,
        pageCount: 1,
        hasOverflow: false,
        items: [
          { key: 'contact:701:0', title: 'Алиса Иванова', recordId: '701', statusLabel: 'Создано' },
          { key: 'contact:702:1', title: 'Борис Петров', recordId: '702', statusLabel: 'Создано' },
        ],
      },
    ],
    hasOverflow: false,
    overflowMessage: '',
  })
})

test('builds retry state only for failed and validation-skipped import rows', () => {
  const retryState = buildImportRunRetryState({
    results: [
      { row_number: 2, status: 'created' },
      { row_number: 3, status: 'failed' },
      { row_number: 4, status: 'skipped' },
      { row_number: 5, status: 'skipped_duplicate' },
      { row_number: 6, status: 'updated' },
    ],
  })

  assert.deepEqual(retryState, {
    retryableRows: 2,
    hasRetryableRows: true,
    retryableRowNumbers: [3, 4],
  })
})

test('treats cancelled import rows as retryable and labels them as stopped', () => {
  const importRunData = {
    results: [
      { row_number: 2, status: 'created', record_id: 501 },
      { row_number: 3, status: 'cancelled', error: 'Import was cancelled before row execution' },
    ],
  }

  assert.deepEqual(buildImportRunRetryState(importRunData), {
    retryableRows: 1,
    hasRetryableRows: true,
    retryableRowNumbers: [3],
  })

  assert.deepEqual(buildImportRunRows(importRunData), [
    {
      key: '2:created',
      rowNumber: 2,
      status: 'created',
      statusLabel: 'Создано',
      createdAt: '—',
      entityLabel: '—',
      title: '—',
      recordId: '501',
      details: '—',
    },
    {
      key: '3:cancelled',
      rowNumber: 3,
      status: 'cancelled',
      statusLabel: 'Остановлено',
      createdAt: '—',
      entityLabel: '—',
      title: '—',
      recordId: '—',
      details: 'Import was cancelled before row execution',
    },
  ])
})

test('builds grouped problem summary and status filters for import report', () => {
  const importRunData = {
    results: [
      { row_number: 2, status: 'created', record_id: 501 },
      { row_number: 3, status: 'failed', error: 'Bitrix create failed for "Bob"' },
      { row_number: 4, status: 'skipped', error: 'Row has validation issues' },
      { row_number: 5, status: 'skipped', error: 'Row has validation issues' },
      { row_number: 6, status: 'cancelled', error: 'Import was cancelled before row execution' },
      { row_number: 7, status: 'updated', record_id: 900 },
      { row_number: 8, status: 'skipped_duplicate', record_id: 901, error: 'Duplicate matched existing record' },
    ],
  }

  assert.deepEqual(buildImportRunStatusFilters(importRunData), [
    { id: 'all', label: 'Все', count: 7 },
    { id: 'problem', label: 'Проблемные', count: 4 },
    { id: 'dedup_risk', label: 'Риск дублей', count: 0 },
    { id: 'created', label: 'Создано', count: 1 },
    { id: 'updated', label: 'Обновлено', count: 1 },
    { id: 'failed', label: 'Ошибки', count: 1 },
    { id: 'skipped', label: 'Пропущено', count: 3 },
    { id: 'cancelled', label: 'Остановлено', count: 1 },
  ])

  assert.equal(resolveImportRunFilterId(importRunData), 'problem')
  assert.equal(resolveImportRunFilterId(importRunData, 'updated'), 'updated')
  assert.equal(resolveImportRunFilterId({ results: [{ row_number: 2, status: 'created', record_id: 501 }] }), 'all')

  assert.deepEqual(buildImportRunProblemGroups(importRunData), [
    {
      key: 'failed:Bitrix create failed for "Bob"',
      label: 'Ошибка',
      reason: 'Bitrix create failed for "Bob"',
      count: 1,
      rowNumbers: [3],
      statuses: ['failed'],
    },
    {
      key: 'skipped:Row has validation issues',
      label: 'Пропущено',
      reason: 'Row has validation issues',
      count: 2,
      rowNumbers: [4, 5],
      statuses: ['skipped'],
    },
    {
      key: 'cancelled:Import was cancelled before row execution',
      label: 'Остановлено',
      reason: 'Import was cancelled before row execution',
      count: 1,
      rowNumbers: [6],
      statuses: ['cancelled'],
    },
  ])

  const rows = buildImportRunRows(importRunData)
  assert.deepEqual(
    filterImportRunRows(rows, 'problem').map((row) => row.rowNumber),
    [3, 4, 5, 6],
  )
  assert.deepEqual(
    filterImportRunRows(rows, 'skipped').map((row) => row.rowNumber),
    [4, 5, 8],
  )
  assert.deepEqual(
    filterImportRunRows(rows, 'all').map((row) => row.rowNumber),
    [2, 3, 4, 5, 6, 7, 8],
  )
})

test('builds dry run rows for preview before import execution', () => {
  const rows = buildDryRunRows({
    results: [
      {
        row_number: 2,
        status: 'ready',
        fields: {
          TITLE: 'Alice',
          PHONE: [{ VALUE: '+123456789', VALUE_TYPE: 'WORK' }],
        },
      },
      {
        row_number: 3,
        status: 'ready_update',
        record_id: 902,
        duplicate_match_fields: ['EMAIL'],
        fields: {
          TITLE: 'Bob',
          EMAIL: 'bob@example.com',
        },
      },
      {
        row_number: 4,
        status: 'skipped_duplicate',
        record_id: 903,
        duplicate_match_fields: ['EMAIL', 'PHONE'],
        error: 'Duplicate matched existing record',
      },
      {
        row_number: 5,
        status: 'skipped',
        error: 'Row has validation issues',
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '2:ready',
      rowNumber: 2,
      status: 'ready',
      statusLabel: 'Готово',
      details: 'Название / заголовок: Alice · Телефон: +123456789',
    },
    {
      key: '3:ready_update',
      rowNumber: 3,
      status: 'ready_update',
      statusLabel: 'Готово к обновлению',
      details: 'Название / заголовок: Bob · Email: bob@example.com · Совпадение: Email',
    },
    {
      key: '4:skipped_duplicate',
      rowNumber: 4,
      status: 'skipped_duplicate',
      statusLabel: 'Дубль пропущен',
      details: 'Duplicate matched existing record · Совпадение: Email, Телефон',
    },
    {
      key: '5:skipped',
      rowNumber: 5,
      status: 'skipped',
      statusLabel: 'Пропущено',
      details: 'Row has validation issues',
    },
  ])
})

test('builds grouped linked dry run rows with primary entity first and nested linked statuses', () => {
  const rows = buildDryRunRows({
    results: [
      {
        row_number: 2,
        status: 'ready',
        fields: {
          DEAL__EXTERNAL_KEY: 'DEAL-1',
          DEAL__TITLE: 'Сделка 1',
          CONTACT__NAME: 'Алиса',
          CONTACT__LAST_NAME: 'Иванова',
          CONTACT__EMAIL: 'alice@example.com',
        },
      },
      {
        row_number: 3,
        status: 'ready_update',
        fields: {
          DEAL__EXTERNAL_KEY: 'DEAL-1',
          DEAL__TITLE: 'Сделка 1',
          CONTACT__NAME: 'Борис',
          CONTACT__LAST_NAME: 'Петров',
          CONTACT__EMAIL: 'boris@example.com',
        },
        linked: {
          contact: {
            duplicate_match_fields: ['EMAIL'],
          },
        },
      },
    ],
  }, 'linked_deal_contact')

  assert.deepEqual(rows, [
    {
      key: 'deal:DEAL-1',
      rowNumber: 2,
      rowNumberLabel: '2, 3',
      status: 'ready',
      statusLabel: 'Готово',
      details: '—',
      entityTree: {
        primary: {
          key: 'deal:DEAL-1:primary',
          entityId: 'deal',
          entityLabel: 'Сделка',
          title: 'Сделка 1',
          recordId: '—',
          status: 'ready',
          statusLabel: 'Готово',
          rowNumbers: [2, 3],
          details: '',
        },
        linkedItems: [
          {
            key: 'deal:DEAL-1:contact:alice@example.com:0',
            entityId: 'contact',
            entityLabel: 'Контакт',
            title: 'Алиса Иванова',
            recordId: '—',
            status: 'ready',
            statusLabel: 'Готово',
            rowNumbers: [2],
            details: '',
          },
          {
            key: 'deal:DEAL-1:contact:boris@example.com:1',
            entityId: 'contact',
            entityLabel: 'Контакт',
            title: 'Борис Петров',
            recordId: '—',
            status: 'ready_update',
            statusLabel: 'Готово к обновлению',
            rowNumbers: [3],
            details: '',
          },
        ],
      },
    },
  ])
})

test('builds dedup weakening warning in dry run rows', () => {
  const rows = buildDryRunRows({
    results: [
      {
        row_number: 2,
        status: 'ready',
        dedup_missing_fields: ['PHONE'],
        fields: {
          TITLE: 'Alice',
          EMAIL: 'alice@example.com',
        },
      },
    ],
  })

  assert.deepEqual(rows, [
    {
      key: '2:ready',
      rowNumber: 2,
      status: 'ready',
      statusLabel: 'Готово',
      details: 'Название / заголовок: Alice · Email: alice@example.com · Неполный поиск дублей: Телефон',
    },
  ])
})

test('builds dedup weakening notice summary for preview and import result', () => {
  assert.deepEqual(buildDedupWeakeningNotice({
    results: [
      { row_number: 2, dedup_missing_fields: ['PHONE'] },
      { row_number: 3, dedup_missing_fields: ['EMAIL', 'PHONE'] },
      { row_number: 4 },
    ],
  }), {
    hasWarnings: true,
    count: 2,
    title: 'Неполный поиск дублей в 2 строках',
    description: 'Поиск дублей выполнен не по всем выбранным полям.',
    fieldsLabel: 'Email, Телефон',
    rowsLabel: '2, 3',
    rowNumbers: [2, 3],
  })

  assert.deepEqual(buildDedupWeakeningNotice({ results: [] }), {
    hasWarnings: false,
    count: 0,
    title: '',
    description: '',
    fieldsLabel: '',
    rowsLabel: '',
    rowNumbers: [],
  })
})

test('adds dedup risk filter to import result filters and rows', () => {
  const importRunData = {
    results: [
      { row_number: 2, status: 'updated', record_id: 901, duplicate_match_fields: ['EMAIL'], dedup_missing_fields: ['PHONE'] },
      { row_number: 3, status: 'failed', error: 'Bitrix create failed' },
      { row_number: 4, status: 'created', record_id: 902 },
      { row_number: 5, status: 'skipped_duplicate', record_id: 903, duplicate_match_fields: ['PHONE'], dedup_missing_fields: ['EMAIL'] },
    ],
  }

  assert.deepEqual(buildImportRunStatusFilters(importRunData), [
    { id: 'all', label: 'Все', count: 4 },
    { id: 'problem', label: 'Проблемные', count: 1 },
    { id: 'dedup_risk', label: 'Риск дублей', count: 2 },
    { id: 'created', label: 'Создано', count: 1 },
    { id: 'updated', label: 'Обновлено', count: 1 },
    { id: 'failed', label: 'Ошибки', count: 1 },
    { id: 'skipped', label: 'Пропущено', count: 1 },
    { id: 'cancelled', label: 'Остановлено', count: 0 },
  ])

  assert.equal(resolveImportRunFilterId(importRunData, 'dedup_risk'), 'dedup_risk')

  const rows = buildImportRunRows(importRunData)
  assert.deepEqual(
    filterImportRunRows(rows, 'dedup_risk').map((row) => row.rowNumber),
    [2, 5],
  )
})

test('builds recent session rows for import history panel', () => {
  const rows = buildSessionHistoryRows([
    {
      id: 'session-1',
      original_filename: 'contacts.xlsx',
      entity_type: 'contact',
      status: 'completed',
      successful_rows: 8,
      failed_rows: 1,
      summary: {
        import_run: {
          created_rows: 6,
          updated_rows: 2,
          skipped_rows: 1,
          failed_rows: 1,
        },
      },
      updated_at: '2026-05-05T18:00:00+00:00',
    },
    {
      id: 'session-2',
      original_filename: 'checklist.xlsx',
      entity_type: 'task_checklist_item',
      status: 'completed',
      successful_rows: 3,
      failed_rows: 0,
      updated_at: '2026-05-05T18:10:00+00:00',
    },
  ])

  assert.deepEqual(rows, [
    {
      key: 'session-1',
      fileName: 'contacts.xlsx',
      status: 'completed',
      entityType: 'Контакты',
      statusLabel: 'Завершено',
      resultLabel: 'Успех',
      resultTone: 'success',
      actionLabel: 'Открыть',
      counters: {
        created: 6,
        updated: 2,
        skipped: 1,
        failed: 1,
        total: 0,
        hasData: true,
      },
      sourceFormat: 'xlsx',
      sourceFormatLabel: 'Excel',
      updatedAt: '2026-05-05T18:00:00+00:00',
      updatedAtLabel: '05.05.2026 18:00',
    },
    {
      key: 'session-2',
      fileName: 'checklist.xlsx',
      status: 'completed',
      entityType: 'Чек-листы задач',
      statusLabel: 'Завершено',
      resultLabel: 'Успех',
      resultTone: 'success',
      actionLabel: 'Открыть',
      counters: {
        created: 3,
        updated: 0,
        skipped: 0,
        failed: 0,
        total: 3,
        hasData: true,
      },
      sourceFormat: 'xlsx',
      sourceFormatLabel: 'Excel',
      updatedAt: '2026-05-05T18:10:00+00:00',
      updatedAtLabel: '05.05.2026 18:10',
    },
  ])
})

test('builds continue action for unfinished history sessions', () => {
  const rows = buildSessionHistoryRows([
    {
      id: 'session-running',
      original_filename: 'deals.xlsx',
      entity_type: 'deal',
      status: 'running',
      successful_rows: 10,
      failed_rows: 0,
      updated_at: '2026-05-05T18:20:00+00:00',
    },
  ])

  assert.equal(rows[0].actionLabel, 'Продолжить')
})

test('builds import run summary from session snapshot when aggregate counters are missing', () => {
  assert.deepEqual(buildImportRunSummaryFromSessionSnapshot({
    id: 'session-contacts-1',
    status: 'completed',
    processed_rows: 2,
    successful_rows: 2,
    failed_rows: 0,
    summary: {
      import_run: {
        results: [
          { row_number: 2, status: 'created', record_id: 501 },
          { row_number: 3, status: 'created', record_id: 502 },
        ],
      },
    },
  }), {
    session_id: 'session-contacts-1',
    status: 'completed',
    retried_rows: 0,
    retry_result: null,
    checked_rows: 2,
    created_rows: 2,
    updated_rows: 0,
    failed_rows: 0,
    skipped_rows: 0,
    cancelled: false,
    cancelled_rows: 0,
    remaining_rows: 0,
    created_ids: [501, 502],
    updated_ids: [],
    results: [
      { row_number: 2, status: 'created', record_id: 501 },
      { row_number: 3, status: 'created', record_id: 502 },
    ],
  })
})

test('builds import run summary from top-level session counters when import_run is absent', () => {
  assert.deepEqual(buildImportRunSummaryFromSessionSnapshot({
    id: 'session-contacts-2',
    status: 'completed',
    processed_rows: 2,
    successful_rows: 2,
    failed_rows: 0,
    summary: {
      job: {
        mode: 'run',
        state: 'completed',
      },
    },
  }), {
    session_id: 'session-contacts-2',
    status: 'completed',
    retried_rows: 0,
    retry_result: null,
    checked_rows: 2,
    created_rows: 2,
    updated_rows: 0,
    failed_rows: 0,
    skipped_rows: 0,
    cancelled: false,
    cancelled_rows: 0,
    remaining_rows: 0,
    created_ids: [],
    updated_ids: [],
    results: [],
  })
})

test('builds cancelled import run summary from top-level session counters when import_run is absent', () => {
  assert.deepEqual(buildImportRunSummaryFromSessionSnapshot({
    id: 'session-contacts-3',
    status: 'cancelled',
    total_rows: 900,
    processed_rows: 120,
    successful_rows: 118,
    failed_rows: 2,
    summary: {
      job: {
        mode: 'run',
        state: 'cancelled',
      },
    },
  }), {
    session_id: 'session-contacts-3',
    status: 'cancelled',
    retried_rows: 0,
    retry_result: null,
    checked_rows: 120,
    created_rows: 118,
    updated_rows: 0,
    failed_rows: 2,
    skipped_rows: 0,
    cancelled: true,
    cancelled_rows: 780,
    remaining_rows: 780,
    created_ids: [],
    updated_ids: [],
    results: [],
  })
})

test('builds dry run summary from session snapshot when background dry run completes', () => {
  assert.deepEqual(buildDryRunSummaryFromSessionSnapshot({
    id: 'session-dry-run-1',
    status: 'validated',
    summary: {
      dry_run: {
        checked_rows: 2,
        ready_rows: 2,
        ready_create_rows: 1,
        ready_update_rows: 1,
        skipped_rows: 0,
        pending_decision_rows: 0,
        results: [
          { row_number: 2, status: 'ready', fields: { TITLE: 'Alice' } },
          { row_number: 3, status: 'ready_update', record_id: 915, fields: { TITLE: 'Bob' } },
        ],
      },
      job: {
        mode: 'dry_run',
        state: 'completed',
      },
    },
  }), {
    session_id: 'session-dry-run-1',
    status: 'validated',
    checked_rows: 2,
    ready_rows: 2,
    ready_create_rows: 1,
    ready_update_rows: 1,
    skipped_rows: 0,
    pending_decision_rows: 0,
    results: [
      { row_number: 2, status: 'ready', fields: { TITLE: 'Alice' } },
      { row_number: 3, status: 'ready_update', record_id: 915, fields: { TITLE: 'Bob' } },
    ],
  })
})

test('keeps waiting for queued import snapshot while status is still running even if counters are already filled', () => {
  assert.equal(shouldWaitForImportExecutionSnapshot({
    id: 'session-running-1',
    status: 'running',
    processed_rows: 1,
    successful_rows: 1,
    failed_rows: 0,
    summary: {
      validation: {
        checked_rows: 1,
        valid_rows: 1,
      },
    },
  }), true)

  assert.equal(shouldWaitForImportExecutionSnapshot({
    id: 'session-running-2',
    status: 'running',
    summary: {
      import_run: {
        checked_rows: 2,
        created_rows: 1,
        failed_rows: 1,
        results: [
          { row_number: 2, status: 'created', record_id: 501 },
          { row_number: 3, status: 'failed', error: 'Boom' },
        ],
      },
      job: {
        mode: 'retry',
        state: 'queued',
      },
    },
  }), true)

  assert.equal(shouldWaitForImportExecutionSnapshot({
    id: 'session-completed-1',
    status: 'completed',
    processed_rows: 1,
    successful_rows: 1,
    failed_rows: 0,
    summary: {},
  }), false)

  assert.equal(shouldWaitForImportExecutionSnapshot({
    id: 'session-validated-1',
    status: 'validated',
    processed_rows: 902,
    successful_rows: 902,
    failed_rows: 0,
    summary: {
      job: {
        mode: 'preimport_scan',
        state: 'completed',
      },
      preimport_scan: {
        checked_rows: 902,
        ready_rows: 902,
      },
    },
  }), false)

  assert.equal(shouldWaitForImportExecutionSnapshot({
    id: 'session-queued-1',
    status: 'validated',
    summary: {
      job: {
        mode: 'run',
        state: 'queued',
      },
    },
  }), true)
})

test('keeps waiting for queued dry run snapshot while background check is active', () => {
  assert.equal(shouldWaitForDryRunExecutionSnapshot({
    id: 'session-dry-run-queued',
    status: 'running',
    processed_rows: 200,
    summary: {
      job: {
        mode: 'dry_run',
        state: 'queued',
      },
    },
  }), true)

  assert.equal(shouldWaitForDryRunExecutionSnapshot({
    id: 'session-dry-run-running',
    status: 'running',
    processed_rows: 500,
    summary: {
      job: {
        mode: 'dry_run',
        state: 'running',
      },
    },
  }), true)

  assert.equal(shouldWaitForDryRunExecutionSnapshot({
    id: 'session-dry-run-completed',
    status: 'validated',
    summary: {
      dry_run: {
        checked_rows: 10,
        ready_rows: 9,
      },
      job: {
        mode: 'dry_run',
        state: 'completed',
      },
    },
  }), false)
})

test('resolves pending dry run rows using duplicate decisions', () => {
  assert.deepEqual(buildResolvedDryRunSummary({
    session_id: 'session-dry-run-ask',
    status: 'validated',
    checked_rows: 4,
    ready_rows: 1,
    ready_create_rows: 1,
    ready_update_rows: 0,
    skipped_rows: 0,
    pending_decision_rows: 3,
    results: [
      { row_number: 2, status: 'ready', fields: { TITLE: 'Alice' } },
      { row_number: 3, status: 'pending_decision', record_id: 901, duplicate_match_fields: ['PHONE'], fields: { TITLE: 'Bob' } },
      { row_number: 4, status: 'pending_decision', record_id: 902, duplicate_match_fields: ['EMAIL'], fields: { TITLE: 'Carol' } },
      { row_number: 5, status: 'pending_decision', record_id: 903, duplicate_match_fields: ['TITLE'], fields: { TITLE: 'Dave' } },
    ],
  }, {
    3: 'update',
    4: 'skip',
    5: 'create',
  }), {
    session_id: 'session-dry-run-ask',
    status: 'validated',
    checked_rows: 4,
    ready_rows: 3,
    ready_create_rows: 2,
    ready_update_rows: 1,
    skipped_rows: 1,
    pending_decision_rows: 0,
    results: [
      { row_number: 2, status: 'ready', fields: { TITLE: 'Alice' } },
      { row_number: 3, status: 'ready_update', record_id: 901, duplicate_match_fields: ['PHONE'], fields: { TITLE: 'Bob' } },
      {
        row_number: 4,
        status: 'skipped_duplicate',
        record_id: 902,
        duplicate_match_fields: ['EMAIL'],
        fields: { TITLE: 'Carol' },
        error: 'Duplicate skipped by user decision',
      },
      { row_number: 5, status: 'ready', record_id: 903, duplicate_match_fields: ['TITLE'], fields: { TITLE: 'Dave' } },
    ],
  })
})

test('builds collapsed state for recent import history panel', () => {
  const state = buildCollapsibleHistoryState([
    { key: '1', fileName: 'a.xlsx' },
    { key: '2', fileName: 'b.xlsx' },
    { key: '3', fileName: 'c.xlsx' },
    { key: '4', fileName: 'd.xlsx' },
  ], {
    expanded: false,
    collapsedCount: 2,
  })

  assert.deepEqual(state, {
    visibleItems: [
      { key: '1', fileName: 'a.xlsx' },
      { key: '2', fileName: 'b.xlsx' },
    ],
    hiddenCount: 2,
    canExpand: true,
  })
})

test('importer workbench keeps wizard navigation only in top step action bars', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const importerUiUtilsSource = readFileSync(
    new URL('../app/utils/importer-ui.js', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('showInlineWizardFooter'), false)
  assert.equal(importerWorkbenchSource.includes('footerStatusLabel'), false)
  assert.equal(importerWorkbenchSource.includes('progressPercent'), false)
  assert.equal(importerUiUtilsSource.includes('shouldRenderInlineWizardFooter'), false)
  assert.equal(importerWorkbenchSource.includes('label="Применить и продолжить"'), true)
  assert.equal(importerWorkbenchSource.includes('label="Сохранить соответствие"'), true)
  assert.equal(importerWorkbenchSource.includes('v-if="!hasPendingMappingChanges"'), true)
  assert.equal(
    importerWorkbenchSource.includes('Сохраните соответствие и выбранные значения по умолчанию, чтобы перейти к следующему шагу.'),
    true,
  )
})

test('builds finish action state for the last wizard step', () => {
  assert.equal(getWizardNextLabel(2), 'Далее: Предпросмотр')
  assert.equal(getWizardNextLabel(7), 'Финиш')

  assert.equal(getWizardAdvanceMode(2, 3), 'next')
  assert.equal(getWizardAdvanceMode(7, 7), 'finish')
  assert.equal(getWizardAdvanceMode(4, 4), 'disabled')

  assert.equal(canAdvanceWizard(2, 3), true)
  assert.equal(canAdvanceWizard(7, 7), true)
  assert.equal(canAdvanceWizard(4, 4), false)
})

test('blocks wizard advance from mapping step when required fields are still missing', () => {
  assert.equal(canAdvanceWizard(4, 5, {
    hasMissingRequiredFields: true,
  }), false)

  assert.equal(canAdvanceWizard(4, 5, {
    hasMissingRequiredFields: false,
  }), true)
})

test('importer workbench ignores contact second name in required mapping summary', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("ignoreFieldIds: entityType.value === 'contact' ? ['SECOND_NAME'] : []"), true)
})

test('importer workbench supports default author selection for task comments', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const taskDefaultCommentAuthorId = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes("...(taskDefaultCommentAuthorId.value ? ['AUTHOR_ID'] : [])"), true)
  assert.equal(importerWorkbenchSource.includes('Пользователь по умолчанию'), true)
  assert.equal(importerWorkbenchSource.includes('AUTHOR_ID'), true)
})

test('importer workbench supports default creator selection for tasks', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const taskDefaultCreatorId = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes("...(taskDefaultCreatorId.value ? ['CREATED_BY'] : [])"), true)
  assert.equal(importerWorkbenchSource.includes('Постановщик по умолчанию'), true)
  assert.equal(importerWorkbenchSource.includes('CREATED_BY'), true)
})

test('step 1 no longer renders quick start block', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Quick Start'), false)
  assert.equal(importerWorkbenchSource.includes('currentTaskQuickStart'), false)
})

test('step 1 no longer renders inline history block, history is on a dedicated page', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Последние импорты'), false)
  assert.equal(importerWorkbenchSource.includes('historyCollapsedState.visibleItems'), false)
  assert.equal(importerWorkbenchSource.includes('currentView === \'history\''), true)
  assert.equal(importerWorkbenchSource.includes('История импортов'), true)
  assert.equal(
    importerWorkbenchSource.includes('xl:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]'),
    false,
  )
})

test('step 1 mode selection screen uses the new return label and hr card no longer mentions roles', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Выбрать режим'), true)
  assert.equal(importerWorkbenchSource.includes('Расширенный режим'), false)
  assert.equal(importerWorkbenchSource.includes('>Роли<'), false)
})

test('builds compact migration status badge state for the sidebar card', () => {
  assert.deepEqual(buildMigrationStatusBadge({}), {
    label: 'Ожидает запуска',
    tone: 'idle',
  })

  assert.deepEqual(buildMigrationStatusBadge({
    sessionId: 'session-1',
  }), {
    label: 'Все в порядке',
    tone: 'ok',
  })

  assert.deepEqual(buildMigrationStatusBadge({
    sessionId: 'session-1',
    busyAction: 'structure',
  }), {
    label: 'В процессе',
    tone: 'busy',
  })

  assert.deepEqual(buildMigrationStatusBadge({
    sessionId: 'session-1',
    validationIssueCount: 2,
  }), {
    label: 'Ошибка',
    tone: 'error',
  })
})

test('builds permission-aware importer access state for operator and viewer', () => {
  assert.deepEqual(buildImporterPermissionState({
    role: 'operator',
    permissions: ['sessions.view', 'sessions.create', 'sessions.edit_own', 'sessions.run', 'templates.manage'],
    isPortalAdmin: false,
  }), {
    role: 'operator',
    isPortalAdmin: false,
    permissions: ['sessions.view', 'sessions.create', 'sessions.edit_own', 'sessions.run', 'templates.manage'],
    canManageRoles: false,
    canManageTemplates: true,
    canCreateSessions: true,
    canEditSessions: true,
    canViewSessions: true,
    canRunSessions: true,
    canCancelSessions: false,
    canViewReports: false,
    isReadOnly: false,
  })

  assert.deepEqual(buildImporterPermissionState({
    role: 'viewer',
    permissions: ['sessions.view', 'reports.view'],
    isPortalAdmin: false,
  }), {
    role: 'viewer',
    isPortalAdmin: false,
    permissions: ['sessions.view', 'reports.view'],
    canManageRoles: false,
    canManageTemplates: false,
    canCreateSessions: false,
    canEditSessions: false,
    canViewSessions: true,
    canRunSessions: false,
    canCancelSessions: false,
    canViewReports: true,
    isReadOnly: true,
  })

  assert.deepEqual(buildImporterPermissionState({
    role: 'none',
    permissions: [],
    isPortalAdmin: false,
  }), {
    role: 'none',
    isPortalAdmin: false,
    permissions: [],
    canManageRoles: false,
    canManageTemplates: false,
    canCreateSessions: false,
    canEditSessions: false,
    canViewSessions: false,
    canRunSessions: false,
    canCancelSessions: false,
    canViewReports: false,
    isReadOnly: false,
  })
})

test('falls back to full importer access when permission payload is empty', () => {
  assert.deepEqual(buildImporterPermissionState({}), {
    role: 'portal_admin',
    isPortalAdmin: true,
    permissions: [
      'roles.manage',
      'templates.manage',
      'sessions.create',
      'sessions.edit_own',
      'sessions.view',
      'sessions.run',
      'sessions.cancel',
      'reports.view',
    ],
    canManageRoles: true,
    canManageTemplates: true,
    canCreateSessions: true,
    canEditSessions: true,
    canViewSessions: true,
    canRunSessions: true,
    canCancelSessions: true,
    canViewReports: true,
    isReadOnly: false,
  })
})

test('builds normalized rows for importer role assignments', () => {
  assert.deepEqual(buildRoleAssignmentsRows([
    {
      id: 'role-1',
      b24_user_id: 59,
      role: 'operator',
      granted_by_b24_user_id: 1,
      updated_at: '2026-05-06T08:00:00+00:00',
    },
    {
      id: 'role-2',
      b24_user_id: 77,
      role: 'viewer',
      granted_by_b24_user_id: 1,
      updated_at: '2026-05-06T08:10:00+00:00',
    },
  ]), [
    {
      key: 'role-1',
      userId: '59',
      role: 'operator',
      roleLabel: 'Оператор',
      grantedByUserId: '1',
      updatedAt: '2026-05-06T08:00:00+00:00',
    },
    {
      key: 'role-2',
      userId: '77',
      role: 'viewer',
      roleLabel: 'Только просмотр',
      grantedByUserId: '1',
      updatedAt: '2026-05-06T08:10:00+00:00',
    },
  ])
})

test('builds validated payload for importer role assignment form', () => {
  assert.deepEqual(buildRoleAssignmentPayload({
    userId: ' 59 ',
    role: 'operator',
  }), {
    b24_user_id: 59,
    role: 'operator',
  })

  assert.throws(() => buildRoleAssignmentPayload({
    userId: 'abc',
    role: 'viewer',
  }), /Bitrix user ID/)

  assert.throws(() => buildRoleAssignmentPayload({
    userId: '59',
    role: 'portal_admin',
  }), /роль/)
})

test('step 1 no longer renders selected scenario block title', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Выбранный сценарий'), false)
})

test('step 1 does not preselect crm entity by default', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const selectedCrmEntityType = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes("const selectedCrmEntityType = ref('deal')"), false)
})

test('step 1 keeps crm and task selectors mutually exclusive', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("selectedTaskEntityType.value = ''"), true)
  assert.equal(importerWorkbenchSource.includes("selectedCrmEntityType.value = ''"), true)
})

test('step 1 supports dependent linked import selectors and keeps them mutually exclusive with crm and task', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const selectedLinkedPrimaryEntityType = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes("const selectedLinkedSecondaryEntityType = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes("selectedLinkedPrimaryEntityType.value = ''"), true)
  assert.equal(importerWorkbenchSource.includes("selectedLinkedSecondaryEntityType.value = ''"), true)
  assert.equal(importerWorkbenchSource.includes('resolveLinkedStrategyEntityType'), true)
  assert.equal(importerWorkbenchSource.includes('Выберите основную сущность'), true)
  assert.equal(importerWorkbenchSource.includes('Выберите связанную сущность'), true)
})

test('crm flavor selection syncs the visible card with the active scenario used by action buttons', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("function selectCrmFlavor(value: 'direct' | 'linked' | 'bulk')"), true)
  assert.equal(importerWorkbenchSource.includes("entityType.value = selectedCrmEntityType.value"), true)
  assert.equal(importerWorkbenchSource.includes("entityType.value = resolveLinkedStrategyEntityType("), true)
  assert.equal(importerWorkbenchSource.includes("entityType.value = selectedFileAttachEntityType.value"), true)
  assert.equal(importerWorkbenchSource.includes("@click=\"selectCrmFlavor(f.key as 'direct' | 'linked' | 'bulk')\""), true)
})

test('final step renders compact linked import summary with paging and csv fallback note', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Что создано по связанному импорту'), true)
  assert.equal(importerWorkbenchSource.includes('linkedImportRunSummary.overflowMessage'), true)
  assert.equal(importerWorkbenchSource.includes('linkedSummaryPage'), true)
  assert.equal(importerWorkbenchSource.includes('Показываем по 5 элементов на страницу, чтобы экран не перегружался.'), false)
  assert.equal(
    importerWorkbenchSource.includes('v-if="!isLinkedCompanyContactImport || !linkedImportRunSummary.hasSummary"'),
    false,
  )
  assert.equal(importerWorkbenchSource.includes('hasLinkedEntityTree(row.original)'), true)
})

test('dry run and import result tables prioritize bitrix payload column and remove standalone status column', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const dryRunStart = importerWorkbenchSource.indexOf('const dryRunTableColumns = computed(() => [')
  const dryRunEnd = importerWorkbenchSource.indexOf('])\n\nwatch(maxAvailableStep', dryRunStart)
  const importRunStart = importerWorkbenchSource.indexOf('const importRunTableColumns = computed(() => [')
  const importRunEnd = importerWorkbenchSource.indexOf('const dryRunTableColumns = computed(() => [', importRunStart)
  const dryRunSource = importerWorkbenchSource.slice(dryRunStart, dryRunEnd)
  const importRunSource = importerWorkbenchSource.slice(importRunStart, importRunEnd)

  assert.equal(dryRunSource.indexOf("accessorKey: 'details'") < dryRunSource.indexOf("accessorKey: 'rowNumber'"), true)
  assert.equal(importRunSource.indexOf("accessorKey: 'details'") < importRunSource.indexOf("accessorKey: 'rowNumber'"), true)
  assert.equal(dryRunSource.includes("accessorKey: 'statusLabel'"), false)
  assert.equal(importRunSource.includes("accessorKey: 'statusLabel'"), false)
  assert.equal(importRunSource.includes("accessorKey: 'createdAt'"), false)
  assert.equal(importRunSource.includes("accessorKey: 'entityLabel'"), false)
  assert.equal(importRunSource.includes("accessorKey: 'title'"), false)
  assert.equal(importRunSource.includes("accessorKey: 'recordId'"), false)
})

test('step 7 collapses the test import table into a spoiler above the final import table', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const stepSevenStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 7"')
  const stepSevenSource = importerWorkbenchSource.slice(stepSevenStart)

  assert.equal(importerWorkbenchSource.includes('const isStepSevenDryRunExpanded = ref(false)'), true)
  assert.equal(stepSevenSource.includes('Результат тестового импорта'), true)
  assert.equal(stepSevenSource.includes('isStepSevenDryRunExpanded'), true)
  assert.equal(stepSevenSource.includes('Таблица тестового импорта'), false)
})

test('step 1 places choose file button between file and template blocks', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const rightColumnStart = importerWorkbenchSource.indexOf('<!-- Right column: dropzone + template -->')
  const rightColumnEnd = importerWorkbenchSource.indexOf('<!-- HR подэкран -->', rightColumnStart)
  const rightColumnSource = importerWorkbenchSource.slice(rightColumnStart, rightColumnEnd)

  const fileBlockIndex = rightColumnSource.indexOf('<!-- Dropzone -->')
  const chooseFileButtonIndex = rightColumnSource.indexOf('Выбрать файл')
  const templateBlockIndex = rightColumnSource.indexOf('<!-- Template download -->')

  assert.notEqual(fileBlockIndex, -1)
  assert.notEqual(chooseFileButtonIndex, -1)
  assert.notEqual(templateBlockIndex, -1)
  assert.equal(fileBlockIndex < chooseFileButtonIndex, true)
  assert.equal(chooseFileButtonIndex < templateBlockIndex, true)
})

test('history panel no longer renders collapsed-state helper text', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(
    importerWorkbenchSource.includes('По умолчанию показываются только последние 2 запуска, чтобы панель не вытягивала экран.'),
    false,
  )
})

test('step 1 upload action is no longer blocked by an unrelated running session from history', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('&& !isBlockedByActiveSession.value'), false)
})

test('history panel can reopen a saved import session in the wizard', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const restoringHistorySessionId = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes('async function resumeHistorySession(sessionId: string)'), true)
  assert.equal(importerWorkbenchSource.includes('const response = await apiStore.getImportSession(sessionId)'), true)
  assert.equal(importerWorkbenchSource.includes('await refreshMapping()'), true)
  assert.equal(importerWorkbenchSource.includes('row.actionLabel'), true)
  assert.equal(importerWorkbenchSource.includes('@click="resumeHistorySession(row.key)"'), true)
})

test('history panel shows explicit load error instead of silently rendering empty state', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const historyLoadError = ref('')"), true)
  assert.equal(importerWorkbenchSource.includes("historyLoadError.value = ''"), true)
  assert.equal(importerWorkbenchSource.includes("historyLoadError.value = error instanceof Error ? error.message : 'Не удалось загрузить историю импортов.'"), true)
  assert.equal(importerWorkbenchSource.includes('Не удалось загрузить историю'), true)
  assert.equal(importerWorkbenchSource.includes("v-if=\"historyLoadError && historyRows.length === 0\""), true)
  assert.equal(importerWorkbenchSource.includes('// silently ignore history load failures'), false)
})

test('sidebar no longer includes context fact label for task scenarios', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("facts.unshift({ label: 'Контекст'"), false)
  assert.equal(importerWorkbenchSource.includes('>Контекст</div>'), false)
})

test('step 1 no longer renders task-only sidebar minimum or family badge', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("facts.splice(1, 0, { label: 'Минимум'"), false)
  assert.equal(importerWorkbenchSource.includes('v-if="currentScenarioSummary.family === \'task\'"'), false)
})

test('importer workbench renders explicit no-access state for users without importer role', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("const hasNoImporterAccess = computed(() =>"), true)
  assert.equal(importerWorkbenchSource.includes('Нет назначенной роли для работы с импортом.'), true)
  assert.equal(importerWorkbenchSource.includes('Обратитесь к администратору портала'), true)
})

test('importer workbench renders dedup warning banner on preview and result steps', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('buildDedupWeakeningNotice'), true)
  assert.equal(importerWorkbenchSource.includes('dryRunDedupWeakeningNotice.hasWarnings'), true)
  assert.equal(importerWorkbenchSource.includes('importRunDedupWeakeningNotice.hasWarnings'), true)
  assert.equal(importerWorkbenchSource.includes('Неполный поиск дублей'), true)
  assert.equal(importerWorkbenchSource.includes('Поля не заполнены'), true)
  assert.equal(importerWorkbenchSource.includes('Строки риска'), true)
})

test('importer workbench can switch to dedup risk rows from banner', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const activeDryRunDedupRiskOnly = ref(false)'), true)
  assert.equal(importerWorkbenchSource.includes('toggleDryRunDedupRiskOnly'), true)
  assert.equal(importerWorkbenchSource.includes("selectImportRunFilter(activeImportRunFilter === 'dedup_risk' ? 'all' : 'dedup_risk')"), true)
  assert.equal(importerWorkbenchSource.includes('Показать только строки риска'), true)
  assert.equal(importerWorkbenchSource.includes('Сбросить фильтр'), true)
})

test('mapping step renders alias-rules and preflight sections', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Правила сопоставления'), true)
  assert.equal(importerWorkbenchSource.includes('Запомнить правило'), true)
  assert.equal(importerWorkbenchSource.includes('Проверка перед запуском'), true)
  assert.equal(importerWorkbenchSource.includes('saveImportAliasRule'), true)
})

test('mapping step describes new preflight blockers and blocks import button on them', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("code === 'field_values_unmapped'"), true)
  assert.equal(importerWorkbenchSource.includes("code === 'field_options_unavailable'"), true)
  assert.equal(importerWorkbenchSource.includes("code === 'crm_activity_communications_missing'"), true)
  assert.equal(importerWorkbenchSource.includes('не загрузились варианты Bitrix24'), true)
  assert.equal(importerWorkbenchSource.includes('не заполнено поле'), true)
  assert.equal(importerWorkbenchSource.includes('&& !hasBlockingPreflightIssues.value'), true)
})

test('importer workbench collapses long messages and resolves field names in preflight issues', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const expandedTextBlocks = ref<Record<string, boolean>>({})'), true)
  assert.equal(importerWorkbenchSource.includes('function resolveImporterFieldLabel(fieldId: string, fieldTitle = \'\')'), true)
  assert.equal(importerWorkbenchSource.includes('function buildPreflightIssueMeta(issue: Record<string, any>)'), true)
  assert.equal(importerWorkbenchSource.includes('function toggleTextBlock(key: string)'), true)
  assert.equal(importerWorkbenchSource.includes('buildPreflightIssueMeta(issue)'), true)
  assert.equal(importerWorkbenchSource.includes('Показать полностью'), true)
  assert.equal(importerWorkbenchSource.includes('Скрыть'), true)
})

test('dedup step can be skipped without enabling duplicate checks', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('async function skipDedupStep()'), true)
  assert.equal(importerWorkbenchSource.includes("dedupStrategy.value = 'create'"), true)
  assert.equal(importerWorkbenchSource.includes("dedupFields.value = []"), true)
  assert.equal(importerWorkbenchSource.includes("currentStep.value = 6"), true)
  assert.equal(importerWorkbenchSource.includes('async function executeValidation({'), true)
  assert.equal(importerWorkbenchSource.includes('persistDedup = true'), true)
  assert.equal(importerWorkbenchSource.includes("busyState = 'validation'"), true)
  assert.equal(importerWorkbenchSource.includes("await executeValidation({ persistDedup: false, resetStatus: false, busyState: 'dedup-skip' })"), false)
  assert.equal(importerWorkbenchSource.includes('label="Пропустить шаг"'), true)
})

test('skip dedup step switches to create strategy and starts duplicate-check flow immediately', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const skippedDedupStep = ref(false)'), true)
  assert.equal(importerWorkbenchSource.includes('skippedDedupStep.value = true'), true)
  assert.equal(importerWorkbenchSource.includes("dedupStrategy.value = 'create'"), true)
  assert.equal(importerWorkbenchSource.includes("await runDedupCheck({ skippedDedup: true })"), true)
})

test('real import requires a completed full test import result', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(
    importerWorkbenchSource.includes("&& Boolean(validationData.value)"),
    true,
  )
  assert.equal(
    importerWorkbenchSource.includes('&& Boolean(preimportScanData.value)'),
    true,
  )
})

test('skip dedup step delegates navigation to duplicate-check execution instead of forcing step 6 early', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  const skipFunctionStart = importerWorkbenchSource.indexOf('async function skipDedupStep() {')
  const saveTemplateStart = importerWorkbenchSource.indexOf('async function saveTemplate() {')
  const skipFunctionSource = importerWorkbenchSource.slice(skipFunctionStart, saveTemplateStart)

  assert.equal(skipFunctionSource.includes("await runDedupCheck({ skippedDedup: true })"), true)
  assert.equal(skipFunctionSource.includes('currentStep.value = 6'), false)
})

test('skip dedup step validates lazily before explicit dry run and import execution', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('async function ensureValidationBeforeExecution()'), true)
  assert.equal(importerWorkbenchSource.includes("busyState: 'validation'"), true)
  assert.equal(importerWorkbenchSource.includes('const validationResult = await ensureValidationBeforeExecution()'), true)
  assert.equal(importerWorkbenchSource.includes('if (!validationResult && !validationData.value) {'), true)
})

test('validation step empty state points to test import after checks pass', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('empty="Ошибок не найдено. Можно запускать импорт."'), false)
  assert.equal(importerWorkbenchSource.includes('empty="Ошибок не найдено. Можно запускать тестовый импорт."'), true)
})

test('validation and execution persist pending dedup changes automatically', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const hasPendingDedupChanges = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('normalizeDedupPayloadForCompare(currentDedupSettingsPayload.value)'), true)
  assert.equal(importerWorkbenchSource.includes('async function persistDedupSettingsIfNeeded()'), true)
  assert.equal(importerWorkbenchSource.includes('await persistDedupSettingsIfNeeded()'), true)
})

test('preview step renders row limit hint before validation starts', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const previewRowLimitExceeded = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('const previewRowLimitError = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('Лимит строк на импорт'), true)
  assert.equal(importerWorkbenchSource.includes('preview?.max_import_rows'), true)
  assert.equal(importerWorkbenchSource.includes('!previewRowLimitExceeded.value'), true)
})

test('test import results render 20 rows per page with compact bottom pagination', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const DRY_RUN_RESULTS_PAGE_SIZE = 20'), true)
  assert.equal(importerWorkbenchSource.includes('const dryRunPage = ref(1)'), true)
  assert.equal(importerWorkbenchSource.includes('const dryRunPageCount = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('const paginatedDryRunRows = computed<DryRunRow[]>(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('function buildVisibleDryRunPageItems()'), true)
  assert.equal(importerWorkbenchSource.includes('Показаны строки'), true)
  assert.equal(importerWorkbenchSource.includes('Страница {{ dryRunPage }} из {{ dryRunPageCount }}'), true)
  assert.equal(importerWorkbenchSource.includes(':data="paginatedDryRunRows"'), true)
  assert.equal(importerWorkbenchSource.includes("pageItem === 'start-ellipsis' || pageItem === 'end-ellipsis'"), true)
})

test('run import requires explicit confirmation before mass creating crm records', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('async function confirmMassCreateImport()'), true)
  assert.equal(importerWorkbenchSource.includes("dedupStrategy.value !== 'create'"), true)
  assert.equal(importerWorkbenchSource.includes("window.confirm(confirmMessage)"), true)
  assert.equal(importerWorkbenchSource.includes('Будет создано'), true)
  assert.equal(importerWorkbenchSource.includes('Существующие записи не будут обновлены'), true)
})

test('long background import keeps running status instead of fake timeout error', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const importerUiSource = readFileSync(
    new URL('../app/utils/importer-ui.js', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const maxAttempts = 600'), true)
  assert.equal(
    importerWorkbenchSource.includes('Импорт продолжает выполняться в фоне.')
      || importerUiSource.includes('Импорт продолжает выполняться в фоне.'),
    true,
  )
  assert.equal(importerWorkbenchSource.includes('Фоновый импорт не завершился за ожидаемое время.'), false)
})

test('step 6 uses one full test run and does not show sample-preview wording', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const sessionJobMode = computed(() => String(session.value?.summary?.job?.mode || \'\').trim())'), true)
  assert.equal(importerWorkbenchSource.includes('async function waitForDryRunExecutionResult(sessionId: string)'), true)
  assert.equal(importerWorkbenchSource.includes('async function resolveDryRunExecutionResult('), true)
  assert.equal(importerWorkbenchSource.includes("jobMode === 'preimport_scan'"), true)
  assert.equal(importerWorkbenchSource.includes("['run', 'retry'].includes(String(busyAction.value || '').trim())"), true)
  assert.equal(importerWorkbenchSource.includes('const showsDedupProgress = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('Тестовый импорт по выборке'), false)
  assert.equal(importerWorkbenchSource.includes('Выборка и запуск'), false)
  assert.equal(importerWorkbenchSource.includes('Полный поиск дублей перед импортом'), false)
  assert.equal(importerWorkbenchSource.includes('Тестовый импорт проверяет весь файл'), true)
})

test('waitForDryRunExecutionResult avoids duplicate jobMode declarations in the same scope', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const functionStart = importerWorkbenchSource.indexOf('async function waitForDryRunExecutionResult(sessionId: string)')
  const functionEnd = importerWorkbenchSource.indexOf('async function waitForImportExecutionResult(sessionId: string)')
  const functionSource = importerWorkbenchSource.slice(functionStart, functionEnd)

  assert.equal((functionSource.match(/const jobMode =/g) || []).length, 2)
})

test('waitForImportExecutionResult handles cancelled sessions without requiring history reopen', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const functionStart = importerWorkbenchSource.indexOf('async function waitForImportExecutionResult(sessionId: string)')
  const functionEnd = importerWorkbenchSource.indexOf('async function resolveDryRunExecutionResult(', functionStart)
  const functionSource = importerWorkbenchSource.slice(functionStart, functionEnd)

  assert.equal(functionSource.includes("if (currentStatus === 'cancelled')"), true)
  assert.equal(functionSource.includes('buildCancelledImportRunSummary(snapshot)'), true)
})

test('cancelActiveImport refreshes stale session state instead of surfacing raw 400 errors', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const functionStart = importerWorkbenchSource.indexOf('async function cancelActiveImport()')
  const functionEnd = importerWorkbenchSource.indexOf('async function downloadImportReport()', functionStart)
  const functionSource = importerWorkbenchSource.slice(functionStart, functionEnd)

  assert.equal(functionSource.includes('await apiStore.getImportSession(String(session.value.id))'), true)
  assert.equal(functionSource.includes("Импорт уже завершён или остановлен. Остановка больше не требуется."), true)
})

test('step 5 only configures duplicate settings and step 6 owns the single full test run', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const stepFiveStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 5"')
  const stepSixStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 6"')
  const stepFiveSource = importerWorkbenchSource.slice(stepFiveStart, stepSixStart)

  assert.equal(importerWorkbenchSource.includes('async function runSamplePreview('), true)
  assert.equal(importerWorkbenchSource.includes('async function runPreimportScanBeforeImport('), false)
  assert.equal(importerWorkbenchSource.includes("mode: 'preimport_scan'"), true)
  assert.equal(stepFiveSource.includes('label="Проверить дубли"'), false)
  assert.equal(stepFiveSource.includes('@click="runPreimportScanBeforeImport"'), false)
  assert.equal(stepFiveSource.includes('label="Сохранить правила дублей"'), true)
})

test('linked imports render separate duplicate rule editors for each entity on step 5', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('buildLinkedImportEntityGroups'), true)
  assert.equal(importerWorkbenchSource.includes('linkedDedupSettings'), true)
  assert.equal(importerWorkbenchSource.includes('Правила для сущности'), true)
})

test('saving duplicate rules on step 5 moves the wizard to step 6', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const functionStart = importerWorkbenchSource.indexOf('async function saveDedupSettings() {')
  const functionEnd = importerWorkbenchSource.indexOf('async function persistDedupSettings() {')
  const functionSource = importerWorkbenchSource.slice(functionStart, functionEnd)

  assert.equal(functionSource.includes('await persistDedupSettings()'), true)
  assert.equal(functionSource.includes('currentStep.value = 6'), true)
})

test('step 6 keeps full test results and duplicate decisions in one place', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const stepFiveStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 5"')
  const stepSixStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 6"')
  const stepSevenStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 7"')
  const stepFiveSource = importerWorkbenchSource.slice(stepFiveStart, stepSixStart)
  const stepSixSource = importerWorkbenchSource.slice(stepSixStart, stepSevenStart)

  assert.equal(stepFiveSource.includes("importExecutionStage === 'duplicate-decisions'"), false)
  assert.equal(stepSixSource.includes('label="Тестовый импорт"'), true)
  assert.equal(stepSixSource.includes('@click="runSamplePreview"'), true)
  assert.equal(stepSixSource.includes("importExecutionStage === 'duplicate-decisions'"), true)
  assert.equal(stepSixSource.includes("requiresPerRowDedupDecision && dryRunData && pendingDecisionRows.length"), true)
  assert.equal(importerWorkbenchSource.includes('const stepSixFlowCards = computed(() => (['), false)
  assert.equal(stepSixSource.includes('v-for="card in stepSixFlowCards"'), false)
})

test('step 6 explains that the test import checks the full file and waits for manual final launch', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('Это пример по первым'), false)
  assert.equal(importerWorkbenchSource.includes('Пропущено в примере'), false)
  assert.equal(importerWorkbenchSource.includes('Полный поиск дублей будет выполнен автоматически перед реальным импортом.'), false)
  assert.equal(importerWorkbenchSource.includes('async function resumeImportAfterDuplicateDecisions()'), false)
  assert.equal(importerWorkbenchSource.includes("watch(hasUnresolvedPendingDedupDecisions, async (nextValue, previousValue) => {"), false)
  assert.equal(importerWorkbenchSource.includes('После проверки можно выбрать решения по дублям и отдельно запустить реальный импорт.'), true)
  assert.equal(importerWorkbenchSource.includes('Продолжаем импорт автоматически.'), false)
  assert.equal(importerWorkbenchSource.includes('Теперь можно запускать импорт.'), true)
})

test('duplicate decisions stay on step 6 and reuse the main import action', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const stepFiveStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 5"')
  const stepSixStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 6"')
  const stepSevenStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 7"')
  const stepFiveSource = importerWorkbenchSource.slice(stepFiveStart, stepSixStart)
  const stepSixSource = importerWorkbenchSource.slice(stepSixStart, stepSevenStart)

  assert.equal(stepFiveSource.includes('Найдены дубли — выберите действие'), false)
  assert.equal(importerWorkbenchSource.includes('async function handleRunImportAction()'), false)
  assert.equal(stepSixSource.includes('label="Запустить импорт"'), true)
  assert.equal(stepSixSource.includes('@click="runImport"'), true)
  assert.equal(stepSixSource.includes('Продолжить импорт сейчас'), false)
})

test('test import progress and duplicate decisions use full file totals', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const executionProgressTotalRows = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('const executionProgressProcessedRows = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('const executionProgressPercent = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('dryRunData.value?.full_total_rows'), true)
  assert.equal(importerWorkbenchSource.includes("строк файла"), true)
})

test('test import and real import expose explicit cancel controls without a separate scan action', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const stepSixStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 6"')
  const stepSevenStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 7"')
  const stepSixSource = importerWorkbenchSource.slice(stepSixStart, stepSevenStart)

  assert.equal(importerWorkbenchSource.includes("['run', 'retry', 'sample-preview'].includes(String(busyAction.value || '').trim())"), true)
  assert.equal(stepSixSource.includes('label="Остановить тестовый импорт"'), true)
  assert.equal(stepSixSource.includes('label="Остановить поиск дублей"'), false)
})

test('linked duplicate decision table uses russian field labels and bulk actions', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const stepSixStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 6"')
  const stepSevenStart = importerWorkbenchSource.indexOf('<section v-if="currentStep === 7"')
  const stepSixSource = importerWorkbenchSource.slice(stepSixStart, stepSevenStart)

  assert.equal(importerWorkbenchSource.includes('function getPendingDecisionMatchFieldsLabel('), true)
  assert.equal(importerWorkbenchSource.includes('function applyBulkPerRowDedupDecision('), true)
  assert.equal(stepSixSource.includes('getPendingDecisionMatchFieldsLabel(row)'), true)
  assert.equal(stepSixSource.includes('getPendingDecisionMatchFieldsLabel(row, entityId)'), true)
  assert.equal(stepSixSource.includes('row.duplicate_match_fields.join(\', \')'), false)
  assert.equal(stepSixSource.includes('row.linked[entityId].duplicate_match_fields.map((fieldId) =>'), false)
  assert.equal(stepSixSource.includes('Всё создать'), true)
  assert.equal(stepSixSource.includes('Всё обновить'), true)
  assert.equal(stepSixSource.includes('Всё пропустить'), true)
})

test('real import progress is split into scan new-record and duplicate phases', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  assert.equal(importerWorkbenchSource.includes('const importExecutionStage = ref<'), true)
  assert.equal(importerWorkbenchSource.includes('Полный поиск дублей'), false)
  assert.equal(importerWorkbenchSource.includes('Импорт новых записей'), true)
  assert.equal(importerWorkbenchSource.includes('Обработка дублей'), true)
})

test('importer workbench enables duplicate step for smart processes', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("'crm_activity', 'crm_note', 'smart_process',"), false)
  assert.equal(importerWorkbenchSource.includes("'crm_activity', 'crm_note',"), true)
})

test('importer workbench disables duplicate step configuration for users and departments', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes("'crm_activity', 'crm_note', 'department', 'user',"), true)
  assert.equal(importerWorkbenchSource.includes('Дедупликация не применяется'), true)
  assert.equal(importerWorkbenchSource.includes('поиск дублей не поддерживается'), true)
})

test('saving mapping for users and departments advances to the informational duplicate step', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )
  const functionStart = importerWorkbenchSource.indexOf('async function saveMapping() {')
  const functionEnd = importerWorkbenchSource.indexOf('async function saveDedupSettings() {')
  const functionSource = importerWorkbenchSource.slice(functionStart, functionEnd)

  assert.equal(functionSource.includes('if (!isDedupApplicable.value) {'), true)
  assert.equal(functionSource.includes('currentStep.value = 5'), true)
})

test('validation remains available in simple mode after session mapping is saved', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const sessionSavedMapping = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('const mappingSavedCount = computed(() => ('), true)
  assert.equal(importerWorkbenchSource.includes('sessionSavedMapping.value && typeof sessionSavedMapping.value === \'object\''), true)
})

test('final import results render 20 rows per page with compact bottom pagination', () => {
  const importerWorkbenchSource = readFileSync(
    new URL('../app/components/ImporterWorkbench.vue', import.meta.url),
    'utf8',
  )

  assert.equal(importerWorkbenchSource.includes('const importRunPage = ref(1)'), true)
  assert.equal(importerWorkbenchSource.includes('const importRunPageCount = computed(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('const paginatedImportRunRows = computed<ImportRunRow[]>(() =>'), true)
  assert.equal(importerWorkbenchSource.includes('function buildVisibleImportRunPageItems()'), true)
  assert.equal(importerWorkbenchSource.includes('Страница {{ importRunPage }} из {{ importRunPageCount }}'), true)
  assert.equal(importerWorkbenchSource.includes(':data="paginatedImportRunRows"'), true)
})

test('importer ui uses module translator for run tables and notices when set', () => {
  setImporterUiTranslator((key, params = null) => {
    const map = {
      'importer.run_status.import_created': 'Created (en)',
      'importer.run_completion.done_ok': 'Import complete (en)',
      'importer.dedup_warning.match_label': `Match (en): ${params?.fields || ''}`,
      'importer.field_labels.PHONE': 'Phone (en)',
    }
    return map[key] || key
  })

  try {
    const rows = buildImportRunRows({
      results: [
        { row_number: 1, status: 'created', duplicate_match_fields: ['PHONE'] },
      ],
    })
    assert.equal(rows[0].statusLabel, 'Created (en)')
    assert.equal(rows[0].details.includes('Match (en): Phone (en)'), true)

    const notice = buildImportRunCompletionNotice({ status: 'completed', failed_rows: 0 })
    assert.equal(notice.message, 'Import complete (en)')
  } finally {
    setImporterUiTranslator(null)
  }

  const fallbackNotice = buildImportRunCompletionNotice({ status: 'completed', failed_rows: 0 })
  assert.equal(fallbackNotice.message, 'Импорт завершен. Все строки обработаны.')
})

test('import mode, scenario, wizard, badge and filter labels use the module translator when set', () => {
  setImporterUiTranslator((key) => {
    const map = {
      'importer.modes.simple_label': 'Simple import (en)',
      'importer.modes.simple_desc': 'Simple desc (en)',
      'importer.modes.advanced_label': 'Advanced import (en)',
      'importer.families.crm_title': 'CRM entities (en)',
      'importer.entities.lead': 'Leads (en)',
      'importer.entities.contact_single': 'Contact (en)',
      'importer.wizard_next.prefix': 'Next: ',
      'importer.wizard_next.step3': 'Preview (en)',
      'importer.wizard_next.finish': 'Finish (en)',
      'importer.status_badge.idle': 'Awaiting start (en)',
      'importer.run_filters.all': 'All (en)',
    }
    return map[key] || key
  })

  try {
    assert.equal(getImportModeMeta('simple').label, 'Simple import (en)')
    assert.equal(getImportModeMeta('simple').description, 'Simple desc (en)')
    assert.equal(buildImportModeOptions()[1].label, 'Advanced import (en)')

    const sections = buildImportScenarioSections()
    const crmSection = sections.find((section) => section.id === 'crm')
    assert.equal(crmSection.title, 'CRM entities (en)')
    assert.equal(crmSection.items.find((item) => item.value === 'lead').label, 'Leads (en)')

    assert.equal(getWizardNextLabel(2), 'Next: Preview (en)')
    assert.equal(getWizardNextLabel(7), 'Finish (en)')

    assert.equal(buildMigrationStatusBadge({}).label, 'Awaiting start (en)')
    assert.equal(buildImportRunStatusFilters({ results: [] })[0].label, 'All (en)')

    const fileAttachOptions = buildFileAttachEntityOptions()
    assert.equal(fileAttachOptions.find((item) => item.value === 'crm_files_contact').label, 'Contact (en)')
  } finally {
    setImporterUiTranslator(null)
  }

  assert.equal(getImportModeMeta('simple').label, 'Простой импорт')
  assert.equal(getWizardNextLabel(2), 'Далее: Предпросмотр')
  assert.equal(buildMigrationStatusBadge({}).label, 'Ожидает запуска')
})
