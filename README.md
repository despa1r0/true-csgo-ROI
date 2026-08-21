# trueROI

Локальный каталог скинов Counter-Strike 2 с быстрым поиском и витриной реальных лотов CSFloat. Каталог берётся из [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) и хранится в PostgreSQL.

## Быстрый запуск

Нужен только запущенный Docker Desktop и API-ключ CSFloat в `.env`:

```powershell
.\start.ps1
```

Для запуска в фоне используйте `.\start.ps1 -Detached`. Скрипт запускает базу,
импорт каталога и приложение одной командой. Если `.env` ещё нет, он создаст его
из `.env.example` и попросит добавить `CSFLOAT_API_KEY`.

Первый запуск скачает актуальные `skins_not_grouped.json` и `skins.json`, создаст схему, импортирует варианты и коллекции. После сообщения `Catalogue is ready` откройте:

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
- компактные фильтры локального каталога по оружию, редкости и коллекции;
- отдельные крупные карточки Factory New, Minimal Wear, Field-Tested, Well-Worn и Battle-Scarred;
- список конкретных активных лотов CSFloat открывается поверх сайта после выбора качества;
- сортировки «Лучшие сделки CSFloat» и «Сначала дешевле»;
- серверные фильтры CSFloat по float, варианту и диапазону цены;
- фильтры «только с наклейками» и «только с charm»;
- подробная аналитика открывается при нажатии на конкретный лот;
- цена и справочная оценка CSFloat на карточке лота;
- до 10 активных лотов с ценой, float, paint seed/index и изображениями стикеров;
- цена стикера на CSFloat во всплывающей карточке;
- текущие заявки на покупку и цена быстрой продажи;
- последние продажи с датой, ценой и float;
- количество продаж в доступной истории и beta-оценка ликвидности;
- кэш цен в PostgreSQL (по умолчанию 5 минут) и последняя сохранённая цена при временном сбое CSFloat;
- Swagger API: `http://localhost:8000/docs`.

## API каталога

```text
GET /api/health
GET /api/catalog/filters
GET /api/skins/search?q=redline&weapon=weapon_ak47&rarity=rarity_mythical_weapon&collection=collection-set-community-2
GET /api/skins/{skin_id}
GET /api/skins/{skin_id}/market/csfloat
GET /api/skins/{skin_id}/market/csfloat/listings?sort_by=best_deal&wear=field-tested&variant=normal&has_stickers=true&has_charm=false
GET /api/listings/{listing_id}/market/csfloat/quick-sell
GET /api/variants/{variant_id}/market/csfloat
```

Поиск работает по таблице `skins`, качества — по `skin_variants`, а связь с коллекциями — по `skin_collections`. В таблицах скинов и вариантов сохраняется `raw_data JSONB`, поэтому новые поля источника можно подключать постепенно.
CSFloat сопоставляется с вариантами по точному `skin_variants.market_hash_name`.
Последняя минимальная цена хранится в `marketplace_listings`; отсутствие активных
лотов также кэшируется, чтобы не повторять одинаковые запросы.

Подробный endpoint вызывается лениво — только при открытии модального окна лота. Его ответ
хранится в `marketplace_variant_details` 120 секунд и содержит максимум 10
активных buy-now листингов, подходящие buy orders и доступную историю продаж.
Если CSFloat ограничивает endpoint, API возвращает сохранённые данные и отдельное
безопасное описание ошибки.

Ликвидность помечена как beta. Это оценка качества быстрой продажи, а не
вероятность продажи:

```text
score = 65% * price_retention
      + 25% * near_bid_depth
      + 10% * sales_velocity
```

`price_retention` показывает, какую долю минимальной цены сохраняет лучшая заявка
на покупку. `near_bid_depth` учитывает количество заявок в пределах 5% от лучшей,
а `sales_velocity` — продажи в день по доступной истории CSFloat. Заявки
проверяются относительно конкретного активного лота; для инвентарного предмета
результат может отличаться из-за float и наклеек.

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

Источники можно заменить переменными `CATALOG_SOURCE_URL` и `CATALOG_GROUPED_SOURCE_URL`. Английская версия выбрана намеренно: её `market_hash_name` пригодны для точного поиска цен на маркетплейсах.

## Тесты

```powershell
python -m pip install -r backend/requirements.txt
python -m pytest
```
