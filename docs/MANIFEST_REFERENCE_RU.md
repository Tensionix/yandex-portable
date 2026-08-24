# Manifest Reference

`config/tool_manifest.yaml` описывает шаблонные операции для GUI.

Минимальная операция:

```yaml
operations:
  - id: validate_input
    title: "Validate input"
    title_ru: "Проверить input"
    description: "Check input and print inventory."
    description_ru: "Проверить input и вывести инвентаризацию."
    tooltip: "Runs a local inventory check without changing files."
    tooltip_ru: "Запускает локальную проверку без изменения файлов."
    service: "system_core.services.sample_service:validate_input"
    kind: "safe"
```

Поля:

- `id`: стабильный идентификатор.
- `title`: короткая EN-надпись для кнопки.
- `title_ru`: короткая RU-надпись для кнопки.
- `description`: пояснение справа от кнопки.
- `description_ru`: русское пояснение.
- `tooltip`: короткая hover-подсказка. Если не задана, GUI использует `description`.
- `tooltip_ru`: русская hover-подсказка. Если не задана, GUI использует `description_ru`.
- `service`: Python callable в формате `module:function`.
- `kind`: `safe` или `dangerous`.

Правила:

- `title/title_ru` должны быть короткими и помещаться в одну строку.
- Длинный смысл переносите в `description`.
- В `tooltip/tooltip_ru` держите короткие ограничения, последствия или неочевидные условия запуска.
- Dangerous operations требуют подтверждения. GUI показывает не только общий вопрос, но и плашку последствий: диски/сеть/WSL/admin/cleanup распознаются по `id`, `service`, названию и описанию операции.
- Для реальных проектов без service layer допустимо адаптировать GUI под subprocess-вызов существующего CLI.

## Вложенные Меню

Для больших CLI-проектов используйте `operation_groups`. Дерево может иметь несколько уровней: например `лаунчер -> формат -> профиль -> запуск`.

```yaml
operation_groups:
  - id: convert
    title: "Convert"
    title_ru: "Конвертация"
    tooltip_ru: "Выберите формат и профиль конвертации."
    children:
      - id: office
        title: "Office"
        title_ru: "Office"
        fields:
          - id: input_formats
            type: "checkboxes"
            label: "Input formats"
            label_ru: "Форматы input"
            default: []
            min_selected: 1
            options:
              - value: "docx"
                label: "DOCX"
              - value: "xlsx"
                label: "XLSX"
              - value: "pptx"
                label: "PPTX"
        children:
          - id: run_convert
            title: "Run"
            title_ru: "Запуск"
            service: "system_core.services.sample_service:run_sample_job"
```

Если задан `operation_groups`, видимый список команд строится из дерева. Важные плоские `operations` нужно продублировать в дереве.

## Fields

`fields` показываются на финальном экране команды, наследуются дочерними узлами и передаются в `context.operation.parameters`. Кнопка запуска находится в верхней строке команды справа от названия, а `Назад` - слева.

Порядок `fields` лучше задавать по смыслу пользовательского решения, а не по порядку CLI-аргументов. Ставьте связанные поля рядом: ключ с моделью, формат с профилем, источник с режимом. Редкие числовые/ручные параметры можно пометить `advanced: true` или вынести ниже через локальные правила рендера.

## Логические Секции Полей

Когда параметров становится много, не оставляйте их одной простынёй. Поля можно явно собрать в блоки:

```yaml
fields:
  - id: source_url
    type: "text"
    group: "source"
    label_ru: "Ссылка"

  - id: output_format
    type: "radio"
    group: "output"
    label_ru: "Формат результата"
```

Поддерживаются ключи:

- `group`
- `ui_group`
- `section`

Если `section` равен `advanced`, `expert` или `rare`, поле попадёт в `Дополнительно`. Если `section` содержит другое значение, оно используется как визуальная группа.

Типовые группы:

- `preset` - профили и быстрые пресеты;
- `source` - ссылки, входные файлы, папки, форматы входа;
- `format` - формат, контейнер, профиль качества;
- `output` - параметры результата, DPI, битрейт, экспорт;
- `encoding` - модель, движок, codec/encode-параметры;
- `options` - флажки поведения;
- `run` - dry-run, overwrite, test-first-file.

Если группа не задана, GUI попробует сгруппировать поле по `id` и `type`. Это запасной механизм. В реальном проекте лучше явно назвать группы в manifest: так экран остаётся логичным даже при переносе десятков параметров.

