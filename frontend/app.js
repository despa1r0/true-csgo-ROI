const elements = Object.fromEntries(
  [
    "catalogStatus", "languageSelect", "searchShell", "searchInput", "suggestions", "searchHint",
    "weaponFilter", "rarityFilter", "collectionFilter", "marketView", "skinImage",
    "skinMeta", "skinName", "skinCollection", "marketStatus", "qualityGrid",
    "qualityMessage", "listingModal", "modalClose", "modalBrowser", "browserTitle",
    "browserOverline", "browserSubtitle", "resultCount", "marketplaceSelect", "sortSelect",
    "bestDealOption", "filterToggle", "activeFilterCount", "profitBuyMarketplace",
    "profitSellMarketplace", "profitAutoSellOption", "profitSwapMarkets", "profitMode", "profitModeTitle",
    "profitModeNote", "profitDepositMethod", "profitWithdrawMethod",
    "profitUseDepositFee", "profitDepositFeeControl",
    "preMarketplaceSelect", "preSortSelect", "preBestDealOption", "preFilterToggle",
    "preActiveFilterCount", "preMarketFilters", "preWearFilter", "preVariantFilter", "preMinFloat",
    "preMaxFloat", "preMinPrice", "preMaxPrice", "preHasStickers", "preHasCharm",
    "preResetMarketFilters", "preFilterError",
    "marketFilters", "variantFilter", "minFloat", "maxFloat", "minPrice", "maxPrice",
    "hasStickers", "hasCharm", "resetMarketFilters", "filterError", "listingGrid",
    "listingsMessage", "modalDetail", "detailBack", "modalListing", "modalAnalytics",
    "suggestionTemplate",
  ].map((id) => [id, document.querySelector(`#${id}`)]),
);

const I18N = {
  ru: {
    "meta.description": "Сравнение цен CS2 на CSFloat и CSGO Market",
    "brand.home": "trueROI — на главную",
    "status.connecting": "Подключение…",
    "status.waiting": "Ожидание",
    "language.label": "Язык",
    "language.aria": "Язык интерфейса",
    "search.section": "Поиск по каталогу",
    "search.input": "Название скина",
    "search.hint": "Введите минимум 2 символа или выберите фильтр",
    "catalogFilters.aria": "Фильтры локального каталога",
    "catalogFilters.weapon": "Оружие",
    "catalogFilters.rarity": "Редкость",
    "catalogFilters.collection": "Коллекция",
    "catalogFilters.anyMasculine": "Любое",
    "catalogFilters.anyFeminine": "Любая",
    "profit.aria": "Настройки расчёта прибыли",
    "profit.engine": "ПРОФИТ-ДВИЖОК",
    "profit.mode": "Режим",
    "profit.buyOn": "Купить на",
    "profit.sellOn": "Продать на",
    "profit.deposit": "Пополнение",
    "profit.withdraw": "Вывод",
    "profit.swapTitle": "Поменять площадки местами",
    "profit.swapAria": "Поменять площадки покупки и продажи местами",
    "profit.quickDeposit": "Депозит в quick flip",
    "payment.card": "Карта",
    "preFilters.aria": "Фильтры лотов до выбора качества",
    "preFilters.overline": "ЛОТЫ",
    "preFilters.title": "Настройте выдачу до выбора качества",
    "marketplace.label": "Площадка",
    "marketplace.all": "Все",
    "marketplace.auto": "Авто",
    "sort.label": "Сортировка",
    "sort.bestDeals": "Лучшие сделки CSFloat",
    "sort.lowest": "Сначала дешевле",
    "filters.button": "⌁ Фильтры",
    "filters.variant": "Вариант",
    "filters.wear": "Износ",
    "filters.any": "Любой",
    "filters.normal": "Обычный",
    "filters.fromFloat": "от 0.00",
    "filters.toFloat": "до 1.00",
    "filters.minFloat": "Минимальный float",
    "filters.maxFloat": "Максимальный float",
    "filters.price": "Цена, USD",
    "filters.from": "от",
    "filters.to": "до",
    "filters.minPrice": "Минимальная цена",
    "filters.maxPrice": "Максимальная цена",
    "filters.stickersOnly": "Только с наклейками",
    "filters.charmOnly": "Только с charm",
    "filters.apply": "Применить",
    "filters.show": "Показать",
    "common.reset": "Сбросить",
    "common.close": "Закрыть",
    "quality.overline": "КАЧЕСТВО",
    "quality.title": "Выберите степень износа",
    "quality.note": "После выбора откроются конкретные листинги этого качества.",
    "detail.back": "← Все листинги качества",
  },
  en: {
    "meta.description": "Compare CS2 prices on CSFloat and CSGO Market",
    "brand.home": "trueROI — home",
    "status.connecting": "Connecting…",
    "status.waiting": "Waiting",
    "language.label": "Language",
    "language.aria": "Interface language",
    "search.section": "Catalog search",
    "search.input": "Skin name",
    "search.hint": "Enter at least 2 characters or choose a filter",
    "catalogFilters.aria": "Local catalog filters",
    "catalogFilters.weapon": "Weapon",
    "catalogFilters.rarity": "Rarity",
    "catalogFilters.collection": "Collection",
    "catalogFilters.anyMasculine": "Any",
    "catalogFilters.anyFeminine": "Any",
    "profit.aria": "Profit calculation settings",
    "profit.engine": "PROFIT ENGINE",
    "profit.mode": "Mode",
    "profit.buyOn": "Buy on",
    "profit.sellOn": "Sell on",
    "profit.deposit": "Deposit",
    "profit.withdraw": "Withdrawal",
    "profit.swapTitle": "Swap marketplaces",
    "profit.swapAria": "Swap buy and sell marketplaces",
    "profit.quickDeposit": "Deposit fee in quick flip",
    "payment.card": "Card",
    "preFilters.aria": "Listing filters before wear selection",
    "preFilters.overline": "LISTINGS",
    "preFilters.title": "Set up results before choosing wear",
    "marketplace.label": "Marketplace",
    "marketplace.all": "All",
    "marketplace.auto": "Auto",
    "sort.label": "Sort",
    "sort.bestDeals": "Best CSFloat deals",
    "sort.lowest": "Lowest price first",
    "filters.button": "⌁ Filters",
    "filters.variant": "Variant",
    "filters.wear": "Wear",
    "filters.any": "Any",
    "filters.normal": "Normal",
    "filters.fromFloat": "from 0.00",
    "filters.toFloat": "to 1.00",
    "filters.minFloat": "Minimum float",
    "filters.maxFloat": "Maximum float",
    "filters.price": "Price, USD",
    "filters.from": "from",
    "filters.to": "to",
    "filters.minPrice": "Minimum price",
    "filters.maxPrice": "Maximum price",
    "filters.stickersOnly": "Only with stickers",
    "filters.charmOnly": "Only with charm",
    "filters.apply": "Apply",
    "filters.show": "Show",
    "common.reset": "Reset",
    "common.close": "Close",
    "quality.overline": "WEAR",
    "quality.title": "Choose wear condition",
    "quality.note": "Select a condition to open its individual listings.",
    "detail.back": "← All wear listings",
  },
};

