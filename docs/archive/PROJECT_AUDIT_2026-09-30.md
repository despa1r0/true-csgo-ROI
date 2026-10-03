# Аудит и отчёт по проекту — 30 сентября 2026

> Исторический срез. Актуальная настройка SSH и расположение скриптов описаны
> в [DEPLOY.md](../DEPLOY.md); секрет `VPS_KNOWN_HOSTS` больше не требуется.

## Что сделано в этом рабочем срезе

- Удалены оставленные конфигурации OpenCode: `.opencode/`, `opencode.json` и
  `docs/OPENCODE.md`; удалены ссылки на них. В `AGENTS.md` сохранены только
  общие правила работы проекта без привязки к Opus/OpenRouter.
- Упрощены `.github/workflows/ci.yml` и `deploy.yml`: длинные команды вынесены
  в `scripts/ci/`, деплой теперь запускается после успешного CI push в `main`.
- Закрыта проблема доверия SSH host key: workflow использует обязательный секрет
  `VPS_KNOWN_HOSTS`, скрипт проверяет соответствие `VPS_HOST`/`VPS_PORT` через
  `ssh-keygen -F`, а `ssh` и `scp` требуют `StrictHostKeyChecking=yes`.
  Инструкция по независимой проверке fingerprint находится в `docs/DEPLOY.md`.
- Исправления CS.MONEY и UI: изолирована ошибка отдельного провайдера в сравнении,
  обработаны оборванные Wiki-ответы, retry Wiki отделён от шестичасовой паузы
  storefront; усилена проверка фазы и диапазона цены; свежие лоты получают
  приоритет над stale; ответ API различает источники и состояние вариантов.
  Цена и количество предложений Wiki проверяются на диапазон PostgreSQL `INTEGER`
  до записи в БД.
  Интерфейсные изменения включают происхождение цен и компонентную свежесть,
  аналитику summary-only варианта и отображение ошибок загрузки. Замечания
  независимого frontend-ревью исправлены: учитывается stale отдельного лота,
  цена/источник/превью выбираются согласованно, устаревшие метрики ликвидности
  скрываются. Выполнена повторная статическая проверка; полный frontend-прогон
  ограничен отсутствием зависимостей.
  Клиент перепроверяет 72-часовую свежесть Wiki Trade при отображении и по
  таймеру границы; эти котировки остаются отдельными от продаж, ликвидности и ROI.

## Оставшиеся ограничения и проблемы

### CS.MONEY и другие источники

Последнее записанное production-свидетельство относится к 21 сентября 2026:
storefront CS.MONEY вернул HTTP 403, а запрос Wiki GraphQL также был
заблокирован Cloudflare при внешней проверке. После этих наблюдений новый запрос
к production не выполнялся. Следовательно, доступность источников сегодня не
подтверждена, а реальные лоты CS.MONEY могут по-прежнему отсутствовать. Код не
обходит security challenge. Wiki Market summary, когда доступна, даёт только
минимум и число предложений без конкретного ID, float и attachments.

Оставшиеся вопросы отделены от исправленных дефектов. Указанные ниже
ограничения кода проверены статически; записи о production-доступности относятся
к предыдущим наблюдениям, а не к сегодняшнему запросу.

