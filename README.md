# trueROI

Локальный каталог скинов Counter-Strike 2 с быстрым поиском, витриной реальных лотов CSFloat и сравнением минимальных цен с CSGO Market. Каталог берётся из [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) и хранится в PostgreSQL.

## Быстрый запуск

Нужен запущенный Docker Desktop и API-ключи CSFloat и CSGO Market в `.env`:

```powershell
.\start.ps1
```

Для запуска в фоне используйте `.\start.ps1 -Detached`. Скрипт запускает базу,
импорт каталога и приложение одной командой. Если `.env` ещё нет, он создаст его
из `.env.example` и попросит добавить `CSFLOAT_API_KEY` и `CSGOMARKET_API_KEY`.

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
- минимальные цены CSFloat и CSGO Market рядом на каждой карточке качества;
- переключатель конкретных лотов CSFloat/CSGO Market, явное направление покупки/продажи и настройки комиссий пополнения/вывода;
- режимы профита Raw, Smart, Enhanced и Quick flip; Quick flip лениво получает лучший bid другой площадки;
- серверное сравнение обеих направлений сделки через Profit Engine;
- список конкретных активных лотов выбранной площадки открывается поверх сайта после выбора качества;
- детальный экран показывает аналитику CSFloat и CSGO Market параллельно; публичная история CSGO Market не содержит float проданных предметов;
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
- подробные лоты, стакан и публичная история CSGO Market через отдельный adapter;
- Swagger API: `http://localhost:8000/docs`.

## API каталога

```text
GET /api/health
GET /api/catalog/filters
GET /api/skins/search?q=redline&weapon=weapon_ak47&rarity=rarity_mythical_weapon&collection=collection-set-community-2
GET /api/skins/{skin_id}
GET /api/skins/{skin_id}/market/csfloat
GET /api/skins/{skin_id}/market/csgomarket
GET /api/skins/{skin_id}/market/csgomarket/listings
GET /api/skins/{skin_id}/markets/compare?profit_mode=smart&deposit_method=crypto&withdraw_method=crypto
GET /api/skins/{skin_id}/market/csfloat/listings?sort_by=best_deal&wear=field-tested&variant=normal&has_stickers=true&has_charm=false
GET /api/listings/{listing_id}/market/csfloat/quick-sell
GET /api/variants/{variant_id}/market/csfloat
GET /api/variants/{variant_id}/market/csgomarket
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

## Adapter CSGO Market

`backend/app/csgomarket.py` загружает публичный USD-прайс-лист лучших предложений
без API-ключа и нормализует его в тот же формат `price_cents` / `quantity`, который
использует проект. Приватные методы добавляют конкретные лоты и стакан, а история
продаж загружается из публичных статических JSON. Результаты синхронизируются с
общим PostgreSQL-кэшем и участвуют в сравнении цен и ROI.

```dotenv
CSGOMARKET_API_KEY=ваш_ключ
CSGOMARKET_MAX_REQUESTS_PER_SECOND=4
```

Лимитер общий для всего backend-процесса и равномерно разносит приватные вызовы
минимум на 260 мс. Настройка программно ограничена значением 4, даже если в `.env`
случайно указано больше. Ключ не возвращается клиенту и не включается в тексты
ошибок. Индекс цен кэшируется 300 секунд, подробности — 120 секунд, публичный
индекс истории — 3600 секунд. `extra.stickers` сохраняется как список Steam class
ID; официальный sticker-каталог использует другую систему ID и поэтому не
применяется для неподтверждённого сопоставления имён и изображений.

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
