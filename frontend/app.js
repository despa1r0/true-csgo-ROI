const elements = Object.fromEntries(
  [
    "catalogStatus", "searchShell", "searchInput", "suggestions", "searchHint",
    "weaponFilter", "rarityFilter", "collectionFilter", "marketView", "skinImage",
    "skinMeta", "skinName", "skinCollection", "marketStatus", "qualityGrid",
    "qualityMessage", "listingModal", "modalClose", "modalBrowser", "browserTitle",
    "browserSubtitle", "resultCount", "sortSelect", "filterToggle", "activeFilterCount",
    "marketFilters", "variantFilter", "minFloat", "maxFloat", "minPrice", "maxPrice",
    "hasStickers", "hasCharm", "resetMarketFilters", "filterError", "listingGrid",
    "listingsMessage", "modalDetail", "detailBack", "modalListing", "modalAnalytics",
    "suggestionTemplate",
  ].map((id) => [id, document.querySelector(`#${id}`)]),
);

const WEAR_SLUGS = {
  "Factory New": "factory-new", "Minimal Wear": "minimal-wear",
  "Field-Tested": "field-tested", "Well-Worn": "well-worn",
  "Battle-Scarred": "battle-scarred",
};
const WEAR_CODES = {
  "Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT",
  "Well-Worn": "WW", "Battle-Scarred": "BS",
};

const state = {
  results: [], selectedIndex: -1, selectedSkin: null, selectedQuality: null,
  listings: [], prices: new Map(), pricesPending: false, searchRequest: null,
  pricesRequest: null, marketRequest: null, detailRequest: null, debounce: null,
  searchCache: new Map(),
};

const api = {
  async get(path, signal) {
    const response = await fetch(path, { signal });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || `Ошибка запроса (${response.status})`);
    }
    return response.json();
  },
};

async function initialize() {
  try {
    const [health, filters] = await Promise.all([api.get("/api/health"), api.get("/api/catalog/filters")]);
    elements.catalogStatus.textContent = `${formatCount(health.catalogue.skins)} скинов`;
    fillSelect(elements.weaponFilter, filters.weapons || []);
    fillSelect(elements.rarityFilter, filters.rarities || []);
    fillSelect(elements.collectionFilter, filters.collections || []);
  } catch {
    elements.catalogStatus.textContent = "Каталог недоступен";
    elements.catalogStatus.classList.add("is-error");
    setSearchHint("Не удалось подключиться к базе данных", true);
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
    setSearchHint("Введите минимум 2 символа или выберите фильтр");
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
  setSearchHint("Ищем совпадения…");
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
      setSearchHint("Поиск временно недоступен", true);
    }
  } finally {
    if (request === state.searchRequest) elements.searchShell.classList.remove("is-loading");
  }
}

function searchResultLabel() {
  return state.results.length ? `Найдено: ${state.results.length}` : "Совпадений не найдено";
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
    node.querySelector("small").textContent = `${skin.weapon_name || "Предмет"} · ${pluralizeVariants(skin.variant_count)}`;
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
  setSearchHint("Загружаем качества…");
  try {
    state.selectedSkin = await api.get(`/api/skins/${encodeURIComponent(skin.id)}`);
    state.prices = new Map();
    state.pricesPending = true;
    renderSelectedSkin();
    elements.marketView.hidden = false;
    renderQualityCards();
    setSearchHint("Скин выбран");
    loadWearPrices();
  } catch (error) {
    setSearchHint(error.message || "Не удалось загрузить скин", true);
  }
}

function renderSelectedSkin() {
  const skin = state.selectedSkin;
  elements.skinImage.src = skin.image_url || "";
  elements.skinImage.alt = skin.name;
  elements.skinName.textContent = skin.name;
  elements.skinMeta.textContent = [skin.weapon_name, skin.rarity_name].filter(Boolean).join(" · ");
  elements.skinCollection.textContent = (skin.collections || []).map((item) => item.name).join(" · ") || "Вне коллекции";
}

