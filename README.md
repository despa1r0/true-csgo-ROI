# trueROI

Локальный каталог скинов Counter-Strike 2 с быстрым поиском, витриной реальных лотов CSFloat и сравнением минимальных цен с CSGO Market. Каталог берётся из [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) и хранится в PostgreSQL.

## Быстрый запуск на Linux и Windows

Проект запускается через Docker Compose: отдельные процессы поднимают PostgreSQL,
одноразовый импорт каталога (`catalog-seed`) и FastAPI. Нужны ключи CSFloat и
CSGO Market — без них стартовый скрипт Windows остановится, а рыночные данные не
будут доступны.

Первый запуск скачивает актуальные `skins_not_grouped.json` и `skins.json`,
создаёт схему PostgreSQL и импортирует варианты и коллекции. Это может занять
несколько минут. Данные БД сохраняются в Docker volume.

### Linux

1. Установите и запустите Docker Engine с Docker Compose v2. Убедитесь, что
   текущий пользователь имеет доступ к Docker:

   ```bash
   docker compose version
   docker ps
   ```

2. В корне репозитория создайте локальный файл настроек и добавьте в него ключи:

   ```bash
   cp .env.example .env
   ```

   В `.env` заполните как минимум:

   ```dotenv
   CSFLOAT_API_KEY=ваш_ключ
   CSGOMARKET_API_KEY=ваш_ключ
   ```

3. Соберите и запустите сервисы:

   ```bash
   docker compose up --build
   ```

   Для фонового запуска используйте `docker compose up --build -d`.
   После успешного импорта в логах появится `Catalogue is ready`.