const TEXT = {
  ru: {
    "profit.rawTitle": "Raw · без комиссий",
    "profit.rawNote": "Покупка и продажа по ask-ценам без каких-либо комиссий.",
    "profit.smartTitle": "Smart · все комиссии",
    "profit.smartNote": "Ask → ask с комиссиями пополнения, продажи и вывода.",
    "profit.enhancedTitle": "Enhanced · без комиссии депозита",
    "profit.enhancedNote": "Ask → ask; комиссия пополнения исключена, продажа и вывод учитываются.",
    "profit.quickTitle": "Quick flip · продажа в лучший bid",
    "profit.quickNote": "Автоматически покупает самый дешёвый ask и продаёт в fast buy другой площадки.",
    "api.requestError": "Ошибка запроса ({status})",
    "catalog.count": "{count} скинов",
    "catalog.unavailable": "Каталог недоступен",
    "catalog.databaseError": "Не удалось подключиться к базе данных",
    "search.searching": "Ищем совпадения…",
    "search.unavailable": "Поиск временно недоступен",
    "search.found": "Найдено: {count}",
    "search.none": "Совпадений не найдено",
    "search.item": "Предмет",
    "search.loadingWear": "Загружаем качества…",
    "search.selected": "Скин выбран",
    "search.skinError": "Не удалось загрузить скин",
    "search.variants.one": "{count} вариант",
    "search.variants.few": "{count} варианта",
    "search.variants.many": "{count} вариантов",
    "skin.noCollection": "Вне коллекции",
    "market.loadingQuick": "Ищем лучшие fast buy заявки…",
    "market.comparing": "Сравниваем площадки…",
    "market.cached": "Часть цен из кэша",
    "market.ready": "2 рынка · цены актуальны",
    "market.unavailable": "Площадки временно недоступны",
    "market.noListings": "Активных лотов нет",
    "market.compareError": "Сравнение временно недоступно",
    "quality.none": "Для скина не найдены варианты качества.",
    "quality.noFilterMatch": "Нет степеней износа, подходящих выбранным фильтрам.",
    "quality.priceLoading": "Цена…",
    "quality.fromPrice": "от {price}",
    "quality.noPrice": "Нет цены",
    "quality.fastBuyUnavailable": "Fast buy недоступен",
    "profit.cardCase": "карту",
    "profit.noFees": "без комиссий",
    "profit.noDepositFee": "без комиссии пополнения",
    "profit.withDepositFee": "с комиссией пополнения",
    "profit.fastBuySale": "продажа в лучший fast buy",
    "profit.askSale": "продажа по ask-цене",
    "profit.tooltip": "{name}. {mode}, {sellMode}, пополнение через {deposit}, вывод через {withdraw}, {depositNote}",
    "filters.floatOrderError": "Минимальный float больше максимального.",
    "filters.priceOrderError": "Минимальная цена больше максимальной.",
    "filters.applied": "Фильтры применены — теперь выберите степень износа.",
    "listings.loading": "Загружаем актуальные лоты {market}…",
    "listings.none": "Лотов с такими фильтрами сейчас нет.",
    "listings.count": "{count} лотов",
    "listings.error": "Не удалось загрузить лоты {market}",
    "listings.noStickers": "Без наклеек",
    "listings.valuation": "Оценка {price}",
    "attachments.sticker": "Наклейка",
    "attachments.priceUnavailable": "Цена недоступна",
    "attachments.active": "{count} активных",
    "detail.variantMissing": "Для этого варианта нет соответствия в локальном каталоге.",
    "detail.marketError": "Не удалось загрузить данные площадки",
    "detail.collection": "Коллекция",
    "detail.valuation": "Оценка CSFloat",
    "detail.valuationDifference": "Разница с оценкой",
    "detail.openListing": "Открыть лот на {market} ↗",
    "detail.stickers": "Наклейки",
    "detail.none": "Нет",
    "detail.selectedListing": "ВЫБРАННЫЙ ЛОТ",
    "detail.comparison": "СРАВНЕНИЕ ДВУХ ПЛОЩАДОК",
    "detail.autoDirection": "АВТОМАТИЧЕСКОЕ НАПРАВЛЕНИЕ · QUICK FLIP",
    "detail.cheapestDirection": "АВТОМАТИЧЕСКОЕ НАПРАВЛЕНИЕ · САМАЯ ДЕШЁВАЯ ПОКУПКА",
    "detail.direction": "ВЫБРАННОЕ НАПРАВЛЕНИЕ",
    "detail.swap": "⇄ Поменять",
    "detail.notEnoughPrices": "Недостаточно цен для расчёта этого направления.",
    "detail.buy": "Покупка",
    "detail.sell": "Продажа",
    "detail.netProfit": "Чистая прибыль",
    "detail.calculation": "РАСЧЁТ ROI",
    "detail.calculationHint": "Настройки применяются и к карточкам, и к этой статистике.",
    "detail.recalculating": "Пересчитываем ROI…",
    "analytics.marketplace": "ПЛОЩАДКА",
    "analytics.unavailable": "Данные площадки недоступны",
    "analytics.high": "Высокая",
    "analytics.medium": "Средняя",
    "analytics.low": "Низкая",
    "common.noData": "Нет данных",
    "analytics.minPrice": "Мин. цена",
    "analytics.exactVariant": "по точному варианту",
    "analytics.quickSale": "Быстрая продажа",
    "analytics.noOrder": "нет заявки",
    "analytics.askDiscount": "−{percent} к ask",
    "analytics.liquidity": "Ликвидность β",
    "analytics.marketScore": "рыночный score",
    "analytics.salesPerDay": "Продаж в день",
    "analytics.listings": "Лотов",
    "analytics.activeNow": "активно сейчас",
    "analytics.bidDepth": "Глубина bid",
    "analytics.withinFive": "в пределах 5%",
    "analytics.open": "Открыть {market} ↗",
    "analytics.apiNoFloat": "API не передаёт",
    "analytics.quickOrders": "Заявки на быструю продажу",
    "analytics.price": "Цена",
    "analytics.quantity": "Количество",
    "analytics.conditions": "Условия",
    "analytics.noQuickOrders": "Подходящих заявок сейчас нет",
    "analytics.orderNote": "Заявки зависят от float и свойств конкретного предмета.",
    "analytics.activeListings": "Активные позиции",
    "analytics.seed": "Seed",
    "analytics.stickers": "Наклейки",
    "analytics.noActiveListings": "Активных позиций нет",
    "analytics.salesHistory": "История продаж",
    "analytics.date": "Дата",
    "analytics.noSales": "История продаж недоступна",
    "analytics.salesTrend": "Динамика последних продаж",
    "analytics.points": "{count} точек",
    "analytics.chartAria": "График последних продаж",
    "analytics.records": "{count} записей",
    "analytics.noRestrictions": "Без ограничений",
    "browser.listings": "ЛИСТИНГИ",
    "filters.normalLabel": "Обычный",
  },
  en: {
    "profit.rawTitle": "Raw · no fees",
    "profit.rawNote": "Buy and sell at ask prices with no fees.",
    "profit.smartTitle": "Smart · all fees",
    "profit.smartNote": "Ask → ask with deposit, sale, and withdrawal fees.",
    "profit.enhancedTitle": "Enhanced · no deposit fee",
    "profit.enhancedNote": "Ask → ask; excludes deposit fees and includes sale and withdrawal fees.",
    "profit.quickTitle": "Quick flip · sell to best bid",
    "profit.quickNote": "Automatically buys the cheapest ask and sells to the other marketplace's best bid.",
    "api.requestError": "Request failed ({status})",
    "catalog.count": "{count} skins",
    "catalog.unavailable": "Catalog unavailable",
    "catalog.databaseError": "Could not connect to the database",
    "search.searching": "Searching…",
    "search.unavailable": "Search is temporarily unavailable",
    "search.found": "Found: {count}",
    "search.none": "No matches found",
    "search.item": "Item",
    "search.loadingWear": "Loading wear conditions…",
    "search.selected": "Skin selected",
    "search.skinError": "Could not load the skin",
    "search.variants.one": "{count} variant",
    "search.variants.few": "{count} variants",
    "search.variants.many": "{count} variants",
    "skin.noCollection": "Not in a collection",
    "market.loadingQuick": "Finding the best fast-buy orders…",
    "market.comparing": "Comparing marketplaces…",
    "market.cached": "Some prices are cached",
    "market.ready": "2 markets · prices are current",
    "market.unavailable": "Marketplaces are temporarily unavailable",
    "market.noListings": "No active listings",
    "market.compareError": "Comparison is temporarily unavailable",
    "quality.none": "No wear variants were found for this skin.",
    "quality.noFilterMatch": "No wear conditions match the selected filters.",
    "quality.priceLoading": "Price…",
    "quality.fromPrice": "from {price}",
    "quality.noPrice": "No price",
    "quality.fastBuyUnavailable": "Fast buy unavailable",
    "profit.cardCase": "card",
    "profit.noFees": "no fees",
    "profit.noDepositFee": "no deposit fee",
    "profit.withDepositFee": "with deposit fee",
    "profit.fastBuySale": "sell to the best fast-buy order",
    "profit.askSale": "sell at the ask price",
    "profit.tooltip": "{name}. {mode}, {sellMode}, deposit via {deposit}, withdraw via {withdraw}, {depositNote}",
    "filters.floatOrderError": "Minimum float is greater than maximum float.",
    "filters.priceOrderError": "Minimum price is greater than maximum price.",
    "filters.applied": "Filters applied — now choose a wear condition.",
    "listings.loading": "Loading current {market} listings…",
    "listings.none": "No listings match these filters.",
    "listings.count": "{count} listings",
    "listings.error": "Could not load {market} listings",
    "listings.noStickers": "No stickers",
    "listings.valuation": "Estimate {price}",
    "attachments.sticker": "Sticker",
    "attachments.priceUnavailable": "Price unavailable",
    "attachments.active": "{count} active",
    "detail.variantMissing": "This variant has no match in the local catalog.",
    "detail.marketError": "Could not load marketplace data",
    "detail.collection": "Collection",
    "detail.valuation": "CSFloat estimate",
    "detail.valuationDifference": "Difference from estimate",
    "detail.openListing": "Open listing on {market} ↗",
    "detail.stickers": "Stickers",
    "detail.none": "None",
    "detail.selectedListing": "SELECTED LISTING",
    "detail.comparison": "TWO-MARKET COMPARISON",
    "detail.autoDirection": "AUTOMATIC DIRECTION · QUICK FLIP",
    "detail.cheapestDirection": "AUTOMATIC DIRECTION · CHEAPEST BUY",
    "detail.direction": "SELECTED DIRECTION",
    "detail.swap": "⇄ Swap",
    "detail.notEnoughPrices": "Not enough prices to calculate this direction.",
    "detail.buy": "Buy",
    "detail.sell": "Sell",
    "detail.netProfit": "Net profit",
    "detail.calculation": "ROI CALCULATION",
    "detail.calculationHint": "These settings apply to the cards and this detailed view.",
    "detail.recalculating": "Recalculating ROI…",
    "analytics.marketplace": "MARKETPLACE",
    "analytics.unavailable": "Marketplace data unavailable",
    "analytics.high": "High",
    "analytics.medium": "Medium",
    "analytics.low": "Low",
    "common.noData": "No data",
    "analytics.minPrice": "Min. price",
    "analytics.exactVariant": "exact variant",
    "analytics.quickSale": "Quick sale",
    "analytics.noOrder": "no order",
    "analytics.askDiscount": "−{percent} from ask",
    "analytics.liquidity": "Liquidity β",
    "analytics.marketScore": "market score",
    "analytics.salesPerDay": "Sales per day",
    "analytics.listings": "Listings",
    "analytics.activeNow": "active now",
    "analytics.bidDepth": "Bid depth",
    "analytics.withinFive": "within 5%",
    "analytics.open": "Open {market} ↗",
    "analytics.apiNoFloat": "Not provided by API",
    "analytics.quickOrders": "Quick-sale orders",
    "analytics.price": "Price",
    "analytics.quantity": "Quantity",
    "analytics.conditions": "Conditions",
    "analytics.noQuickOrders": "No suitable orders right now",
    "analytics.orderNote": "Orders depend on the item's float and properties.",
    "analytics.activeListings": "Active listings",
    "analytics.seed": "Seed",
    "analytics.stickers": "Stickers",
    "analytics.noActiveListings": "No active listings",
    "analytics.salesHistory": "Sales history",
    "analytics.date": "Date",
    "analytics.noSales": "Sales history unavailable",
    "analytics.salesTrend": "Recent sales trend",
    "analytics.points": "{count} points",
    "analytics.chartAria": "Recent sales chart",
    "analytics.records": "{count} records",
    "analytics.noRestrictions": "No restrictions",
    "browser.listings": "LISTINGS",
    "filters.normalLabel": "Normal",
  },
};

