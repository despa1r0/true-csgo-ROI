# Технологический стек

## Backend и данные

- Python 3.13
- FastAPI
- PostgreSQL 16
- Psycopg 3
- Pytest
- Docker Compose

Каталог разделён на базовые модели `skins`, продаваемые варианты `skin_variants` и связи `skin_collections`. Исходные записи CSGO-API сохраняются в JSONB. Для поиска по частичному названию используется PostgreSQL `pg_trgm`. Рыночные индексы и подробные снимки адаптеров хранятся в общих таблицах `marketplace_listings`, `marketplace_syncs` и `marketplace_variant_details` с разделением по полю `marketplace`.

Импорт запускается отдельным одноразовым Compose-сервисом `catalog-seed`. Он скачивает плоский список вариантов `skins_not_grouped.json` и сгруппированный `skins.json` с коллекциями, делает upsert и удаляет устаревшие записи. API стартует только после успешного импорта.

## Frontend

Production-frontend расположен в `frontend-react`:

- React 19 + TypeScript 5.9;
- Vite 7;
- React Router 7;
- TanStack Query 5;
- i18next/react-i18next;
- Radix UI Dialog;
- Apache ECharts 6;
- Motion;
- CSS Modules и CSS custom properties;
- Vitest, Testing Library, jsdom и MSW.

Маршрут `/` содержит каталог, сравнение и модальную аналитику; `/calculator` — ручной калькулятор профита. UI доступен на русском и английском. Серверное состояние кэшируется TanStack Query, а доступность функций площадок определяется динамическими capabilities из `/api/marketplaces`.

Графики показывают только реальные продажи за 24 часа, 7 дней, 14 дней или всю доступную выборку. White.Market не имеет публичной истории продаж, поэтому для него график не строится. Наклейки и charms доступны как самостоятельные предметы общего каталога; фильтры `has_stickers` и `has_charm` внутри лотов проверяют наличие attachments, но не их конкретное имя/ID.

Комиссии рассчитываются на backend. Пользователь может включать и выключать их учёт чекбоксами, однако не может менять server-owned ставки.

## Сборка и доставка

Корневой Dockerfile использует multi-stage build. Node 22 выполняет `npm ci` и `npm run build` в `frontend-react`, затем собранный `dist` копируется в Python 3.13 образ и раздаётся FastAPI. UI и API работают на одном origin.

Основной сценарий: ввод названия или выбор коллекции → выбор скина → выбор режима Raw/Smart/Enhanced/Quick flip, направления покупки/продажи и способов пополнения/вывода → сравнение цен и ROI на карточках FN/MW/FT/WW/BS → выбор площадки и модальный список её лотов → аналитика доступных площадок. Quick flip лениво загружает лучший bid; приватный Market.CSGO API защищён общим thread-safe limiter с безопасным потолком четыре запроса в секунду.

Подробнее: [`docs/FRONTEND.md`](docs/FRONTEND.md).
