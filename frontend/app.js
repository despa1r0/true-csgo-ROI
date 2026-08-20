const elements = {
  catalogStatus: document.querySelector("#catalogStatus"),
  searchShell: document.querySelector("#searchShell"),
  searchInput: document.querySelector("#searchInput"),
  suggestions: document.querySelector("#suggestions"),
  searchHint: document.querySelector("#searchHint"),
  weaponFilter: document.querySelector("#weaponFilter"),
  rarityFilter: document.querySelector("#rarityFilter"),
  resetFilters: document.querySelector("#resetFilters"),
  skinView: document.querySelector("#skinView"),
  welcomeState: document.querySelector("#welcomeState"),
  skinImage: document.querySelector("#skinImage"),
  skinWeapon: document.querySelector("#skinWeapon"),
  skinRarity: document.querySelector("#skinRarity"),
  skinName: document.querySelector("#skinName"),
  skinDescription: document.querySelector("#skinDescription"),
  skinFloat: document.querySelector("#skinFloat"),
  skinPaint: document.querySelector("#skinPaint"),
  variantFilters: document.querySelector("#variantFilters"),
  qualityGrid: document.querySelector("#qualityGrid"),
  qualityEmpty: document.querySelector("#qualityEmpty"),
  suggestionTemplate: document.querySelector("#suggestionTemplate"),
};

const state = {
  results: [],
  selectedIndex: -1,
  selectedSkin: null,
  request: null,
  marketRequest: null,
  debounce: null,
  selectedVariants: new Map(),
};

const api = {
  async get(path, signal) {
    const response = await fetch(path, { signal });
    if (!response.ok) throw new Error(`Ошибка запроса (${response.status})`);
    return response.json();
  },
};

async function initialize() {
  try {
    const [health, filters] = await Promise.all([
      api.get("/api/health"),
      api.get("/api/catalog/filters"),
    ]);
    elements.catalogStatus.textContent = `${formatCount(health.catalogue.skins)} скинов`;
    fillSelect(elements.weaponFilter, filters.weapons);
    fillSelect(elements.rarityFilter, filters.rarities);
  } catch {
    elements.catalogStatus.textContent = "Каталог недоступен";
    elements.catalogStatus.classList.add("is-error");
    setSearchHint("Не удалось подключиться к базе данных", true);
  }
}