const PROVIDER_TEXT_EN = {
  "Доступная история CSFloat": "Available CSFloat history",
  "До 200 последних продаж CSGO Market": "Up to 200 recent CSGO Market sales",
  "CSFloat передаёт float для тех продаж, где он доступен в ответе API": "CSFloat provides float values when they are available in the API response.",
  "Публичная история CSGO Market не передаёт float проданного предмета": "CSGO Market's public history does not provide the sold item's float value.",
  "CSFloat проверил эти заявки по float и свойствам выбранного лота.": "CSFloat checked these orders against the selected listing's float and properties.",
  "Заявки проверены относительно самого дешёвого активного лота. Для конкретного инвентарного предмета итог зависит от его float и наклеек.": "Orders were checked against the cheapest active listing. The result for an individual item depends on its float and stickers.",
  "Стакан CSGO Market сопоставлен по market_hash_name. Для Doppler точная цена может зависеть от выбранной phase.": "The CSGO Market order book is matched by market_hash_name. For Doppler, the exact price may depend on the selected phase.",
  "Вариант не найден": "Variant not found",
  "Скин не найден": "Skin not found",
  "Вариант скина не найден": "Skin variant not found",
  "Лот CSFloat не найден": "CSFloat listing not found",
  "Минимальный float больше максимального": "Minimum float is greater than maximum float",
  "Минимальная цена больше максимальной": "Minimum price is greater than maximum price",
  "Для этого скина отсутствует paint index": "This skin has no paint index",
  "Не настроен CSFLOAT_API_KEY": "CSFLOAT_API_KEY is not configured",
  "Не настроен CSGOMARKET_API_KEY": "CSGOMARKET_API_KEY is not configured",
};

function savedLanguage() {
  try { return localStorage.getItem("trueROI.language") === "en" ? "en" : "ru"; }
  catch { return "ru"; }
}

function t(key, variables = {}) {
  const language = state?.language || "ru";
  const template = I18N[language]?.[key] ?? TEXT[language]?.[key] ?? I18N.ru[key] ?? TEXT.ru[key] ?? key;
  return Object.entries(variables).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    template,
  );
}

function translateProviderText(text) {
  if (!text || state.language !== "en") return text;
  return PROVIDER_TEXT_EN[text] || text;
}

function translationKeyFor(text, language) {
  for (const dictionary of [I18N[language] || {}, TEXT[language] || {}]) {
    const match = Object.entries(dictionary).find(([, value]) => !value.includes("{") && value === text);
    if (match) return match[0];
  }
  return null;
}

const WEAR_SLUGS = {
  "Factory New": "factory-new", "Minimal Wear": "minimal-wear",
  "Field-Tested": "field-tested", "Well-Worn": "well-worn",
  "Battle-Scarred": "battle-scarred",
};
const WEAR_CODES = {
  "Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT",
  "Well-Worn": "WW", "Battle-Scarred": "BS",
};
const WEAR_FLOAT_RANGES = {
  "Factory New": [0, 0.07],
  "Minimal Wear": [0.07, 0.15],
  "Field-Tested": [0.15, 0.38],
  "Well-Worn": [0.38, 0.45],
  "Battle-Scarred": [0.45, 1],
};
const PROFIT_MODE_UI = {
  raw: {
    titleKey: "profit.rawTitle",
    noteKey: "profit.rawNote",
  },
  smart: {
    titleKey: "profit.smartTitle",
    noteKey: "profit.smartNote",
  },
  enhanced: {
    titleKey: "profit.enhancedTitle",
    noteKey: "profit.enhancedNote",
  },
  quick_flip: {
    titleKey: "profit.quickTitle",
    noteKey: "profit.quickNote",
  },
};

const state = {
  language: savedLanguage(), catalogueCount: null,
  results: [], selectedIndex: -1, selectedSkin: null, selectedQuality: null,
  selectedListing: null, detailResults: null,
  listings: [], prices: new Map(), pricesPending: false, searchRequest: null,
  pricesRequest: null, marketRequest: null, detailRequest: null, debounce: null,
  searchCache: new Map(), selectedMarketplace: "csfloat",
};

const api = {
  async get(path, signal) {
    const response = await fetch(path, { signal });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(translateProviderText(payload?.detail) || t("api.requestError", { status: response.status }));
    }
    return response.json();
  },
};

function applyStaticLanguage() {
  document.documentElement.lang = state.language;
  elements.languageSelect.value = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  ["aria-label", "title", "placeholder", "content"].forEach((attribute) => {
    const dataAttribute = `i18n${attribute.split("-").map((part) => part[0].toUpperCase() + part.slice(1)).join("")}`;
    document.querySelectorAll(`[data-${dataAttribute.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}]`).forEach((node) => {
      node.setAttribute(attribute, t(node.dataset[dataAttribute]));
    });
  });
}

function changeLanguage(language) {
  const previousLanguage = state.language;
  const marketStatusKey = translationKeyFor(elements.marketStatus.textContent, previousLanguage);
  const searchHintKey = translationKeyFor(elements.searchHint.textContent, previousLanguage);
  state.language = language === "en" ? "en" : "ru";
  try { localStorage.setItem("trueROI.language", state.language); } catch { /* Storage can be disabled. */ }
  applyStaticLanguage();
  if (marketStatusKey) elements.marketStatus.textContent = t(marketStatusKey);
  if (searchHintKey) elements.searchHint.textContent = t(searchHintKey);
  updateProfitModeUi();
  updateCatalogStatus();
  if (state.selectedSkin) {
    renderSelectedSkin();
    renderQualityCards();
  }
  if (!elements.suggestions.hidden) renderSuggestions();
  updateMarketplaceUi();
  if (elements.listingModal.open) {
    elements.browserSubtitle.textContent = `${state.selectedQuality?.wear || ""} · ${WEAR_CODES[state.selectedQuality?.wear] || ""}`;
    if (!elements.modalBrowser.hidden) renderListingsGrid();
    if (!elements.modalDetail.hidden && state.selectedListing) {
      renderModalListing(state.selectedListing);
      if (state.detailResults) renderModalComparison(state.selectedListing, state.detailResults);
    }
  }
}

function updateCatalogStatus() {
  if (state.catalogueCount != null) elements.catalogStatus.textContent = t("catalog.count", { count: formatCount(state.catalogueCount) });
}

async function initialize() {
  try {
    const [health, filters] = await Promise.all([api.get("/api/health"), api.get("/api/catalog/filters")]);
    state.catalogueCount = health.catalogue.skins;
    updateCatalogStatus();
    fillSelect(elements.weaponFilter, filters.weapons || []);
    fillSelect(elements.rarityFilter, filters.rarities || []);
    fillSelect(elements.collectionFilter, filters.collections || []);
  } catch {
    elements.catalogStatus.textContent = t("catalog.unavailable");
    elements.catalogStatus.classList.add("is-error");
    setSearchHint(t("catalog.databaseError"), true);
  }
}

