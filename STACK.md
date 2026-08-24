# Технологический стек

## Backend и данные

- Python 3.13
- FastAPI
- PostgreSQL 16
- Psycopg 3
- Pytest
- Docker Compose

Каталог разделён на базовые модели `skins`, продаваемые варианты `skin_variants` и связи `skin_collections`. Исходные записи CSGO-API сохраняются в JSONB. Для поиска по частичному названию используется PostgreSQL `pg_trgm`. Рыночные индексы и подробные снимки CSFloat/CSGO Market хранятся в общих таблицах `marketplace_listings`, `marketplace_syncs` и `marketplace_variant_details` с разделением по полю `marketplace`.

Импорт запускается отдельным одноразовым Compose-сервисом `catalog-seed`. Он скачивает плоский список вариантов `skins_not_grouped.json` и сгруппированный `skins.json` с коллекциями, делает upsert и удаляет устаревшие записи. API стартует только после успешного импорта.

## Frontend

Обычные HTML, CSS и JavaScript без React, TypeScript, Vite и шага сборки. FastAPI раздаёт файлы из `frontend/`, поэтому всё приложение доступно на одном адресе и не требует CORS-настройки в браузере.

Основной сценарий: ввод названия или выбор коллекции → выбор скина → сравнение минимальных цен и чистого ROI CSFloat/CSGO Market на карточках FN/MW/FT/WW/BS → модальный список отфильтрованных лотов CSFloat → аналитика выбранного лота. Подробные endpoints обеих площадок загружаются лениво. Приватный Market.CSGO API защищён общим thread-safe limiter с безопасным потолком четыре запроса в секунду.