function fillSelect(select, items) {
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.name} · ${item.count}`;
    select.append(option);
  }
}

function scheduleSearch() {
  clearTimeout(state.debounce);
  state.debounce = setTimeout(runSearch, 220);
}

async function runSearch() {
  const query = elements.searchInput.value.trim();
  if (query.length < 2) {
    closeSuggestions();
    setSearchHint("Введите минимум 2 символа");
    return;
  }

  state.request?.abort();
  state.request = new AbortController();
  elements.searchShell.classList.add("is-loading");
  setSearchHint("Ищем совпадения…");

  const params = new URLSearchParams({ q: query });
  if (elements.weaponFilter.value) params.set("weapon", elements.weaponFilter.value);
  if (elements.rarityFilter.value) params.set("rarity", elements.rarityFilter.value);

  try {
    state.results = await api.get(`/api/skins/search?${params}`, state.request.signal);
    state.selectedIndex = -1;
    renderSuggestions();
    setSearchHint(
      state.results.length
        ? `Найдено: ${state.results.length}`
        : "Совпадений не найдено",
    );
  } catch (error) {
    if (error.name !== "AbortError") {
      closeSuggestions();
      setSearchHint("Поиск временно недоступен", true);
    }
  } finally {
    elements.searchShell.classList.remove("is-loading");
  }
}

function renderSuggestions() {
  elements.suggestions.replaceChildren();
  if (!state.results.length) {
    closeSuggestions();
    return;
  }

  state.results.forEach((skin, index) => {
    const node = elements.suggestionTemplate.content.cloneNode(true);
    const button = node.querySelector("button");
    const image = node.querySelector("img");
    button.dataset.index = String(index);
    button.setAttribute("aria-selected", "false");
    image.src = skin.image_url || "";
    image.alt = `Превью ${skin.name}`;
    node.querySelector("strong").textContent = skin.name;
    node.querySelector(".suggestion-weapon").textContent = skin.weapon_name || "Предмет";
    node.querySelector(".suggestion-variants").textContent = pluralizeVariants(skin.variant_count);
    node.querySelector(".rarity-line").style.background = skin.rarity_color || "#748197";
    button.addEventListener("click", () => selectSkin(skin));
    elements.suggestions.append(node);
  });

  elements.suggestions.hidden = false;
  elements.searchInput.setAttribute("aria-expanded", "true");
}

async function selectSkin(skin) {
  closeSuggestions();
  state.marketRequest?.abort();
  state.selectedVariants.clear();
  elements.searchInput.value = skin.name;
  setSearchHint("Загружаем варианты…");
  try {
    state.selectedSkin = await api.get(`/api/skins/${encodeURIComponent(skin.id)}`);
    for (const quality of state.selectedSkin.qualities) {
      for (const variant of quality.variants) variant.csfloatPending = true;
    }
    renderSkin(state.selectedSkin);
    elements.skinView.hidden = false;
    elements.welcomeState.hidden = true;
    setSearchHint("Данные каталога загружены");
    elements.skinView.scrollIntoView({ behavior: "smooth", block: "start" });
    loadCsfloatPrices(skin.id);
  } catch {
    setSearchHint("Не удалось загрузить скин", true);
  }
}

async function loadCsfloatPrices(skinId) {
  state.marketRequest = new AbortController();
  const request = state.marketRequest;
  try {
    const market = await api.get(
      `/api/skins/${encodeURIComponent(skinId)}/market/csfloat`,
      request.signal,
    );
    if (request !== state.marketRequest || state.selectedSkin?.id !== skinId) return;

    const prices = new Map(market.variants.map((item) => [item.variant_id, item]));
    for (const quality of state.selectedSkin.qualities) {
      for (const variant of quality.variants) {
        const price = prices.get(variant.id);
        variant.csfloatPending = false;
        variant.csfloatListing = price?.listing || null;
        variant.csfloatError = price?.error || null;
      }
    }
    renderQualities();
  } catch (error) {
    if (error.name === "AbortError" || request !== state.marketRequest) return;
    for (const quality of state.selectedSkin?.qualities || []) {
      for (const variant of quality.variants) {
        variant.csfloatPending = false;
        variant.csfloatError = "Не удалось загрузить цены CSFloat";
      }
    }
    renderQualities();
  }
}

function renderSkin(skin) {
  elements.skinImage.src = skin.image_url || "";
  elements.skinImage.alt = skin.name;
  elements.skinWeapon.textContent = skin.weapon_name || skin.category_name || "Предмет";
  elements.skinRarity.textContent = skin.rarity_name || "Без редкости";
  elements.skinRarity.style.setProperty("--rarity-color", skin.rarity_color || "#748197");
  elements.skinName.textContent = skin.name;
  elements.skinDescription.textContent = cleanDescription(skin.description) || "Описание пока отсутствует.";
  elements.skinFloat.textContent = formatFloatRange(skin.min_float, skin.max_float);
  elements.skinPaint.textContent = skin.paint_index || "—";
  renderQualities();
}

function renderQualities() {
  const skin = state.selectedSkin;
  if (!skin) return;
  const enabled = new Set(
    [...elements.variantFilters.querySelectorAll("input:checked")].map((input) => input.value),
  );
  const openWears = new Set(
    [...elements.qualityGrid.querySelectorAll("details[open]")].map((card) => card.dataset.wear),
  );
  elements.qualityGrid.replaceChildren();
  let visibleCount = 0;

  for (const quality of skin.qualities) {
    const variants = quality.variants.filter((variant) => enabled.has(variantType(variant)));
    if (!variants.length) continue;
    visibleCount += 1;
    elements.qualityGrid.append(renderQualityCard(quality, variants, openWears.has(quality.wear)));
  }
  elements.qualityEmpty.hidden = visibleCount > 0;
}

function renderQualityCard(quality, variants, wasOpen) {
  const card = document.createElement("details");
  card.className = "quality-card";
  card.dataset.wear = quality.wear;
  card.open = wasOpen;

  const summary = document.createElement("summary");
  const heading = document.createElement("span");
  heading.className = "quality-title";
  const title = document.createElement("strong");
  title.textContent = quality.wear;
  const count = document.createElement("small");
  count.textContent = pluralizeVariants(variants.length);
  heading.append(title, count);

  const market = document.createElement("span");
  market.className = "quality-market";
  market.append(renderQualityMarket(variants));
  const chevron = document.createElement("span");
  chevron.className = "chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "⌄";
  summary.append(heading, market, chevron);

  const body = document.createElement("div");
  body.className = "quality-details";
  card.append(summary, body);

  const renderBody = () => renderQualityDetails(body, quality, variants);
  card.addEventListener("toggle", () => {
    if (card.open) renderBody();
  });
  if (card.open) renderBody();
  return card;
}

function renderQualityMarket(variants) {
  if (variants.some((variant) => variant.csfloatPending)) {
    const pending = document.createElement("span");
    pending.className = "summary-price is-pending";
    pending.textContent = "CSFloat · загрузка";
    return pending;
  }
  const priced = variants
    .filter((variant) => variant.csfloatListing)
    .sort((left, right) => left.csfloatListing.price_cents - right.csfloatListing.price_cents);
  if (!priced.length) {
    const empty = document.createElement("span");
    empty.className = "summary-price is-muted";
    empty.textContent = "Нет активных лотов";
    return empty;
  }
  const cheapest = priced[0];
  const link = document.createElement("a");
  link.className = "summary-price";
  link.href = cheapest.csfloatListing.item_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = `от ${formatUsd(cheapest.csfloatListing.price_cents)}`;
  link.title = "Открыть лоты на CSFloat";
  link.addEventListener("click", (event) => event.stopPropagation());
  return link;
}

function renderQualityDetails(container, quality, variants) {
  let selectedId = state.selectedVariants.get(quality.wear);
  if (!variants.some((variant) => variant.id === selectedId)) selectedId = variants[0].id;
  state.selectedVariants.set(quality.wear, selectedId);
  const selected = variants.find((variant) => variant.id === selectedId);

  const tabs = document.createElement("div");
  tabs.className = "variant-tabs";
  for (const variant of variants) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `variant-tab ${variant.id === selected.id ? "is-active" : ""}`;
    button.textContent = variantLabel(variant);
    button.addEventListener("click", () => {
      state.selectedVariants.set(quality.wear, variant.id);
      renderQualityDetails(container, quality, variants);
    });
    tabs.append(button);
  }

  const panel = document.createElement("div");
  panel.className = "variant-panel";
  renderVariantPanel(panel, selected);
  container.replaceChildren(tabs, panel);

  if (!selected.csfloatDetails && !selected.csfloatDetailsPending && !selected.csfloatDetailsError) {
    loadVariantDetails(selected, () => {
      if (container.isConnected && state.selectedVariants.get(quality.wear) === selected.id) {
        renderQualityDetails(container, quality, variants);
      }
    });
  }
}

async function loadVariantDetails(variant, onUpdate) {
  variant.csfloatDetailsPending = true;
  onUpdate();
  try {
    variant.csfloatDetails = await api.get(
      `/api/variants/${encodeURIComponent(variant.id)}/market/csfloat`,
    );
  } catch {
    variant.csfloatDetailsError = "Не удалось загрузить подробности варианта";
  } finally {
    variant.csfloatDetailsPending = false;
    onUpdate();
  }
}

function renderVariantPanel(panel, variant) {
  const header = document.createElement("div");
  header.className = "variant-panel-header";
  const name = document.createElement("div");
  const overline = document.createElement("small");
  overline.textContent = "CSFLOAT · BUY NOW";
  const title = document.createElement("h4");
  title.textContent = variant.market_hash_name || variant.name;
  name.append(overline, title);
  header.append(name, renderVariantPrice(variant));
  panel.append(header);

  if (variant.csfloatDetailsPending) {
    panel.append(renderDetailsSkeleton());
    return;
  }
  if (variant.csfloatDetailsError) {
    panel.append(renderNotice(variant.csfloatDetailsError, true));
    return;
  }
  if (!variant.csfloatDetails) {
    panel.append(renderDetailsSkeleton());
    return;
  }

  const details = variant.csfloatDetails;
  panel.append(renderMetrics(details));
  if (details.sales_error) panel.append(renderNotice(`История продаж: ${details.sales_error}`, false));

  const listingsHeader = document.createElement("div");
  listingsHeader.className = "listings-heading";
  const listingsTitle = document.createElement("h5");
  listingsTitle.textContent = "Первые 10 листингов";
  const fetched = document.createElement("span");
  fetched.textContent = details.stale ? "сохранённые данные" : "актуальный срез";
  listingsHeader.append(listingsTitle, fetched);
  panel.append(listingsHeader);

  if (details.listings.length) {
    panel.append(renderListings(details.listings));
  } else if (details.listings_error) {
    panel.append(renderNotice(details.listings_error, true));
  } else {
    panel.append(renderNotice("Активных листингов для этого варианта нет", false));
  }
}

function renderVariantPrice(variant) {
  if (variant.csfloatPending) {
    const pending = document.createElement("span");
    pending.className = "detail-price is-pending";
    pending.textContent = "Цена…";
    return pending;
  }
  if (!variant.csfloatListing) {
    const empty = document.createElement("span");
    empty.className = "detail-price is-muted";
    empty.textContent = "Нет лотов";
    return empty;
  }
  const link = document.createElement("a");
  link.className = "detail-price";
  link.href = variant.csfloatListing.item_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.innerHTML = `${formatUsd(variant.csfloatListing.price_cents)} <span>↗</span>`;
  return link;
}

function renderMetrics(details) {
  const metrics = document.createElement("div");
  metrics.className = "metrics-grid";
  const liquidity = liquidityPresentation(details.stats);
  const values = [
    ["Мин. цена", formatNullableUsd(details.overview.price_cents), "Текущий индекс CSFloat"],
    ["Активные лоты", formatNullableCount(details.overview.active_listings), "Доступно сейчас"],
    ["Продаж в истории", formatNullableCount(details.stats.sales_count), details.stats.sales_scope],
    ["Ликвидность β", liquidity.value, details.stats.methodology],
  ];
  for (const [label, value, hint] of values) {
    const metric = document.createElement("div");
    metric.className = "metric";
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    const hintNode = document.createElement("small");
    hintNode.textContent = hint;
    hintNode.title = hint;
    metric.append(labelNode, valueNode, hintNode);
    metrics.append(metric);
  }
  return metrics;
}

function renderListings(listings) {
  const wrap = document.createElement("div");
  wrap.className = "listings-table-wrap";
  const table = document.createElement("table");
  table.className = "listings-table";
  table.innerHTML = "<thead><tr><th>Цена</th><th>Float</th><th>Seed</th><th>Paint</th><th>Стикеры</th><th></th></tr></thead>";
  const body = document.createElement("tbody");
  for (const listing of listings) {
    const row = document.createElement("tr");
    row.append(
      tableCell(formatUsd(listing.price_cents), "listing-price-cell"),
      tableCell(formatListingFloat(listing.float_value)),
      tableCell(listing.paint_seed ?? "—"),
      tableCell(listing.paint_index ?? "—"),
      stickerCell(listing.stickers),
      listingLinkCell(listing),
    );
    body.append(row);
  }
  table.append(body);
  wrap.append(table);
  return wrap;
}

function tableCell(value, className = "") {
  const cell = document.createElement("td");
  cell.className = className;
  cell.textContent = value;
  return cell;
}

function stickerCell(stickers) {
  const cell = document.createElement("td");
  const wrap = document.createElement("div");
  wrap.className = "sticker-list";
  if (!stickers?.length) {
    wrap.textContent = "—";
  } else {
    for (const sticker of stickers.slice(0, 2)) {
      const tag = document.createElement("span");
      tag.textContent = sticker.name;
      tag.title = `${sticker.name}${sticker.slot == null ? "" : ` · слот ${sticker.slot + 1}`}`;
      wrap.append(tag);
    }
    if (stickers.length > 2) {
      const more = document.createElement("span");
      more.textContent = `+${stickers.length - 2}`;
      wrap.append(more);
    }
  }
  cell.append(wrap);
  return cell;
}

function listingLinkCell(listing) {
  const cell = document.createElement("td");
  const link = document.createElement("a");
  link.className = "listing-link";
  link.href = listing.item_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Открыть ↗";
  cell.append(link);
  return cell;
}

function renderDetailsSkeleton() {
  const skeleton = document.createElement("div");
  skeleton.className = "details-skeleton";
  skeleton.innerHTML = "<span></span><span></span><span></span><span></span>";
  return skeleton;
}

function renderNotice(message, isError) {
  const notice = document.createElement("p");
  notice.className = `detail-notice${isError ? " is-error" : ""}`;
  notice.textContent = message;
  return notice;
}

function liquidityPresentation(stats) {
  if (stats.liquidity_score == null) return { value: "Нет данных" };
  const labels = { high: "Высокая", medium: "Средняя", low: "Низкая" };
  return { value: `${labels[stats.liquidity_label] || "Нет данных"} · ${stats.liquidity_score}%` };
}

function variantType(variant) {
  if (variant.stattrak) return "stattrak";
  if (variant.souvenir) return "souvenir";
  return "normal";
}

function variantLabel(variant) {
  const type = variantType(variant);
  if (type === "stattrak") return "StatTrak™";
  if (type === "souvenir") return "Souvenir";
  return "Обычный";
}

function cleanDescription(value) {
  if (!value) return "";
  const documentFragment = new DOMParser().parseFromString(value, "text/html");
  return documentFragment.body.textContent.replace(/\s+/g, " ").trim();
}

function formatFloatRange(min, max) {
  if (min == null || max == null) return "—";
  return `${Number(min).toFixed(2)} — ${Number(max).toFixed(2)}`;
}

function formatListingFloat(value) {
  return value == null ? "—" : Number(value).toFixed(8);
}

function formatNullableCount(value) {
  return value == null ? "Нет данных" : formatCount(value);
}

function formatNullableUsd(value) {
  return value == null ? "Нет данных" : formatUsd(value);
}

function setSearchHint(message, isError = false) {
  elements.searchHint.textContent = message;
  elements.searchHint.classList.toggle("is-error", isError);
}

function closeSuggestions() {
  elements.suggestions.hidden = true;
  elements.searchInput.setAttribute("aria-expanded", "false");
  state.selectedIndex = -1;
}

function moveSelection(direction) {
  if (elements.suggestions.hidden || !state.results.length) return;
  state.selectedIndex = (state.selectedIndex + direction + state.results.length) % state.results.length;
  const buttons = [...elements.suggestions.querySelectorAll("button")];
  buttons.forEach((button, index) => {
    const active = index === state.selectedIndex;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    if (active) button.scrollIntoView({ block: "nearest" });
  });
}

function pluralizeVariants(count) {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 19) return `${count} вариантов`;
  if (last === 1) return `${count} вариант`;
  if (last >= 2 && last <= 4) return `${count} варианта`;
  return `${count} вариантов`;
}

function formatCount(count) {
  return new Intl.NumberFormat("ru-RU").format(count);
}

function formatUsd(cents) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

elements.searchInput.addEventListener("input", scheduleSearch);
elements.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown") { event.preventDefault(); moveSelection(1); }
  if (event.key === "ArrowUp") { event.preventDefault(); moveSelection(-1); }
  if (event.key === "Enter" && state.selectedIndex >= 0) {
    event.preventDefault();
    selectSkin(state.results[state.selectedIndex]);
  }
  if (event.key === "Escape") closeSuggestions();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== elements.searchInput) {
    event.preventDefault();
    elements.searchInput.focus();
  }
});
document.addEventListener("click", (event) => {
  if (!elements.searchShell.contains(event.target)) closeSuggestions();
});
[elements.weaponFilter, elements.rarityFilter].forEach((select) => {
  select.addEventListener("change", () => {
    select.closest(".select-chip").classList.toggle("is-active", Boolean(select.value));
    if (elements.searchInput.value.trim().length >= 2) runSearch();
  });
});
elements.resetFilters.addEventListener("click", () => {
  for (const select of [elements.weaponFilter, elements.rarityFilter]) {
    select.value = "";
    select.closest(".select-chip").classList.remove("is-active");
  }
  if (elements.searchInput.value.trim().length >= 2) runSearch();
});
elements.variantFilters.addEventListener("change", renderQualities);

initialize();
