# План поэтапного рефакторинга

Цель — уменьшать связанность и эксплуатационные риски небольшими совместимыми
изменениями. После каждого этапа проходят релевантные backend/frontend-тесты,
проверка сборки и обновление документации. Формулы прибыли и правила комиссий
меняются только отдельной согласованной задачей.

## Этапы и критерии завершения

| Этап | Результат | Проверка завершения |
| --- | --- | --- |
| 0. Инвентаризация | Зафиксированы тесты, CI/Docker, ограничения и этот план | Известен baseline; рабочие изменения пользователя сохранены |
| 1. Единый frontend | Удалён legacy fallback; production раздаёт только React bundle; dev использует Vite | SPA routes работают, неизвестные `/api/*` дают 404, отсутствие production bundle останавливает запуск |
| 2. Свежесть кэша | Независимые timestamps/status для listings, sales и buy orders | Неудачное частичное обновление не делает старые данные свежими; есть тест двух последовательных запросов |
| 3. Границы backend | Routers, services, repositories и adapters выделяются по одному provider | URL и response-контракты сохранены; тесты проходят после каждого переноса |
| 4. Alembic и pool | Версионированная схема и ограниченный PostgreSQL pool | Чистая БД и существующая production-схема безопасно мигрируют одной командой |
| 5. Provider resilience | Единые статусы, diagnostics/readiness, coalescing/rate limits и устойчивый circuit breaker | UI честно различает fresh/stale/blocked/unavailable; деградация одного provider наблюдаема |
| 6. Поставка | Зафиксированные зависимости, lint/types, integration/contract/smoke tests и меньший initial bundle | CI проверяет API, PostgreSQL и Compose; frontend build не имеет случайных артефактов |

Текущий статус на 21 сентября 2026 года: этапы 0–2 завершены. Legacy frontend
удалён, production и development режимы разделены, а detail-кэш CSFloat и CSGO
Market получил независимую свежесть `listings`, `sales` и `buy_orders`.
Regression-тесты подтверждают повторное обновление упавшего компонента внутри
TTL.

Этап 3 выполняется. HTTP endpoints CSFloat, CSGO Market, White.Market и CS.MONEY
перенесены из `main.py` в отдельные FastAPI routers. Публичные URL,
OpenAPI-параметры и прежние коды ошибок закреплены контрактными тестами после
каждого переноса. `main.py` сокращён до точки сборки и общих маршрутов. Data-layer
провайдеров пока намеренно не перемещался: следующий подэтап — выделить service
и repository boundaries по одному провайдеру, начиная с CSFloat.

Выполнен cleanup-срез этапа 6: удалены неиспользуемые React-компоненты,
устаревшие Python-модель и compatibility alias, test-only Python-зависимости
отделены от production requirements. Из frontend удалены неиспользуемые
Testing Library/MSW и декоративная Motion-зависимость; чистая установка содержит
168 npm packages, `npm audit` сообщает 0 известных уязвимостей. Production build
трансформирует 776 модулей вместо 1180, а бывший Motion chunk уменьшен с 127,83
до 5,04 kB. CS.MONEY provider и его внешняя блокировка этим срезом не изменялись.

## Основные риски

- частичные ответы providers могут смешивать данные разной свежести;
- миграция существующей PostgreSQL-схемы требует baseline/stamp без повторного
  создания таблиц;
- перенос маршрутов способен незаметно изменить OpenAPI и HTTP-коды;
- process-local rate limits и circuit breakers не работают между репликами;
- CS.MONEY/Cloudflare остаётся внешним ограничением и не обходится кодом проекта;
- лениво загружаемый ECharts Canvas renderer остаётся крупным chunk размером
  531,07 kB (180,45 kB gzip); его замена требует отдельного UI-решения.

## Порядок миграций

1. Зафиксировать текущую схему как начальную Alembic revision без удаления
   `ensure_schema`.
2. На копии существующей БД сравнить фактическую схему, выполнить безопасный
   `stamp` baseline и затем `upgrade head`.
3. На чистой БД проверить создание схемы миграциями и запуск seed/API.
4. Добавить явную команду migrate и вызвать её в Docker deployment до API.
5. Удалять `ensure_schema` только после подтверждённого production rollout и
   документированного rollback/backup процесса.

## Оставшиеся подэтапы

1. Завершить этап 3: по одному провайдеру отделить orchestration/services от
   доступа к PostgreSQL и внешних API, не меняя response-контракты.
2. Выполнить этап 4: добавить Alembic baseline, безопасный upgrade существующей
   схемы и ограниченный pool соединений.
3. Выполнить этап 5: унифицировать diagnostics/readiness, статусы деградации,
   request coalescing, rate limits и circuit breaker для всех провайдеров.
4. Завершить этап 6: зафиксировать Python-зависимости, расширить CI
   интеграционными и smoke-тестами и отдельно решить судьбу крупного ECharts
   renderer. Очистка frontend-зависимостей и измерение bundle уже выполнены.
5. Проверить production Docker image после запуска Docker Desktop: локально
   Compose-конфигурация проверена, но daemon был недоступен для image build.
