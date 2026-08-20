# trueROI

Локальный каталог скинов Counter-Strike 2 с быстрым поиском, превью и вариантами качества. Каталог берётся из [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) и хранится в PostgreSQL.

## Быстрый запуск

Нужен только запущенный Docker Desktop и API-ключ CSFloat в `.env`:

```powershell
.\start.ps1
```

Для запуска в фоне используйте `.\start.ps1 -Detached`. Скрипт запускает базу,
импорт каталога и приложение одной командой. Если `.env` ещё нет, он создаст его
из `.env.example` и попросит добавить `CSFLOAT_API_KEY`.

Первый запуск скачает актуальный `skins_not_grouped.json`, создаст схему и заполнит БД. После сообщения `Catalogue is ready` откройте:

```text
http://localhost:8000
```

Повторный `docker compose up` обновляет каталог идемпотентно. Данные PostgreSQL остаются в Docker volume.

Остановить приложение:

```powershell
docker compose down
```

Удалить также локальную БД и начать с чистого каталога:

```powershell
docker compose down -v
```

## Что доступно

- автоподсказки по названию с превью;
- фильтры по оружию и редкости;
- карточка скина с float-диапазоном и paint index;
- компактные фильтры-теги по оружию, редкости и типу варианта;
- раскрываемые блоки Factory New, Minimal Wear, Field-Tested, Well-Worn и Battle-Scarred;
- переключение обычных, StatTrak™ и Souvenir вариантов внутри блока;
- минимальная цена активных лотов CSFloat для каждого варианта;
- переход по цене на страницу лотов этого варианта на CSFloat;
- до 10 активных лотов с ценой, float, paint seed/index и стикерами;
- количество продаж в доступной истории и beta-оценка ликвидности;
- кэш цен в PostgreSQL (по умолчанию 5 минут) и последняя сохранённая цена при временном сбое CSFloat;
- Swagger API: `http://localhost:8000/docs`.

## API каталога

```text
GET /api/health
GET /api/catalog/filters
GET /api/skins/search?q=redline&weapon=weapon_ak47&rarity=rarity_mythical_weapon
GET /api/skins/{skin_id}
GET /api/skins/{skin_id}/market/csfloat
GET /api/variants/{variant_id}/market/csfloat
```

Поиск работает по таблице `skins`, а качества — по `skin_variants`. В обеих таблицах сохраняется `raw_data JSONB`, поэтому новые поля источника можно подключать постепенно.
CSFloat сопоставляется с вариантами по точному `skin_variants.market_hash_name`.
Последняя минимальная цена хранится в `marketplace_listings`; отсутствие активных
лотов также кэшируется, чтобы не повторять одинаковые запросы.

Подробный endpoint вызывается лениво — только при раскрытии wear-блока. Его ответ
хранится в `marketplace_variant_details` 120 секунд и содержит максимум 10
активных buy-now листингов. Если CSFloat ограничивает endpoint, API возвращает
сохранённые данные и отдельное безопасное описание ошибки.

Ликвидность помечена как beta. Это прозрачная внутренняя оценка:

```text
liquidity_score = min(100, sales_in_available_history / active_listings * 100)
```

`sales_in_available_history` — размер выборки, которую в данный момент возвращает
CSFloat, а не гарантированное полное число продаж за всё время.

## Настройка CSFloat

В `.env` укажите ключ без кавычек:

```dotenv
CSFLOAT_API_KEY=ваш_ключ
```

Ключ не передаётся во frontend и не возвращается API приложения. Весь индекс цен
CSFloat загружается одним запросом; частоту обновления можно изменить через
`CSFLOAT_CACHE_TTL_SECONDS`. Время хранения подробностей регулируется через
`CSFLOAT_DETAILS_TTL_SECONDS`.

## Обновить только каталог

При уже запущенной БД:

```powershell
docker compose run --rm catalog-seed
```

Источник можно заменить переменной `CATALOG_SOURCE_URL`. Английская версия выбрана намеренно: её `market_hash_name` пригодны для будущего поиска цен на маркетплейсах.

## Тесты

```powershell
python -m pip install -r backend/requirements.txt
python -m pytest
```