async function loadWearPrices() {
  const skinId = state.selectedSkin.id;
  const request = new AbortController();
  state.pricesRequest = request;
  setMarketStatus("Обновляем цены…", "loading");
  try {
    const result = await api.get(`/api/skins/${encodeURIComponent(skinId)}/market/csfloat`, request.signal);
    if (request !== state.pricesRequest || state.selectedSkin?.id !== skinId) return;
    state.prices = new Map(result.variants.map((item) => [item.variant_id, item]));
    const firstError = result.variants.find((item) => item.error)?.error;
    const available = result.variants.filter((item) => item.listing).length;
    if (available) setMarketStatus(firstError ? "Цены из кэша" : "Цены актуальны", firstError ? "warning" : "ready");
    else if (firstError) setMarketStatus("Временный сбой CSFloat", "error");
    else setMarketStatus("Активных лотов нет", "muted");
  } catch (error) {
    if (error.name !== "AbortError") setMarketStatus("Временный сбой CSFloat", "error");
  } finally {
    if (request === state.pricesRequest) {
      state.pricesPending = false;
      renderQualityCards();
    }
  }
}

function renderQualityCards() {
  elements.qualityGrid.replaceChildren();
  const qualities = state.selectedSkin?.qualities || [];
  elements.qualityMessage.hidden = Boolean(qualities.length);
  if (!qualities.length) {
    showMessage(elements.qualityMessage, "Для скина не найдены варианты качества.", "empty");
    return;
  }
  qualities.forEach((quality) => {
    const priced = quality.variants
      .map((variant) => ({ variant, market: state.prices.get(variant.id) }))
      .filter((item) => item.market?.listing)
      .sort((left, right) => left.market.listing.price_cents - right.market.listing.price_cents);
    const cheapest = priced[0]?.market.listing;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "quality-card";
    const top = element("div", "quality-card-top");
    top.append(element("strong", "wear-code", WEAR_CODES[quality.wear] || "—"), element("span", "", quality.wear));
    const imageWrap = element("div", "quality-image");
    const image = document.createElement("img");
    image.src = quality.variants[0]?.image_url || state.selectedSkin.image_url || "";
    image.alt = "";
    imageWrap.append(image);
    const types = quality.variants.map(variantTypeLabel);
    const bottom = element("div", "quality-card-bottom");
    const price = element("strong", "quality-price");
    price.textContent = state.pricesPending ? "Цена…" : cheapest ? `от ${formatUsd(cheapest.price_cents)}` : "Нет цены";
    bottom.append(price, element("small", "", [...new Set(types)].join(" · ")));
    card.append(top, imageWrap, bottom);
    card.addEventListener("click", () => openQualityModal(quality));
    elements.qualityGrid.append(card);
  });
}

function openQualityModal(quality) {
  state.selectedQuality = quality;
  resetMarketFilters(false);
  elements.browserTitle.textContent = state.selectedSkin.name;
  elements.browserSubtitle.textContent = `${quality.wear} · ${WEAR_CODES[quality.wear] || ""}`;
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
  if (minFloat != null && maxFloat != null && minFloat > maxFloat) message = "Минимальный float больше максимального.";
  if (!message && minPrice != null && maxPrice != null && minPrice > maxPrice) message = "Минимальная цена больше максимальной.";
  elements.filterError.textContent = message;
  elements.filterError.hidden = !message;
  return !message;
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
  showMessage(elements.listingsMessage, "Загружаем актуальные лоты CSFloat…", "loading");
  elements.listingGrid.replaceChildren();
  updateActiveFilterCount();
  try {
    const path = `/api/skins/${encodeURIComponent(state.selectedSkin.id)}/market/csfloat/listings?${marketParams()}`;
    const result = await api.get(path, request.signal);
    if (request !== state.marketRequest) return;
    state.listings = result.listings || [];
    if (result.error) showMessage(elements.listingsMessage, `${result.error}. Это временная ошибка; повторите запрос чуть позже.`, "error");
    else if (!state.listings.length) showMessage(elements.listingsMessage, "Лотов с такими фильтрами сейчас нет.", "empty");
    else {
      elements.listingsMessage.hidden = true;
      renderListingsGrid();
    }
    elements.resultCount.textContent = `${formatCount(state.listings.length)} лотов`;
  } catch (error) {
    if (error.name !== "AbortError") showMessage(elements.listingsMessage, error.message || "Временная ошибка CSFloat", "error");
  }
}