| Приоритет | Ограничение и свидетельство | Следующий шаг |
| --- | --- | --- |
| P0, внешний доступ | Storefront CS.MONEY и Wiki GraphQL дали 403 в последнем записанном production-наблюдении 21 сентября; новых запросов не было ([`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md)). | С разрешения владельца отдельно проверить доступ с VPS и официальный допустимый источник; challenge не обходить. |
| P1, живучесть | Storefront breaker остаётся в памяти процесса (`backend/app/csmoney_worker.py`, `run`), поэтому рестарт сбрасывает паузу. | Сохранить срок блокировки в PostgreSQL и проверить переходы на тестовой БД. |
| P1, конкуренция | Задания берутся через `claim_refresh_job`, а `complete_refresh_job` удаляет строку только по `variant_id` (`backend/app/csmoney_data.py`); lease не имеет ownership/fencing token. | Добавить token/generation и условное завершение до запуска нескольких collector-ов. |
| P1, схема | `ensure_schema` вызывается при старте воркера (`backend/app/csmoney_worker.py`); версионированных миграций Alembic нет. | Спланировать миграции, совместимость и откат перед изменением production-схемы; текущая задача миграций не выполняла. |
| P1, историческое наблюдение | CSFloat ранее ограничивал запросы конкретных лотов, хотя индексная цена была доступна отдельно ([`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md)); повторного provider-запроса не было. | Проверить авторизованный запрос к лотам отдельно от индекса после согласования доступа/лимитов. |
| P1, наблюдаемость | Health check проверяет процесс, но не свежесть рыночных данных; общий diagnostics статус провайдеров пока не унифицирован (`docs/KNOWN_ISSUES.md`). | Показывать возраст данных и последний исход запроса для каждого источника независимо от HTTP 200 приложения. |

### CI и поставка

Деплой требует добавления нового секрета `VPS_KNOWN_HOSTS` и независимой проверки
host-key fingerprint владельцем инфраструктуры. Без секрета деплой намеренно
завершится ошибкой до SSH-соединения. Автоматическая проверка удалённого VPS,
публикация и запуск production в этой задаче не выполнялись. Кэшированный
`actionlint` доступен локально и прошёл проверку workflow; системный ShellCheck
отсутствует, поэтому встроенная в `actionlint` проверка shell была отключена.
Синтаксис Bash и offline subprocess сценарии проверены локально.

## Проверки

- Backend: `PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests -q --tb=short` —
  218 passed до объединения веток; после объединения с актуальной `origin/develop` — 230 passed.
- SSH helper: `PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests/test_deploy_ssh.py -q --tb=short` — 3 passed.
- `bash -n scripts/ci/deploy-ssh.sh`, `scripts/ci/validate-compose.sh` и `git diff --check` прошли.
- JSON RU/EN и новые ключи переводов проверены; отсутствие `.opencode/`, `opencode.json` и `docs/OPENCODE.md` подтверждено.
- Кэшированный `actionlint` 1.7.12: `/home/cqa/.codex/skills/github-actions-validator/scripts/.tools/actionlint -shellcheck= .github/workflows/ci.yml .github/workflows/deploy.yml` — exit 0. Флаг `-shellcheck=` отключает интеграцию ShellCheck; отдельный ShellCheck отсутствует.
- Frontend `npm test` / `npm run build` не запускались: на хосте нет Node и
  `node_modules`; образ `node:22-alpine` кэширован, но установки зависимостей
  не было и разрешения на неё не получено.
- Дополнительно выполнены 15 offline assertions над извлечёнными из текущих
  `ListingDialog.tsx` и `quoteSource.tsx` чистыми функциями: stale отдельного лота,
  выбор цены/источника/превью, независимая свежесть bid и ликвидности, граница
  Wiki Trade в 72 часа. Использован уже имевшийся `node:22-alpine` с
  `--network=none --pull=never`; пакеты не устанавливались. Команда:
  `docker run --pull=never --rm --network=none --read-only --mount type=bind,src=/tmp/truecsroi-ui-check-a150a7a3,dst=/checks,readonly node:22-alpine node --experimental-strip-types /checks/checks.mts`.
  Это проверка поведения helper-функций, не TypeScript typecheck, Vitest или
  рендеринг компонентов. Регрессионные случаи также добавлены в
  `frontend-react/src/features/catalog/ListingDialog.test.ts` для полного CI.
- Provider API, production VPS, реальная БД и deployment не проверялись.

Историческая база CS.MONEY-аудита и статические наблюдения сохранены в
[`CSMONEY_REVIEW.md`](CSMONEY_REVIEW.md); production-свидетельства — в
[`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md). Эти документы содержат состояние на даты
проверок и не подтверждают текущую доступность сторонних сервисов.
