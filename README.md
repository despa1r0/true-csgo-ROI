# trueROI

Локальный каталог скинов Counter-Strike 2 с быстрым поиском, превью и вариантами качества. Каталог берётся из [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) и хранится в PostgreSQL.

## Быстрый запуск

Нужен только Docker Desktop:

```powershell
docker compose up --build
```

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
- отдельные блоки Factory New, Minimal Wear, Field-Tested, Well-Worn и Battle-Scarred;
- фильтры обычных, StatTrak™ и Souvenir вариантов;
- Swagger API: `http://localhost:8000/docs`.

## API каталога

```text
GET /api/health
GET /api/catalog/filters
GET /api/skins/search?q=redline&weapon=weapon_ak47&rarity=rarity_mythical_weapon
GET /api/skins/{skin_id}
```

Поиск работает по таблице `skins`, а качества — по `skin_variants`. В обеих таблицах сохраняется `raw_data JSONB`, поэтому новые поля источника можно подключать постепенно.

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