function renderListingsGrid() {
  elements.listingGrid.replaceChildren();
  state.listings.forEach((listing) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "listing-card";
    card.setAttribute("aria-label", `${listing.market_hash_name}, ${formatUsd(listing.price_cents)}`);
    const top = element("div", "card-top");
    top.append(element("span", "wear-chip", WEAR_CODES[listing.wear_name] || listing.wear_name || "—"));
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
    attachments.append(renderAttachmentRow(listing.stickers, "sticker", "Без наклеек", 4));
    if (listing.charms?.length) attachments.append(renderAttachmentRow(listing.charms, "charm", "", 2));
    const copy = element("div", "card-copy");
    copy.append(element("strong", "card-price", formatUsd(listing.price_cents)), element("span", "card-float", `Float ${formatFloat(listing.float_value)}`));
    if (listing.predicted_price_cents && listing.predicted_price_cents !== listing.price_cents) copy.append(element("small", "reference-price", `Оценка ${formatUsd(listing.predicted_price_cents)}`));
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
      element("strong", "", attachment.name || (type === "charm" ? "Charm" : "Наклейка")),
      element("span", "", attachment.csfloat_price_cents == null ? "Цена недоступна" : `CSFloat · ${formatUsd(attachment.csfloat_price_cents)}`),
      element("small", "", attachment.csfloat_quantity == null ? "" : `${formatCount(attachment.csfloat_quantity)} активных`),
    );
    item.append(tooltip);
    row.append(item);
  });
  if (items.length > limit) row.append(element("span", "sticker-more", `+${items.length - limit}`));
  return row;
}

async function openListingDetail(listing) {
  state.detailRequest?.abort();
  renderModalListing(listing);
  elements.modalAnalytics.replaceChildren(modalLoading());
  showDetailView();
  if (!listing.variant_id) {
    elements.modalAnalytics.replaceChildren(notice("Для этого варианта нет соответствия в локальном каталоге.", true));
    return;
  }
  const request = new AbortController();
  state.detailRequest = request;
  try {
    const [detailsResult, quickSellResult] = await Promise.allSettled([
      api.get(`/api/variants/${encodeURIComponent(listing.variant_id)}/market/csfloat`, request.signal),
      api.get(`/api/listings/${encodeURIComponent(listing.listing_id)}/market/csfloat/quick-sell`, request.signal),
    ]);
    if (detailsResult.status === "rejected") throw detailsResult.reason;
    const details = detailsResult.value;
    if (quickSellResult.status === "fulfilled") details.quick_sell = quickSellResult.value;
    if (request === state.detailRequest) renderModalAnalytics(details);
  } catch (error) {
    if (error.name !== "AbortError") elements.modalAnalytics.replaceChildren(notice(error.message || "Не удалось загрузить аналитику", true));
  }
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
  if (listing.collection) appendFact(facts, "Коллекция", listing.collection);
  if (listing.predicted_price_cents) appendFact(facts, "Оценка CSFloat", formatUsd(listing.predicted_price_cents));
  if (listing.deal_percent != null) appendFact(facts, "Разница с оценкой", `${listing.deal_percent > 0 ? "−" : "+"}${formatPercent(Math.abs(listing.deal_percent))}`);
  const link = element("a", "csfloat-link", "Открыть лот на CSFloat ↗");
  link.href = listing.item_url; link.target = "_blank"; link.rel = "noopener noreferrer";
  const attachments = element("div", "modal-stickers");
  attachments.append(element("span", "", "Наклейки"), renderAttachmentRow(listing.stickers, "sticker", "Нет", 5));
  if (listing.charms?.length) attachments.append(element("span", "", "Charm"), renderAttachmentRow(listing.charms, "charm", "", 2));
  elements.modalListing.replaceChildren(
    element("p", "modal-overline", "ВЫБРАННЫЙ ЛОТ"), element("h2", "", listing.market_hash_name || state.selectedSkin.name),
    imageWrap, element("strong", "modal-price", formatUsd(listing.price_cents)), facts, attachments, link,
  );
}