function fillSelect(select, items) {
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.name} · ${formatCount(item.count)}`;
    select.append(option);
  });
}

function catalogFilterIsActive() {
  return Boolean(elements.weaponFilter.value || elements.rarityFilter.value || elements.collectionFilter.value);
}

function scheduleSearch() {
  clearTimeout(state.debounce);
  state.debounce = setTimeout(runSearch, 90);
}

async function runSearch() {
  const query = elements.searchInput.value.trim();
  if ((query.length > 0 && query.length < 2) || (!query && !catalogFilterIsActive())) {
    closeSuggestions();
    setSearchHint(t("search.hint"));
    return;
  }
  const params = new URLSearchParams({ q: query });
  if (elements.weaponFilter.value) params.set("weapon", elements.weaponFilter.value);
  if (elements.rarityFilter.value) params.set("rarity", elements.rarityFilter.value);
  if (elements.collectionFilter.value) params.set("collection", elements.collectionFilter.value);
  const cacheKey = params.toString();
  if (state.searchCache.has(cacheKey)) {
    state.searchRequest?.abort();
    state.results = state.searchCache.get(cacheKey);
    state.selectedIndex = -1;
    renderSuggestions();
    setSearchHint(searchResultLabel());
    return;
  }

  state.searchRequest?.abort();
  const request = new AbortController();
  state.searchRequest = request;
  elements.searchShell.classList.add("is-loading");
  setSearchHint(t("search.searching"));
  try {
    state.results = await api.get(`/api/skins/search?${params}`, request.signal);
    state.searchCache.set(cacheKey, state.results);
    if (state.searchCache.size > 80) state.searchCache.delete(state.searchCache.keys().next().value);
    state.selectedIndex = -1;
    renderSuggestions();
    setSearchHint(searchResultLabel());
  } catch (error) {
    if (error.name !== "AbortError") {
      closeSuggestions();
      setSearchHint(t("search.unavailable"), true);
    }
  } finally {
    if (request === state.searchRequest) elements.searchShell.classList.remove("is-loading");
  }
}

function searchResultLabel() {
  return state.results.length ? t("search.found", { count: state.results.length }) : t("search.none");
}

function renderSuggestions() {
  elements.suggestions.replaceChildren();
  if (!state.results.length) return closeSuggestions();
  state.results.forEach((skin, index) => {
    const node = elements.suggestionTemplate.content.cloneNode(true);
    const button = node.querySelector("button");
    const image = node.querySelector("img");
    button.dataset.index = String(index);
    button.setAttribute("aria-selected", "false");
    image.src = skin.image_url || "";
    node.querySelector("strong").textContent = skin.name;
    node.querySelector("small").textContent = `${skin.weapon_name || t("search.item")} · ${pluralizeVariants(skin.variant_count)}`;
    node.querySelector(".rarity-line").style.background = skin.rarity_color || "#748197";
    button.addEventListener("click", () => selectSkin(skin));
    elements.suggestions.append(node);
  });
  elements.suggestions.hidden = false;
  elements.searchInput.setAttribute("aria-expanded", "true");
}

async function selectSkin(skin) {
  closeSuggestions();
  state.pricesRequest?.abort();
  state.marketRequest?.abort();
  elements.searchInput.value = skin.name;
  setSearchHint(t("search.loadingWear"));
  try {
    state.selectedSkin = await api.get(`/api/skins/${encodeURIComponent(skin.id)}`);
    state.prices = new Map();
    state.pricesPending = true;
    renderSelectedSkin();
    elements.marketView.hidden = false;
    renderQualityCards();
    setSearchHint(t("search.selected"));
    loadWearPrices();
  } catch (error) {
    setSearchHint(error.message || t("search.skinError"), true);
  }
}

function renderSelectedSkin() {
  const skin = state.selectedSkin;
  elements.skinImage.src = skin.image_url || "";
  elements.skinImage.alt = skin.name;
  elements.skinName.textContent = skin.name;
  elements.skinMeta.textContent = [skin.weapon_name, skin.rarity_name].filter(Boolean).join(" · ");
  elements.skinCollection.textContent = (skin.collections || []).map((item) => item.name).join(" · ") || t("skin.noCollection");
}

async function loadWearPrices() {
  state.pricesRequest?.abort();
  const skinId = state.selectedSkin.id;
  const request = new AbortController();
  state.pricesRequest = request;
  setMarketStatus(elements.profitMode.value === "quick_flip" ? t("market.loadingQuick") : t("market.comparing"), "loading");
  try {
    const params = new URLSearchParams({
      profit_mode: elements.profitMode.value,
      deposit_method: elements.profitDepositMethod.value,
      withdraw_method: elements.profitWithdrawMethod.value,
      use_deposit_fee: String(elements.profitUseDepositFee.checked),
    });
    const result = await api.get(`/api/skins/${encodeURIComponent(skinId)}/markets/compare?${params}`, request.signal);
    if (request !== state.pricesRequest || state.selectedSkin?.id !== skinId) return;
    state.prices = new Map(result.variants.map((item) => [item.variant_id, item]));
    const firstError = result.marketplaces.find((item) => item.error)?.error;
    const available = result.variants.reduce(
      (count, item) => count + Object.values(item.markets || {}).filter(Boolean).length,
      0,
    );
    if (available) setMarketStatus(firstError ? t("market.cached") : t("market.ready"), firstError ? "warning" : "ready");
    else if (firstError) setMarketStatus(t("market.unavailable"), "error");
    else setMarketStatus(t("market.noListings"), "muted");
  } catch (error) {
    if (error.name !== "AbortError") setMarketStatus(t("market.compareError"), "error");
  } finally {
    if (request === state.pricesRequest) {
      state.pricesPending = false;
      renderQualityCards();
    }
  }
}

function renderQualityCards() {
  elements.qualityGrid.replaceChildren();
  const allQualities = state.selectedSkin?.qualities || [];
  const qualities = allQualities.filter(qualityMatchesPreselection);
  elements.qualityMessage.hidden = Boolean(qualities.length);
  if (!qualities.length) {
    showMessage(elements.qualityMessage, t(allQualities.length ? "quality.noFilterMatch" : "quality.none"), "empty");
    return;
  }
  qualities.forEach((quality) => {
    const automaticBuy = elements.profitBuyMarketplace.value === "all";
    const qualityVariants = quality.variants.filter(variantMatchesPreselection);
    const marketMinimums = { csfloat: null, csgomarket: null };
    const opportunities = [];
    qualityVariants.forEach((variant) => {
      const comparison = state.prices.get(variant.id);
      (comparison?.opportunities || [])
        .filter((opportunity) => elements.profitMode.value === "quick_flip" || automaticBuy || (
          opportunity.buy_marketplace === elements.profitBuyMarketplace.value
          && opportunity.sell_marketplace === elements.profitSellMarketplace.value
        ))
        .forEach((opportunity) => {
          opportunities.push({ ...opportunity, market_hash_name: comparison.market_hash_name });
        });
      Object.entries(comparison?.markets || {}).forEach(([marketplace, listing]) => {
        if (!listing) return;
        if (!marketMinimums[marketplace] || listing.price_cents < marketMinimums[marketplace].price_cents) {
          marketMinimums[marketplace] = listing;
        }
      });
    });
    const availablePrices = Object.entries(marketMinimums).filter(([, listing]) => listing);
    availablePrices.sort((left, right) => left[1].price_cents - right[1].price_cents);
    const cheapest = availablePrices[0]?.[1];
    const cheapestMarket = availablePrices[0]?.[0];
    opportunities.sort((left, right) => automaticBuy
      ? left.buy_price_cents - right.buy_price_cents || right.profit_cents - left.profit_cents
      : right.profit_cents - left.profit_cents);
    const bestOpportunity = opportunities[0];
    const card = document.createElement("button");
    card.type = "button";
    card.className = "quality-card";
    const top = element("div", "quality-card-top");
    top.append(element("strong", "wear-code", WEAR_CODES[quality.wear] || "—"), element("span", "", quality.wear));
    const imageWrap = element("div", "quality-image");
    const image = document.createElement("img");
    image.src = qualityVariants[0]?.image_url || state.selectedSkin.image_url || "";
    image.alt = "";
    imageWrap.append(image);
    const types = qualityVariants.map(variantTypeLabel);
    const bottom = element("div", "quality-card-bottom");
    const price = element("strong", "quality-price");
    price.textContent = state.pricesPending ? t("quality.priceLoading") : cheapest ? t("quality.fromPrice", { price: formatUsd(cheapest.price_cents) }) : t("quality.noPrice");
    const marketPrices = element("div", "quality-market-prices");
    [
      ["csfloat", "CSFloat"],
      ["csgomarket", "CSGO Market"],
    ].forEach(([marketplace, label]) => {
      const row = element("span", marketplace === cheapestMarket ? "is-cheapest" : "");
      row.append(element("small", "", label), element("strong", "", state.pricesPending ? "…" : formatNullableUsd(marketMinimums[marketplace]?.price_cents)));
      marketPrices.append(row);
    });
    bottom.append(price, marketPrices);
    if (bestOpportunity) {
      const marketLabels = { csfloat: "CSFloat", csgomarket: "CSGO" };
      const profitTone = bestOpportunity.profit_cents > 0 ? "is-positive" : bestOpportunity.profit_cents < 0 ? "is-negative" : "is-neutral";
      const profit = element("small", `quality-profit ${profitTone}`);
      const sign = bestOpportunity.profit_cents > 0 ? "+" : "";
      profit.textContent = `${marketLabels[bestOpportunity.buy_marketplace]} → ${marketLabels[bestOpportunity.sell_marketplace]} · ${sign}${formatUsd(bestOpportunity.profit_cents)} · ${formatPercent(bestOpportunity.cash_roi_percent)}`;
      const depositLabel = elements.profitDepositMethod.value === "card" ? t("profit.cardCase") : "crypto";
      const withdrawLabel = elements.profitWithdrawMethod.value === "card" ? t("profit.cardCase") : "crypto";
      const depositNote = elements.profitMode.value === "raw"
        ? t("profit.noFees")
        : elements.profitMode.value === "enhanced"
          ? t("profit.noDepositFee")
          : elements.profitMode.value === "smart"
            ? t("profit.withDepositFee")
            : elements.profitUseDepositFee.checked
              ? t("profit.withDepositFee")
              : t("profit.noDepositFee");
      const sellMode = bestOpportunity.sell_mode === "fast_buy" ? t("profit.fastBuySale") : t("profit.askSale");
      profit.title = t("profit.tooltip", { name: bestOpportunity.market_hash_name, mode: t(PROFIT_MODE_UI[elements.profitMode.value].titleKey), sellMode, deposit: depositLabel, withdraw: withdrawLabel, depositNote });
      bottom.append(profit);
    } else if (!state.pricesPending && elements.profitMode.value === "quick_flip") {
      bottom.append(element("small", "quality-profit is-neutral", t("quality.fastBuyUnavailable")));
    }
    bottom.append(element("small", "quality-types", [...new Set(types)].join(" · ")));
    card.append(top, imageWrap, bottom);
    card.addEventListener("click", () => openQualityModal(quality));
    elements.qualityGrid.append(card);
  });
}

function qualityMatchesPreselection(quality) {
  if (elements.preWearFilter.value !== "any" && quality.wear !== elements.preWearFilter.value) return false;
  if (!quality.variants.some(variantMatchesPreselection)) return false;
  const [wearMin, wearMax] = WEAR_FLOAT_RANGES[quality.wear] || [0, 1];
  const qualityMin = Math.max(wearMin, state.selectedSkin?.min_float ?? 0);
  const qualityMax = Math.min(wearMax, state.selectedSkin?.max_float ?? 1);
  const requestedMin = numberOrNull(elements.preMinFloat.value) ?? 0;
  const requestedMax = numberOrNull(elements.preMaxFloat.value) ?? 1;
  return qualityMin <= requestedMax && qualityMax >= requestedMin;
}

function variantMatchesPreselection(item) {
  const variant = elements.preVariantFilter.value;
  if (variant === "normal") return !item.stattrak && !item.souvenir;
  if (variant === "stattrak") return Boolean(item.stattrak);
  if (variant === "souvenir") return Boolean(item.souvenir);
  return true;
}

function openQualityModal(quality) {
  state.selectedQuality = quality;
  syncPreselectionToModal();
  elements.browserTitle.textContent = state.selectedSkin.name;
  elements.browserSubtitle.textContent = `${quality.wear} · ${WEAR_CODES[quality.wear] || ""}`;
  updateMarketplaceUi();
  showBrowserView();
  if (!elements.listingModal.open) elements.listingModal.showModal();
  loadListings();
}

function showBrowserView() {
  elements.modalBrowser.hidden = false;
  elements.modalDetail.hidden = true;
}

function showDetailView() {
  elements.modalBrowser.hidden = true;
  elements.modalDetail.hidden = false;
}

function validateMarketFilters() {
  const minFloat = numberOrNull(elements.minFloat.value), maxFloat = numberOrNull(elements.maxFloat.value);
  const minPrice = numberOrNull(elements.minPrice.value), maxPrice = numberOrNull(elements.maxPrice.value);
  let message = "";
  if (minFloat != null && maxFloat != null && minFloat > maxFloat) message = t("filters.floatOrderError");
  if (!message && minPrice != null && maxPrice != null && minPrice > maxPrice) message = t("filters.priceOrderError");
  elements.filterError.textContent = message;
  elements.filterError.hidden = !message;
  elements.preFilterError.textContent = message;
  elements.preFilterError.hidden = !message;
  return !message;
}

const FILTER_FIELD_PAIRS = [
  ["preVariantFilter", "variantFilter"],
  ["preMinFloat", "minFloat"], ["preMaxFloat", "maxFloat"],
  ["preMinPrice", "minPrice"], ["preMaxPrice", "maxPrice"],
  ["preHasStickers", "hasStickers"], ["preHasCharm", "hasCharm"],
];

function copyControlValue(source, target) {
  if (source.type === "checkbox") target.checked = source.checked;
  else target.value = source.value;
}

function syncPreselectionToModal() {
  elements.marketplaceSelect.value = elements.preMarketplaceSelect.value;
  elements.sortSelect.value = elements.preSortSelect.value;
  FILTER_FIELD_PAIRS.forEach(([preId, modalId]) => copyControlValue(elements[preId], elements[modalId]));
  updateMarketplaceUi();
}

function syncModalToPreselection() {
  elements.preMarketplaceSelect.value = elements.marketplaceSelect.value;
  elements.preSortSelect.value = elements.sortSelect.value;
  FILTER_FIELD_PAIRS.forEach(([preId, modalId]) => copyControlValue(elements[modalId], elements[preId]));
  updatePreselectionMarketplaceUi();
  updateActiveFilterCount();
}

function marketParams() {
  const params = new URLSearchParams({
    sort_by: elements.sortSelect.value,
    wear: WEAR_SLUGS[state.selectedQuality.wear],
    limit: "30",
  });
  if (elements.variantFilter.value !== "any") params.set("variant", elements.variantFilter.value);
  if (elements.minFloat.value !== "") params.set("min_float", elements.minFloat.value);
  if (elements.maxFloat.value !== "") params.set("max_float", elements.maxFloat.value);
  if (elements.minPrice.value !== "") params.set("min_price_cents", String(Math.round(Number(elements.minPrice.value) * 100)));
  if (elements.maxPrice.value !== "") params.set("max_price_cents", String(Math.round(Number(elements.maxPrice.value) * 100)));
  if (elements.hasStickers.checked) params.set("has_stickers", "true");
  if (elements.hasCharm.checked) params.set("has_charm", "true");
  return params;
}

async function loadListings() {
  if (!state.selectedSkin || !state.selectedQuality || !validateMarketFilters()) return;
  state.marketRequest?.abort();
  const request = new AbortController();
  state.marketRequest = request;
  const marketLabel = state.selectedMarketplace === "csgomarket" ? "CSGO Market" : "CSFloat";
  showMessage(elements.listingsMessage, t("listings.loading", { market: marketLabel }), "loading");
  elements.listingGrid.replaceChildren();
  updateActiveFilterCount();
  try {
    const path = `/api/skins/${encodeURIComponent(state.selectedSkin.id)}/market/${state.selectedMarketplace}/listings?${marketParams()}`;
    const result = await api.get(path, request.signal);
    if (request !== state.marketRequest) return;
    state.listings = result.listings || [];
    if (result.error) showMessage(elements.listingsMessage, result.error, "error");
    else if (!state.listings.length) showMessage(elements.listingsMessage, t("listings.none"), "empty");
    else {
      elements.listingsMessage.hidden = true;
      renderListingsGrid();
    }
    elements.resultCount.textContent = t("listings.count", { count: formatCount(state.listings.length) });
  } catch (error) {
    if (error.name !== "AbortError") showMessage(elements.listingsMessage, error.message || t("listings.error", { market: marketLabel }), "error");
  }
}

function renderListingsGrid() {
  elements.listingGrid.replaceChildren();
  state.listings.forEach((listing) => {
    listing.marketplace_id ||= state.selectedMarketplace;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "listing-card";
    card.setAttribute("aria-label", `${listing.market_hash_name}, ${formatUsd(listing.price_cents)}`);
    const top = element("div", "card-top");
    top.append(element("span", "wear-chip", WEAR_CODES[listing.wear_name] || listing.wear_name || "—"));
    top.append(element("span", "market-chip", listing.marketplace_id === "csgomarket" ? "CSGO" : "CSFloat"));
    if (listing.stattrak) top.append(element("span", "variant-chip stattrak", "StatTrak™"));
    if (listing.souvenir) top.append(element("span", "variant-chip souvenir", "Souvenir"));
    if (listing.charms?.length) top.append(element("span", "variant-chip charm-chip", "Charm"));
    if (listing.deal_percent > 0) top.append(element("strong", "deal-chip", `-${formatPercent(listing.deal_percent)}`));
    const imageWrap = element("div", "card-image");
    const image = document.createElement("img");
    image.src = listing.image_url || state.selectedSkin.image_url || "";
    image.loading = "lazy";
    imageWrap.append(image);
    const attachments = element("div", "attachment-lines");
    attachments.append(renderAttachmentRow(listing.stickers, "sticker", t("listings.noStickers"), 4));
    if (listing.charms?.length) attachments.append(renderAttachmentRow(listing.charms, "charm", "", 2));
    const copy = element("div", "card-copy");
    copy.append(element("strong", "card-price", formatUsd(listing.price_cents)), element("span", "card-float", `Float ${formatFloat(listing.float_value)}`));
    if (listing.predicted_price_cents && listing.predicted_price_cents !== listing.price_cents) copy.append(element("small", "reference-price", t("listings.valuation", { price: formatUsd(listing.predicted_price_cents) })));
    card.append(top, imageWrap, attachments, copy);
    card.addEventListener("click", () => openListingDetail(listing));
    elements.listingGrid.append(card);
  });
}

function renderAttachmentRow(items, type, emptyLabel, limit = 5) {
  const row = element("div", `sticker-row ${type}-row`);
  if (!items?.length) {
    if (emptyLabel) row.append(element("span", "no-stickers", emptyLabel));
    return row;
  }
  items.slice(0, limit).forEach((attachment) => {
    const item = element("span", `sticker ${type}`);
    item.tabIndex = 0;
    if (attachment.icon_url) {
      const image = document.createElement("img");
      image.src = attachment.icon_url;
      image.loading = "lazy";
      item.append(image);
    } else item.textContent = type === "charm" ? "C" : "S";
    const tooltip = element("span", "sticker-tooltip");
    tooltip.append(
      element("strong", "", attachment.name || (type === "charm" ? "Charm" : t("attachments.sticker"))),
      element("span", "", attachment.csfloat_price_cents == null ? t("attachments.priceUnavailable") : `CSFloat · ${formatUsd(attachment.csfloat_price_cents)}`),
      element("small", "", attachment.csfloat_quantity == null ? "" : t("attachments.active", { count: formatCount(attachment.csfloat_quantity) })),
    );
    item.append(tooltip);
    row.append(item);
  });
  if (items.length > limit) row.append(element("span", "sticker-more", `+${items.length - limit}`));
  return row;
}

async function openListingDetail(listing) {
  state.detailRequest?.abort();
  state.selectedListing = listing;
  state.detailResults = null;
  renderModalListing(listing);
  elements.modalAnalytics.replaceChildren(modalLoading());
  showDetailView();
  if (!listing.variant_id) {
    elements.modalAnalytics.replaceChildren(notice(t("detail.variantMissing"), true));
    return;
  }
  const request = new AbortController();
  state.detailRequest = request;
  const selectedMarketplace = listing.marketplace_id || state.selectedMarketplace;
  const quickSellRequest = selectedMarketplace === "csfloat" && listing.listing_id
    ? api.get(`/api/listings/${encodeURIComponent(listing.listing_id)}/market/csfloat/quick-sell`, request.signal)
    : Promise.resolve(null);
  const [csfloatResult, csgomarketResult, quickSellResult] = await Promise.allSettled([
    api.get(`/api/variants/${encodeURIComponent(listing.variant_id)}/market/csfloat`, request.signal),
    api.get(`/api/variants/${encodeURIComponent(listing.variant_id)}/market/csgomarket`, request.signal),
    quickSellRequest,
  ]);
  if (request !== state.detailRequest) return;
  const aborted = [csfloatResult, csgomarketResult].some(
    (result) => result.status === "rejected" && result.reason?.name === "AbortError",
  );
  if (aborted) return;
  if (csfloatResult.status === "fulfilled" && quickSellResult.status === "fulfilled" && quickSellResult.value) {
    csfloatResult.value.quick_sell = quickSellResult.value;
  }
  state.detailResults = {
    csfloat: normalizeSettledDetail(csfloatResult),
    csgomarket: normalizeSettledDetail(csgomarketResult),
  };
  renderModalComparison(listing, state.detailResults);
}

function normalizeSettledDetail(result) {
  if (result.status === "fulfilled") return { details: result.value, error: null };
  return { details: null, error: result.reason?.message || t("detail.marketError") };
}

function renderModalListing(listing) {
  const imageWrap = element("div", "modal-image");
  const image = document.createElement("img");
  image.src = listing.image_url || state.selectedSkin.image_url || "";
  image.alt = listing.market_hash_name || state.selectedSkin.name;
  imageWrap.append(image);
  const facts = element("dl", "listing-facts");
  appendFact(facts, "Float", formatFloat(listing.float_value));
  appendFact(facts, "Paint seed", listing.paint_seed ?? "—");
  appendFact(facts, "Paint index", listing.paint_index ?? "—");
  if (listing.collection) appendFact(facts, t("detail.collection"), listing.collection);
  if (listing.predicted_price_cents) appendFact(facts, t("detail.valuation"), formatUsd(listing.predicted_price_cents));
  if (listing.deal_percent != null) appendFact(facts, t("detail.valuationDifference"), `${listing.deal_percent > 0 ? "−" : "+"}${formatPercent(Math.abs(listing.deal_percent))}`);
  const marketplace = listing.marketplace_id || state.selectedMarketplace;
  const marketLabel = marketplace === "csgomarket" ? "CSGO Market" : "CSFloat";
  const link = element("a", "csfloat-link", t("detail.openListing", { market: marketLabel }));
  link.href = listing.item_url; link.target = "_blank"; link.rel = "noopener noreferrer";
  const attachments = element("div", "modal-stickers");
  attachments.append(element("span", "", t("detail.stickers")), renderAttachmentRow(listing.stickers, "sticker", t("detail.none"), 5));
  if (listing.charms?.length) attachments.append(element("span", "", "Charm"), renderAttachmentRow(listing.charms, "charm", "", 2));
  elements.modalListing.replaceChildren(
    element("p", "modal-overline", t("detail.selectedListing")), element("h2", "", listing.market_hash_name || state.selectedSkin.name),
    imageWrap, element("strong", "modal-price", formatUsd(listing.price_cents)), facts, attachments, link,
  );
}

function renderModalComparison(listing, results) {
  const header = element("div", "analytics-header comparison-header");
  header.append(
    element("div", "", t("detail.comparison")),
    element("h2", "", listing.market_hash_name || state.selectedSkin.name),
  );
  const grid = element("div", "market-analytics-grid");
  grid.append(
    renderMarketplaceAnalytics("csfloat", "CSFloat", results.csfloat),
    renderMarketplaceAnalytics("csgomarket", "CSGO Market", results.csgomarket),
  );
  elements.modalAnalytics.replaceChildren(header, renderDetailProfitControls(), renderDirectionSummary(listing), grid);
}

function detailSelect(label, options, value, onChange, disabled = false) {
  const wrap = element("label", "detail-control");
  wrap.append(element("span", "", label));
  const select = document.createElement("select");
  options.forEach(([optionValue, optionLabel]) => {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionLabel;
    select.append(option);
  });
  select.value = value;
  select.disabled = disabled;
  select.addEventListener("change", () => onChange(select.value));
  wrap.append(select);
  return wrap;
}

function renderDetailProfitControls() {
  const mode = elements.profitMode.value;
  const quickFlip = mode === "quick_flip";
  const automaticBuy = elements.profitBuyMarketplace.value === "all";
  const raw = mode === "raw";
  const enhanced = mode === "enhanced";
  elements.profitAutoSellOption.disabled = !automaticBuy;
  if (automaticBuy) elements.profitSellMarketplace.value = "auto";
  else if (elements.profitSellMarketplace.value === "auto") {
    elements.profitSellMarketplace.value = elements.profitBuyMarketplace.value === "csfloat" ? "csgomarket" : "csfloat";
  }
  const sellOptions = automaticBuy
    ? [["auto", t("marketplace.auto")], ["csgomarket", "CSGO Market"], ["csfloat", "CSFloat"]]
    : [["csgomarket", "CSGO Market"], ["csfloat", "CSFloat"]];
  const section = element("section", "detail-profit-controls");
  const copy = element("div", "detail-profit-copy");
  copy.append(element("span", "", t("detail.calculation")), element("strong", "", t(PROFIT_MODE_UI[mode].titleKey)), element("small", "", t("detail.calculationHint")));
  section.append(
    copy,
    detailSelect(t("profit.mode"), [["raw", "Raw"], ["smart", "Smart"], ["enhanced", "Enhanced"], ["quick_flip", "Quick flip"]], mode, (value) => {
      elements.profitMode.value = value;
      updateProfitModeUi();
      recalculateProfit();
    }),
    detailSelect(t("profit.buyOn"), [["all", t("marketplace.all")], ["csfloat", "CSFloat"], ["csgomarket", "CSGO Market"]], elements.profitBuyMarketplace.value, (value) => {
      elements.profitBuyMarketplace.value = value;
      keepProfitDirectionDistinct(elements.profitBuyMarketplace);
      updateProfitModeUi();
      recalculateProfit();
    }, quickFlip),
  );
  const swap = element("button", "profit-swap detail-profit-swap", "⇄");
  swap.type = "button";
  swap.title = t("profit.swapTitle");
  swap.setAttribute("aria-label", t("profit.swapAria"));
  swap.disabled = quickFlip || automaticBuy;
  swap.addEventListener("click", swapProfitMarkets);
  section.append(
    swap,
    detailSelect(t("profit.sellOn"), sellOptions, elements.profitSellMarketplace.value, (value) => {
      elements.profitSellMarketplace.value = value;
      keepProfitDirectionDistinct(elements.profitSellMarketplace);
      recalculateProfit();
    }, quickFlip || automaticBuy),
    detailSelect(t("profit.deposit"), [["crypto", "Crypto"], ["card", t("payment.card")]], elements.profitDepositMethod.value, (value) => {
      elements.profitDepositMethod.value = value;
      recalculateProfit();
    }, raw || enhanced),
    detailSelect(t("profit.withdraw"), [["crypto", "Crypto"], ["card", t("payment.card")]], elements.profitWithdrawMethod.value, (value) => {
      elements.profitWithdrawMethod.value = value;
      recalculateProfit();
    }, raw),
  );
  if (quickFlip) {
    const checkbox = element("label", "detail-profit-checkbox");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = elements.profitUseDepositFee.checked;
    input.addEventListener("change", () => {
      elements.profitUseDepositFee.checked = input.checked;
      recalculateProfit();
    });
    checkbox.append(input, element("span", "", t("profit.quickDeposit")));
    section.append(checkbox);
  }
  return section;
}

function renderDirectionSummary(listing) {
  const quickFlip = elements.profitMode.value === "quick_flip";
  const automaticBuy = elements.profitBuyMarketplace.value === "all";
  let buyMarketplace = elements.profitBuyMarketplace.value;
  let sellMarketplace = elements.profitSellMarketplace.value;
  const labels = { csfloat: "CSFloat", csgomarket: "CSGO Market" };
  const comparison = state.prices.get(listing.variant_id);
  const opportunity = quickFlip || automaticBuy
    ? [...(comparison?.opportunities || [])].sort((left, right) => (
      left.buy_price_cents - right.buy_price_cents || right.profit_cents - left.profit_cents
    ))[0]
    : (comparison?.opportunities || []).find((item) => (
      item.buy_marketplace === buyMarketplace && item.sell_marketplace === sellMarketplace
    ));
  if (opportunity) {
    buyMarketplace = opportunity.buy_marketplace;
    sellMarketplace = opportunity.sell_marketplace;
  }
  const summary = element("section", "direction-summary");
  const title = element("div", "direction-summary-title");
  title.append(
    element("span", "", quickFlip ? t("detail.autoDirection") : automaticBuy ? t("detail.cheapestDirection") : t("detail.direction")),
    element("strong", "", opportunity ? `${labels[buyMarketplace]} → ${labels[sellMarketplace]}` : t("marketplace.all")),
  );
  if (!quickFlip && !automaticBuy) {
    const swapButton = element("button", "direction-swap", t("detail.swap"));
    swapButton.type = "button";
    swapButton.addEventListener("click", () => {
      swapProfitMarkets();
    });
    title.append(swapButton);
  }
  summary.append(title);
  if (!opportunity) {
    summary.append(element("small", "", t("detail.notEnoughPrices")));
    return summary;
  }
  const sign = opportunity.profit_cents > 0 ? "+" : "";
  summary.append(
    directionMetric(t("detail.buy"), formatUsd(opportunity.buy_price_cents)),
    directionMetric(t("detail.sell"), formatUsd(opportunity.sell_price_cents)),
    directionMetric(t("detail.netProfit"), `${sign}${formatUsd(opportunity.profit_cents)}`, opportunity.profit_cents),
    directionMetric("Cash ROI", formatPercent(opportunity.cash_roi_percent), opportunity.profit_cents),
  );
  return summary;
}

function directionMetric(label, value, signedValue = 0) {
  const tone = signedValue > 0 ? " is-positive" : signedValue < 0 ? " is-negative" : "";
  const metric = element("div", `direction-metric${tone}`);
  metric.append(element("span", "", label), element("strong", "", value));
  return metric;
}

function renderMarketplaceAnalytics(marketplaceId, label, result) {
  const panel = element("section", `market-analytics-panel market-${marketplaceId}`);
  const panelHeader = element("header", "market-panel-header");
  panelHeader.append(element("span", "", t("analytics.marketplace")), element("h3", "", label));
  const metricsSlot = element("div", "analytics-slot metrics-slot");
  const linkSlot = element("div", "analytics-slot link-slot");
  const chartSlot = element("div", "analytics-slot chart-slot");
  const statsNoteSlot = element("div", "analytics-slot stats-note-slot");
  const quickOrdersSlot = element("div", "analytics-slot quick-orders-slot");
  const quickNoteSlot = element("div", "analytics-slot quick-note-slot");
  const listingsSlot = element("div", "analytics-slot listings-slot");
  const salesSlot = element("div", "analytics-slot sales-slot");
  panel.append(panelHeader, metricsSlot, linkSlot, chartSlot, statsNoteSlot, quickOrdersSlot, quickNoteSlot, listingsSlot, salesSlot);
  if (result.error || !result.details) {
    metricsSlot.append(notice(translateProviderText(result.error) || t("analytics.unavailable"), true));
    return panel;
  }

  const details = result.details;
  const stats = details.stats || {}, quick = details.quick_sell || {};
  const liquidityLabel = { high: t("analytics.high"), medium: t("analytics.medium"), low: t("analytics.low") }[stats.liquidity_label] || t("common.noData");
  const metrics = element("div", "metrics-grid market-metrics-grid");
  [
    [t("analytics.minPrice"), formatNullableUsd(details.overview?.price_cents), t("analytics.exactVariant")],
    [t("analytics.quickSale"), formatNullableUsd(quick.best_price_cents), quick.discount_percent == null ? t("analytics.noOrder") : t("analytics.askDiscount", { percent: formatPercent(quick.discount_percent) })],
    [t("analytics.liquidity"), stats.liquidity_score == null ? t("common.noData") : `${liquidityLabel} · ${stats.liquidity_score}%`, t("analytics.marketScore")],
    [t("analytics.salesPerDay"), stats.sales_per_day == null ? t("common.noData") : Number(stats.sales_per_day).toFixed(2), translateProviderText(stats.sales_scope) || ""],
    [t("analytics.listings"), details.overview?.active_listings ?? "—", t("analytics.activeNow")],
    [t("analytics.bidDepth"), quick.near_bid_depth ?? stats.near_bid_depth ?? "—", t("analytics.withinFive")],
  ].forEach(([metricLabel, value, hint]) => {
    const metric = element("div", "metric");
    metric.append(element("span", "", metricLabel), element("strong", "", String(value)), element("small", "", hint));
    metrics.append(metric);
  });
  metricsSlot.append(metrics);
  if (details.overview?.item_url) {
    const link = element("a", "market-panel-link", t("analytics.open", { market: label }));
    link.href = details.overview.item_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    linkSlot.append(link);
  }
  if (details.sales?.length) chartSlot.append(renderSalesChart(details.sales.slice(0, 20)));
  if (stats.sales_float_note) statsNoteSlot.append(notice(translateProviderText(stats.sales_float_note)));
  const saleFloat = (row) => {
    if (row.float_value != null) return formatFloat(row.float_value);
    return marketplaceId === "csgomarket" ? t("analytics.apiNoFloat") : "—";
  };
  quickOrdersSlot.append(sectionTable(t("analytics.quickOrders"), quick.orders || [], [[t("analytics.price"), (row) => formatUsd(row.price_cents)], [t("analytics.quantity"), (row) => formatCount(row.quantity)], [t("analytics.conditions"), formatOrderConditions]], translateProviderText(quick.error) || t("analytics.noQuickOrders")));
  quickNoteSlot.append(notice(translateProviderText(quick.note) || t("analytics.orderNote")));
  listingsSlot.append(sectionTable(t("analytics.activeListings"), (details.listings || []).slice(0, 10), [[t("analytics.price"), (row) => formatUsd(row.price_cents)], ["Float", (row) => formatFloat(row.float_value)], [t("analytics.seed"), (row) => row.paint_seed ?? "—"], [t("analytics.stickers"), (row) => row.stickers?.length || "—"]], translateProviderText(details.listings_error) || t("analytics.noActiveListings")));
  salesSlot.append(sectionTable(t("analytics.salesHistory"), (details.sales || []).slice(0, 10), [[t("analytics.date"), (row) => formatDate(row.sold_at)], [t("analytics.price"), (row) => formatNullableUsd(row.price_cents)], ["Float", saleFloat]], translateProviderText(details.sales_error) || t("analytics.noSales")));
  return panel;
}

function renderSalesChart(sales) {
  const values = sales.map((sale) => sale.price_cents).filter(Number.isFinite).reverse();
  const section = element("section", "chart-section");
  const heading = element("div", "table-heading");
  heading.append(element("h3", "", t("analytics.salesTrend")), element("span", "", t("analytics.points", { count: values.length })));
  section.append(heading);
  if (values.length < 2) return section;
  const width = 800, height = 150, pad = 10, min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", t("analytics.chartAria"));
  const line = document.createElementNS(svg.namespaceURI, "polyline");
  line.setAttribute("points", values.map((value, index) => `${pad + index * ((width - pad * 2) / (values.length - 1))},${height - pad - ((value - min) / range) * (height - pad * 2)}`).join(" "));
  line.setAttribute("fill", "none"); line.setAttribute("stroke", "currentColor"); line.setAttribute("stroke-width", "3"); line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(line); section.append(svg); return section;
}

function sectionTable(title, rows, columns, emptyMessage) {
  const section = element("section", "data-section"), heading = element("div", "table-heading");
  heading.append(element("h3", "", title), element("span", "", rows.length ? t("analytics.records", { count: rows.length }) : "")); section.append(heading);
  if (!rows.length) { section.append(notice(emptyMessage)); return section; }
  const wrap = element("div", "table-wrap"), table = document.createElement("table"), head = document.createElement("thead"), headerRow = document.createElement("tr");
  table.className = `columns-${columns.length}`;
  columns.forEach(([label]) => headerRow.append(element("th", "", label))); head.append(headerRow);
  const body = document.createElement("tbody");
  rows.forEach((row) => { const tr = document.createElement("tr"); columns.forEach(([, getValue]) => tr.append(element("td", "", String(getValue(row))))); body.append(tr); });
  table.append(head, body); wrap.append(table); section.append(wrap); return section;
}

function updateActiveFilterCount() {
  const count = [elements.preWearFilter.value !== "any", elements.variantFilter.value !== "any", elements.minFloat.value, elements.maxFloat.value, elements.minPrice.value, elements.maxPrice.value, elements.hasStickers.checked, elements.hasCharm.checked].filter(Boolean).length;
  elements.activeFilterCount.textContent = String(count); elements.activeFilterCount.hidden = count === 0;
  elements.preActiveFilterCount.textContent = String(count); elements.preActiveFilterCount.hidden = count === 0;
}

function updateMarketplaceUi() {
  state.selectedMarketplace = elements.marketplaceSelect.value;
  const isCsgoMarket = state.selectedMarketplace === "csgomarket";
  elements.browserOverline.textContent = `${isCsgoMarket ? "CSGO MARKET" : "CSFLOAT"} · ${t("browser.listings")}`;
  elements.bestDealOption.disabled = isCsgoMarket;
  if (isCsgoMarket && elements.sortSelect.value === "best_deal") elements.sortSelect.value = "lowest_price";
  elements.hasCharm.disabled = isCsgoMarket;
  elements.hasCharm.closest("label").classList.toggle("is-disabled", isCsgoMarket);
  if (isCsgoMarket) elements.hasCharm.checked = false;
  syncModalToPreselection();
  updateActiveFilterCount();
}

function updatePreselectionMarketplaceUi() {
  const isCsgoMarket = elements.preMarketplaceSelect.value === "csgomarket";
  elements.preBestDealOption.disabled = isCsgoMarket;
  if (isCsgoMarket && elements.preSortSelect.value === "best_deal") elements.preSortSelect.value = "lowest_price";
  elements.preHasCharm.disabled = isCsgoMarket;
  elements.preHasCharm.closest("label").classList.toggle("is-disabled", isCsgoMarket);
  if (isCsgoMarket) elements.preHasCharm.checked = false;
}

async function recalculateProfit() {
  if (!state.selectedSkin) return;
  state.pricesPending = true;
  renderQualityCards();
  const summary = elements.modalAnalytics.querySelector(".direction-summary");
  if (!elements.modalDetail.hidden && summary) {
    summary.classList.add("is-loading");
    summary.setAttribute("aria-busy", "true");
  }
  await loadWearPrices();
  if (!elements.modalDetail.hidden && state.selectedListing && state.detailResults) {
    renderModalComparison(state.selectedListing, state.detailResults);
  }
}

function updateProfitModeUi() {
  const mode = elements.profitMode.value;
  const config = PROFIT_MODE_UI[mode];
  const quickFlip = mode === "quick_flip";
  const automaticBuy = elements.profitBuyMarketplace.value === "all";
  const raw = mode === "raw";
  const enhanced = mode === "enhanced";
  elements.profitModeTitle.textContent = t(config.titleKey);
  elements.profitModeNote.textContent = t(config.noteKey);
  elements.profitBuyMarketplace.disabled = quickFlip;
  elements.profitSellMarketplace.disabled = quickFlip || automaticBuy;
  elements.profitSwapMarkets.disabled = quickFlip || automaticBuy;
  elements.profitDepositMethod.disabled = raw || enhanced;
  elements.profitWithdrawMethod.disabled = raw;
  elements.profitUseDepositFee.disabled = !quickFlip;
  elements.profitDepositFeeControl.classList.toggle("is-disabled", !quickFlip);
}

function keepProfitDirectionDistinct(changedControl) {
  if (elements.profitBuyMarketplace.value === "all") {
    elements.profitSellMarketplace.value = "auto";
    return;
  }
  if (elements.profitSellMarketplace.value === "auto") {
    elements.profitSellMarketplace.value = elements.profitBuyMarketplace.value === "csfloat" ? "csgomarket" : "csfloat";
    return;
  }
  if (elements.profitBuyMarketplace.value !== elements.profitSellMarketplace.value) return;
  const otherMarketplace = changedControl.value === "csfloat" ? "csgomarket" : "csfloat";
  if (changedControl === elements.profitBuyMarketplace) elements.profitSellMarketplace.value = otherMarketplace;
  else elements.profitBuyMarketplace.value = otherMarketplace;
}

function swapProfitMarkets() {
  if (elements.profitBuyMarketplace.value === "all") return;
  const buyMarketplace = elements.profitBuyMarketplace.value;
  elements.profitBuyMarketplace.value = elements.profitSellMarketplace.value;
  elements.profitSellMarketplace.value = buyMarketplace;
  recalculateProfit();
}

function resetMarketFilters(reload = true) {
  elements.preWearFilter.value = "any";
  elements.variantFilter.value = "any";
  [elements.minFloat, elements.maxFloat, elements.minPrice, elements.maxPrice].forEach((input) => { input.value = ""; });
  elements.hasStickers.checked = false; elements.hasCharm.checked = false;
  elements.filterError.hidden = true; elements.preFilterError.hidden = true;
  syncModalToPreselection();
  updateActiveFilterCount();
  if (state.selectedSkin) renderQualityCards();
  if (reload && state.selectedQuality) loadListings();
}

function modalLoading() { const wrap = element("div", "modal-loading"); wrap.append(element("span"), element("span"), element("span")); return wrap; }
function notice(message, isError = false) { return element("p", `notice${isError ? " is-error" : ""}`, message); }
function showMessage(target, message, type) { target.textContent = message; target.className = `listings-message is-${type}`; target.hidden = false; }
function setSearchHint(message, isError = false) { elements.searchHint.textContent = message; elements.searchHint.classList.toggle("is-error", isError); }
function setMarketStatus(message, type) { elements.marketStatus.textContent = message; elements.marketStatus.className = `is-${type}`; }
function closeSuggestions() { elements.suggestions.hidden = true; elements.searchInput.setAttribute("aria-expanded", "false"); state.selectedIndex = -1; }
function moveSelection(direction) {
  if (elements.suggestions.hidden || !state.results.length) return;
  state.selectedIndex = (state.selectedIndex + direction + state.results.length) % state.results.length;
  [...elements.suggestions.querySelectorAll("button")].forEach((button, index) => { const active = index === state.selectedIndex; button.classList.toggle("is-active", active); button.setAttribute("aria-selected", String(active)); if (active) button.scrollIntoView({ block: "nearest" }); });
}
function appendFact(list, label, value) { const wrap = document.createElement("div"); wrap.append(element("dt", "", label), element("dd", "", String(value))); list.append(wrap); }
function element(tag, className = "", text = null) { const node = document.createElement(tag); if (className) node.className = className; if (text !== null && text !== undefined) node.textContent = text; return node; }
function variantTypeLabel(variant) { return variant.stattrak ? "StatTrak™" : variant.souvenir ? "Souvenir" : t("filters.normalLabel"); }
function formatOrderConditions(order) { if (order.min_float == null && order.max_float == null) return t("analytics.noRestrictions"); return `Float ${order.min_float == null ? "0" : Number(order.min_float).toFixed(4)}—${order.max_float == null ? "1" : Number(order.max_float).toFixed(4)}`; }
function numberOrNull(value) { return value === "" ? null : Number(value); }
function formatFloat(value) { return value == null ? "—" : Number(value).toFixed(8); }
function formatNullableUsd(value) { return value == null ? t("common.noData") : formatUsd(value); }
function currentLocale() { return state.language === "en" ? "en-US" : "ru-RU"; }
function formatPercent(value) { return `${Number(value).toLocaleString(currentLocale(), { maximumFractionDigits: 1 })}%`; }
function formatCount(value) { return new Intl.NumberFormat(currentLocale()).format(value); }
function formatUsd(cents) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100); }
function formatDate(value) { const date = value ? new Date(value) : null; return !date || Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat(currentLocale(), { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date); }
function pluralizeVariants(count) {
  if (state.language === "en") return t(count === 1 ? "search.variants.one" : "search.variants.many", { count: formatCount(count) });
  const lastTwo = count % 100, last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 19) return t("search.variants.many", { count: formatCount(count) });
  if (last === 1) return t("search.variants.one", { count: formatCount(count) });
  if (last >= 2 && last <= 4) return t("search.variants.few", { count: formatCount(count) });
  return t("search.variants.many", { count: formatCount(count) });
}

elements.searchInput.addEventListener("input", scheduleSearch);
elements.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown") { event.preventDefault(); moveSelection(1); }
  if (event.key === "ArrowUp") { event.preventDefault(); moveSelection(-1); }
  if (event.key === "Enter" && state.selectedIndex >= 0) { event.preventDefault(); selectSkin(state.results[state.selectedIndex]); }
  if (event.key === "Escape") closeSuggestions();
});
[elements.weaponFilter, elements.rarityFilter, elements.collectionFilter].forEach((select) => select.addEventListener("change", runSearch));
elements.languageSelect.addEventListener("change", () => changeLanguage(elements.languageSelect.value));
elements.sortSelect.addEventListener("change", () => { syncModalToPreselection(); loadListings(); });
elements.marketplaceSelect.addEventListener("change", () => { updateMarketplaceUi(); loadListings(); });
elements.preMarketplaceSelect.addEventListener("change", () => { syncPreselectionToModal(); updatePreselectionMarketplaceUi(); });
elements.preSortSelect.addEventListener("change", syncPreselectionToModal);
elements.preWearFilter.addEventListener("change", () => {
  updateActiveFilterCount();
  if (state.selectedSkin) renderQualityCards();
});
elements.preFilterToggle.addEventListener("click", () => {
  const open = elements.preMarketFilters.hidden;
  elements.preMarketFilters.hidden = !open;
  elements.preFilterToggle.setAttribute("aria-expanded", String(open));
});
elements.preMarketFilters.addEventListener("submit", (event) => {
  event.preventDefault();
  syncPreselectionToModal();
  if (validateMarketFilters()) {
    if (state.selectedSkin) renderQualityCards();
    setSearchHint(t("filters.applied"));
  }
});
elements.preResetMarketFilters.addEventListener("click", () => {
  syncPreselectionToModal();
  resetMarketFilters(false);
});
elements.profitMode.addEventListener("change", () => { updateProfitModeUi(); recalculateProfit(); });
[elements.profitBuyMarketplace, elements.profitSellMarketplace].forEach((control) => {
  control.addEventListener("change", () => { keepProfitDirectionDistinct(control); updateProfitModeUi(); recalculateProfit(); });
});
elements.profitSwapMarkets.addEventListener("click", swapProfitMarkets);
[elements.profitDepositMethod, elements.profitWithdrawMethod, elements.profitUseDepositFee]
  .forEach((control) => control.addEventListener("change", recalculateProfit));
elements.filterToggle.addEventListener("click", () => { const open = elements.marketFilters.hidden; elements.marketFilters.hidden = !open; elements.filterToggle.setAttribute("aria-expanded", String(open)); });
elements.marketFilters.addEventListener("submit", (event) => { event.preventDefault(); syncModalToPreselection(); loadListings(); });
elements.resetMarketFilters.addEventListener("click", () => resetMarketFilters(true));
elements.detailBack.addEventListener("click", () => { state.detailRequest?.abort(); showBrowserView(); });
elements.modalClose.addEventListener("click", () => elements.listingModal.close());
elements.listingModal.addEventListener("click", (event) => { if (event.target === elements.listingModal) elements.listingModal.close(); });
elements.listingModal.addEventListener("close", () => { state.marketRequest?.abort(); state.detailRequest?.abort(); state.selectedListing = null; state.detailResults = null; showBrowserView(); });
document.addEventListener("click", (event) => { if (!elements.searchShell.contains(event.target)) closeSuggestions(); });
document.addEventListener("keydown", (event) => { if (event.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); elements.searchInput.focus(); } });

applyStaticLanguage();
updateProfitModeUi();
updatePreselectionMarketplaceUi();
initialize();