Команды в `children` должны быть связаны с объектом текущей формы. Если leaf меняет конкретный список, cache или файл, отражайте это в `title_ru/title`: `Ключ в избранное`, `Модель в избранное`, `Сделать инструкцию активной`, `Импортировать файл`. Не используйте безымянные `В избранное`, `Сохранить`, `Применить`, когда рядом несколько `fields` и непонятно, к чему относится действие.

## Подписи И Тултипы Полей

У поля две пары текстов, и они делят работу:

- `label` / `label_ru` - подпись у контрола. Коротко: 7-10 слов, часто одно-два.
- `hint` / `hint_ru` - строка под контролом. Тоже коротко, той же меркой.
- `tooltip` / `tooltip_ru` - что появляется при наведении. Здесь можно и нужно
  объяснять подробно: что произойдёт, чем грозит неверный выбор, что будет с
  профилем. Ограничения по длине нет.

Тултип поля берётся из `tooltip`, при его отсутствии - из `hint`, затем из
`label`. Поэтому длинное объяснение держите в `tooltip`, а не раздувайте `hint`:
иначе оно окажется прямо в окне и вытеснит собой всё остальное.

Поддерживаемые типы:

- `text`: строка, ссылка, путь или ручной параметр.
- `number`, `int`, `float`: числовой ввод.
- `select`: один вариант из списка `options`.
- `radio`: один вариант из списка `options`, когда вариантов мало и их полезно видеть сразу. В этих проектах рисуется рядом кнопок-переключателей, а не точками.
- `checkbox`, `bool`, `boolean`: один флажок, значение `true/false`. Рисуется карточкой в сетке блока.
- `checkboxes`: группа флажков, значение - список выбранных `value`. Рисуется рядом кнопок с заголовком блока и кнопками `Отметить блок` / `Снять блок`.
- `profile_buttons`, `preset_buttons`: набор кнопок, которые меняют значения других `fields`, но не запускают операцию.

Для `checkboxes` используйте:

- `default`: список выбранных значений по умолчанию. Для новых миграций держите `[]`, чтобы пользователь явно выбрал нужное.
- `min_selected`: минимальное количество выбранных пунктов.
- `options`: список вариантов с `value`, `label`, `label_ru`.

Для миграции CLI-проектов удобно делать так: GUI собирает список чекбоксов в `context.operation.parameters`, сервис превращает его в аргумент старого CLI, например `--extensions docx,pptx,xlsx`, и уже CLI фильтрует работу. По умолчанию чекбоксы лучше оставлять пустыми: обычно пользователь хочет обработать что-то конкретное.

## Динамические Options

Для `select`, `radio` и `checkboxes` можно не хранить список вариантов в YAML, а загрузить его из Python provider:

```yaml
fields:
  - id: selected_input_files
    type: "checkboxes"
    label: "Staged input files"
    label_ru: "Файлы в input"
    default: []
    options_source: "system_core.services.sample_service:input_file_options"
    cache_seconds: 20
```

`options_source` использует формат `module:function`. Provider может принимать `root` проекта или не принимать аргументов. Он должен вернуть список:

```python
[
    {"value": "example.docx", "label": "example.docx", "label_ru": "example.docx"},
]
```

GUI кэширует результат на `cache_seconds` секунд и показывает кнопку `Обновить список`. Если provider упал, GUI покажет ошибку как один вариант списка, а не уронит окно.

Для развитых LLM-проектов это заменяет старые ручные файлы со списками моделей. Не держите одновременно `options_source`/cache/favorites/smoke и статический `models.yaml` как равноправные источники. Manifest должен указывать динамический источник, а устойчивые значения вроде лимитов, prompts и env-настроек должны жить отдельно от model ids.

## Профили / Пресеты

`profile_buttons` удобны для типовых наборов галочек и настроек:

```yaml
fields:
  - id: sample_profiles
    type: "profile_buttons"
    label: "Quick presets"
    label_ru: "Быстрые профили"
    presets:
      - id: office
        label: "Office"
        label_ru: "Office"
        values:
          input_formats: ["docx", "pptx", "xlsx"]
          include_metadata: true
      - id: reset
        label: "Reset"
        label_ru: "Сброс"
        values:
          input_formats: []
          include_metadata: false
```

Пресет только меняет `field_values`; пользователь видит результат и сам нажимает `Запустить`.