function renderModalAnalytics(details) {
  const header = element("div", "analytics-header");
  header.append(element("div", "", "РЫНОЧНАЯ АНАЛИТИКА"), element("h2", "", details.market_hash_name));
  const metrics = element("div", "metrics-grid");
  const stats = details.stats || {}, quick = details.quick_sell || {};
  const liquidityLabel = { high: "Высокая", medium: "Средняя", low: "Низкая" }[stats.liquidity_label] || "Нет данных";
  [
    ["Мин. цена", formatNullableUsd(details.overview?.price_cents), "по точному варианту"],
    ["Быстрая продажа", formatNullableUsd(quick.best_price_cents), quick.discount_percent == null ? "нет заявки" : `−${formatPercent(quick.discount_percent)} к ask`],
    ["Ликвидность β", stats.liquidity_score == null ? "Нет данных" : `${liquidityLabel} · ${stats.liquidity_score}%`, "рыночный score"],
    ["Продаж в день", stats.sales_per_day == null ? "Нет данных" : Number(stats.sales_per_day).toFixed(2), stats.sales_scope || ""],
    ["Лотов", details.overview?.active_listings ?? "—", "активно сейчас"],
    ["Глубина bid", quick.near_bid_depth ?? stats.near_bid_depth ?? "—", "в пределах 5%"],
  ].forEach(([label, value, hint]) => {
    const metric = element("div", "metric");
    metric.append(element("span", "", label), element("strong", "", String(value)), element("small", "", hint));
    metrics.append(metric);
  });
  elements.modalAnalytics.replaceChildren(header, metrics);
  if (details.sales?.length) elements.modalAnalytics.append(renderSalesChart(details.sales.slice(0, 20)));
  elements.modalAnalytics.append(
    sectionTable("Заявки на быструю продажу", quick.orders || [], [["Цена", (row) => formatUsd(row.price_cents)], ["Количество", (row) => formatCount(row.quantity)], ["Условия", formatOrderConditions]], quick.error || "Подходящих заявок сейчас нет"),
    notice(quick.note || "Заявки зависят от float и свойств конкретного предмета."),
    sectionTable("10 активных позиций", (details.listings || []).slice(0, 10), [["Цена", (row) => formatUsd(row.price_cents)], ["Float", (row) => formatFloat(row.float_value)], ["Seed", (row) => row.paint_seed ?? "—"], ["Наклейки", (row) => row.stickers?.length || "—"], ["Charm", (row) => row.charms?.length ? "Да" : "—"]], details.listings_error || "Активных позиций нет"),
    sectionTable("История продаж", (details.sales || []).slice(0, 10), [["Дата", (row) => formatDate(row.sold_at)], ["Цена", (row) => formatNullableUsd(row.price_cents)], ["Float", (row) => formatFloat(row.float_value)]], details.sales_error || "История продаж недоступна"),
  );
}

function renderSalesChart(sales) {
  const values = sales.map((sale) => sale.price_cents).filter(Number.isFinite).reverse();
  const section = element("section", "chart-section");
  const heading = element("div", "table-heading");
  heading.append(element("h3", "", "Динамика последних продаж"), element("span", "", `${values.length} точек`));
  section.append(heading);
  if (values.length < 2) return section;
  const width = 800, height = 150, pad = 10, min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "График последних продаж");
  const line = document.createElementNS(svg.namespaceURI, "polyline");
  line.setAttribute("points", values.map((value, index) => `${pad + index * ((width - pad * 2) / (values.length - 1))},${height - pad - ((value - min) / range) * (height - pad * 2)}`).join(" "));
  line.setAttribute("fill", "none"); line.setAttribute("stroke", "currentColor"); line.setAttribute("stroke-width", "3"); line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(line); section.append(svg); return section;
}