4. Откройте [http://localhost:8000](http://localhost:8000). Проверить, что API
   отвечает, можно командой:

   ```bash
   curl http://localhost:8000/api/health
   ```

### Windows

1. Установите Docker Desktop, запустите его и дождитесь статуса *Engine running*.
   В PowerShell из корня репозитория проверьте Compose:

   ```powershell
   docker compose version
   ```

2. Запустите подготовленный скрипт:

   ```powershell
   .\start.ps1
   ```

   Если `.env` отсутствует, скрипт создаст его из `.env.example`. Заполните в
   созданном файле `CSFLOAT_API_KEY` и `CSGOMARKET_API_KEY`, затем повторите
   команду. Для запуска в фоне:

   ```powershell
   .\start.ps1 -Detached
   ```

3. После `Catalogue is ready` откройте [http://localhost:8000](http://localhost:8000).
   Проверка API из PowerShell:

   ```powershell
   Invoke-WebRequest http://localhost:8000/api/health
   ```

### Управление запуском

Посмотреть состояние и логи сервисов:

```bash
docker compose ps
docker compose logs -f api
```

Остановить приложение, сохранив базу:

```bash
docker compose down
```

Полностью удалить локальную БД и начать импорт заново:

```bash
docker compose down -v
```

> Эта команда удаляет Docker volume с PostgreSQL и все сохранённые данные проекта.

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

## Как сейчас устроен проект

```text
ByMykel / CSGO-API                         CSFloat                CSGO Market
      │                                      │                         │
      │ catalog-seed                         │ adapter                 │ adapter
      ▼                                      ▼                         ▼
skins · skin_variants · skin_collections   нормализованные цены, лоты, стакан и история
      │                                      │                         │
      └─────────────── PostgreSQL-кэш: marketplace_listings ───────────┘
                                      │
                                      ▼
                          FastAPI: /api/*
                           │          │
                           │          └── Profit Engine + правила комиссий
                           ▼
                  frontend/ (HTML, CSS, JavaScript)
```

### Поток данных

1. `catalog-seed` скачивает два файла ByMykel: плоский список вариантов и
   сгруппированный список с коллекциями. Затем выполняет идемпотентный upsert в
   PostgreSQL. Поиск всегда работает по локальному каталогу, а не по API
   маркетплейсов.
2. Пользователь ищет базовый скин в `skins`, выбирает один из его вариантов в
   `skin_variants` — например, конкретный wear или StatTrak™.
3. API сопоставляет вариант с площадками по точному английскому
   `market_hash_name`. Адаптеры CSFloat и CSGO Market получают только динамические
   данные: минимальную цену, конкретные лоты, заявки и историю продаж.
4. Общие индексы цен сохраняются в `marketplace_listings`, а подробности варианта
   (лоты, стакан, история и ликвидность) — в `marketplace_variant_details`.
   Поэтому повторное открытие карточки не обязано обращаться к внешней площадке.
5. Для сравнения API параллельно получает нормализованные данные двух площадок.
   Profit Engine принимает уже готовые суммы и правила комиссий; он не знает о
   HTTP, FastAPI, PostgreSQL или формате ответов внешних API.

### Каталог и нормализация данных

Каталог и рынок — разные слои данных:

| Слой | Что в нём хранится | Зачем |
| --- | --- | --- |
| `skins` | базовый скин, оружие, редкость, изображение, float-диапазон | локальный поиск и группировка |
| `skin_variants` | точное рыночное имя, wear, StatTrak™, Souvenir | выбор предмета, который можно сопоставить с маркетплейсом |
| `skin_collections` | связи с коллекциями | фильтр по коллекции |
| `marketplace_listings` | минимальная цена, количество, время получения и площадка | кэш индекса цен |
| `marketplace_variant_details` | подробные лоты, заявки, история и метрики | кэш модального окна и быстрой продажи |

Исходные записи каталога остаются в `raw_data JSONB`, поэтому новые поля источника
можно подключать без немедленной переделки всей схемы.

Каждый adapter изолирует формат своей площадки. Общая минимальная котировка в коде
называется `MarketPrice` и имеет единый вид:

```text
marketplace · price_cents · item_url · listing_id? · float_value? · quantity? · fetched_at? · stale
```

Для конкретных лотов оба adapter-а также возвращают одинаковые по смыслу поля:
`listing_id`, `price_cents`, `item_url`, `float_value`, `paint_seed`,
`paint_index`, `stickers`, `charms`. Поля, которых площадка не даёт, остаются
`null` или пустым списком: например, публичная история CSGO Market не содержит
float проданных предметов, а её идентификаторы наклеек пока не сопоставляются с
официальным каталогом.

Все денежные значения внутри приложения — целые `*_cents`, не `float`:

```text
effective_buy = buy_price + deposit_fee
effective_payout = sell_price - sell_fee - withdraw_fee
profit = effective_payout - effective_buy
ROI = profit / effective_buy × 100
```

Процентные и фиксированные комиссии описаны отдельно в
`backend/app/marketplaces_fees.py`. Режимы `raw`, `smart`, `enhanced` и
`quick_flip` выбирают, какие из этих правил применить; в `quick_flip` цена продажи
берётся из лучшей заявки на покупку другой площадки.

## API каталога

Ниже перечислены все маршруты текущего backend-а. Интерактивные схемы запросов и
ответов доступны в Swagger: [http://localhost:8000/docs](http://localhost:8000/docs).

### Состояние и локальный каталог

```text
GET /api/health
GET /api/catalog/filters
GET /api/skins/search?q=redline&weapon=weapon_ak47&rarity=rarity_mythical_weapon&collection=collection-set-community-2
GET /api/skins/{skin_id}
```

- `GET /api/health` — статус приложения и число записей каталога.
- `GET /api/catalog/filters` — доступные оружия, редкости и коллекции.
- `GET /api/skins/search` — локальный поиск. `q` имеет лимит 100 символов,
  `limit` — от 1 до 20; также поддерживает `weapon`, `rarity`, `collection`.
- `GET /api/skins/{skin_id}` — базовый скин с его вариантами.

### Цены, лоты и аналитика маркетплейсов

```text
GET /api/skins/{skin_id}/market/csfloat
GET /api/skins/{skin_id}/market/csgomarket
GET /api/skins/{skin_id}/markets/compare?profit_mode=smart&deposit_method=crypto&withdraw_method=crypto
GET /api/skins/{skin_id}/market/csfloat/listings?sort_by=best_deal&wear=field-tested&variant=normal&has_stickers=true&has_charm=false
GET /api/skins/{skin_id}/market/csgomarket/listings?sort_by=lowest_price&wear=field-tested&variant=normal
GET /api/listings/{listing_id}/market/csfloat/quick-sell
GET /api/variants/{variant_id}/market/csfloat
GET /api/variants/{variant_id}/market/csgomarket
```

- Маршруты `/market/csfloat` и `/market/csgomarket` возвращают кэшированный
  индекс минимальных цен для всех вариантов выбранного скина.
- `/markets/compare` сопоставляет варианты двух площадок, показывает самую дешёвую
  цену, gross spread и обе стороны сделки с расчётом ROI. Принимает
  `profit_mode=raw|smart|enhanced|quick_flip`, `deposit_method=card|crypto`,
  `withdraw_method=card|crypto` и `use_deposit_fee`.
- Оба `/listings` возвращают конкретные лоты. Общие параметры: `wear`,
  `variant=any|normal|stattrak|souvenir`, `min_float`, `max_float`,
  `min_price_cents`, `max_price_cents`, `has_stickers`, `has_charm`, `limit`
  (1–50). CSFloat передаёт свою сортировку `best_deal|lowest_price` во внешнее
  API. CSGO Market сейчас всегда сортирует лоты локально по минимальной цене;
  параметр `sort_by` сохраняется в ответе как запрошенный для совместимости UI.
- Маршруты `/api/variants/{variant_id}/market/...` лениво загружают и кэшируют
  подробности одного точного варианта: активные лоты, buy orders, историю продаж
  и beta-оценку ликвидности.
- `GET /api/listings/{listing_id}/market/csfloat/quick-sell` возвращает подходящие
  заявки CSFloat для уже выбранного конкретного лота.

### Площадки и чистый расчёт прибыли

```text
GET  /api/market-overview
GET  /api/marketplaces
POST /api/calculate
```

- `GET /api/marketplaces` — возможности и доступные способы ввода/вывода для
  площадок, зарегистрированных в правилах комиссий.
- `GET /api/market-overview` — те же данные, дополненные демонстрационным именем
  предмета для интерфейса.
- `POST /api/calculate` — детерминированный расчёт без запросов к площадкам.
  Тело: `buy_price_cents`, `sell_price_cents`, `buy_marketplace`,
  `sell_marketplace`, а также опциональные `profit_mode`, `deposit_method`,
  `withdraw_method`, `sell_mode`, `use_deposit_fee`. Ответ содержит каждую
  комиссию, прибыль и три варианта ROI.

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

```bash
docker compose run --rm catalog-seed
```

Команда одинакова в Linux и в PowerShell на Windows.

Источники можно заменить переменными `CATALOG_SOURCE_URL` и `CATALOG_GROUPED_SOURCE_URL`. Английская версия выбрана намеренно: её `market_hash_name` пригодны для точного поиска цен на маркетплейсах.

## Тесты

Linux:

```bash
python -m pip install -r backend/requirements.txt
python -m pytest
```

Windows (PowerShell):

```powershell
py -m pip install -r backend/requirements.txt
py -m pytest
```