function sectionTable(title, rows, columns, emptyMessage) {
  const section = element("section", "data-section"), heading = element("div", "table-heading");
  heading.append(element("h3", "", title), element("span", "", rows.length ? `${rows.length} записей` : "")); section.append(heading);
  if (!rows.length) { section.append(notice(emptyMessage)); return section; }
  const wrap = element("div", "table-wrap"), table = document.createElement("table"), head = document.createElement("thead"), headerRow = document.createElement("tr");
  columns.forEach(([label]) => headerRow.append(element("th", "", label))); head.append(headerRow);
  const body = document.createElement("tbody");
  rows.forEach((row) => { const tr = document.createElement("tr"); columns.forEach(([, getValue]) => tr.append(element("td", "", String(getValue(row))))); body.append(tr); });
  table.append(head, body); wrap.append(table); section.append(wrap); return section;
}

function updateActiveFilterCount() {
  const count = [elements.variantFilter.value !== "any", elements.minFloat.value, elements.maxFloat.value, elements.minPrice.value, elements.maxPrice.value, elements.hasStickers.checked, elements.hasCharm.checked].filter(Boolean).length;
  elements.activeFilterCount.textContent = String(count); elements.activeFilterCount.hidden = count === 0;
}

function resetMarketFilters(reload = true) {
  elements.variantFilter.value = "any";
  [elements.minFloat, elements.maxFloat, elements.minPrice, elements.maxPrice].forEach((input) => { input.value = ""; });
  elements.hasStickers.checked = false; elements.hasCharm.checked = false; elements.filterError.hidden = true;
  updateActiveFilterCount();
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
function variantTypeLabel(variant) { return variant.stattrak ? "StatTrak™" : variant.souvenir ? "Souvenir" : "Обычный"; }
function formatOrderConditions(order) { if (order.min_float == null && order.max_float == null) return "Без ограничений"; return `Float ${order.min_float == null ? "0" : Number(order.min_float).toFixed(4)}—${order.max_float == null ? "1" : Number(order.max_float).toFixed(4)}`; }
function numberOrNull(value) { return value === "" ? null : Number(value); }
function formatFloat(value) { return value == null ? "—" : Number(value).toFixed(8); }
function formatNullableUsd(value) { return value == null ? "Нет данных" : formatUsd(value); }
function formatPercent(value) { return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`; }
function formatCount(value) { return new Intl.NumberFormat("ru-RU").format(value); }
function formatUsd(cents) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100); }
function formatDate(value) { const date = value ? new Date(value) : null; return !date || Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date); }
function pluralizeVariants(count) { const lastTwo = count % 100, last = count % 10; if (lastTwo >= 11 && lastTwo <= 19) return `${count} вариантов`; if (last === 1) return `${count} вариант`; if (last >= 2 && last <= 4) return `${count} варианта`; return `${count} вариантов`; }

elements.searchInput.addEventListener("input", scheduleSearch);
elements.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown") { event.preventDefault(); moveSelection(1); }
  if (event.key === "ArrowUp") { event.preventDefault(); moveSelection(-1); }
  if (event.key === "Enter" && state.selectedIndex >= 0) { event.preventDefault(); selectSkin(state.results[state.selectedIndex]); }
  if (event.key === "Escape") closeSuggestions();
});
[elements.weaponFilter, elements.rarityFilter, elements.collectionFilter].forEach((select) => select.addEventListener("change", runSearch));
elements.sortSelect.addEventListener("change", loadListings);
elements.filterToggle.addEventListener("click", () => { const open = elements.marketFilters.hidden; elements.marketFilters.hidden = !open; elements.filterToggle.setAttribute("aria-expanded", String(open)); });
elements.marketFilters.addEventListener("submit", (event) => { event.preventDefault(); loadListings(); });
elements.resetMarketFilters.addEventListener("click", () => resetMarketFilters(true));
elements.detailBack.addEventListener("click", () => { state.detailRequest?.abort(); showBrowserView(); });
elements.modalClose.addEventListener("click", () => elements.listingModal.close());
elements.listingModal.addEventListener("click", (event) => { if (event.target === elements.listingModal) elements.listingModal.close(); });
elements.listingModal.addEventListener("close", () => { state.marketRequest?.abort(); state.detailRequest?.abort(); showBrowserView(); });
document.addEventListener("click", (event) => { if (!elements.searchShell.contains(event.target)) closeSuggestions(); });
document.addEventListener("keydown", (event) => { if (event.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); elements.searchInput.focus(); } });

initialize();
