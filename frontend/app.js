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
  debounce: null,
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
  } catch (error) {
    elements.catalogStatus.textContent = "Каталог недоступен";
    elements.catalogStatus.classList.add("is-error");
    elements.searchHint.textContent = "Не удалось подключиться к базе данных";
    elements.searchHint.classList.add("is-error");
  }
}

function fillSelect(select, items) {
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.name} (${item.count})`;
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
    elements.searchHint.textContent = "Введите минимум 2 символа";
    return;
  }

  state.request?.abort();
  state.request = new AbortController();
  elements.searchShell.classList.add("is-loading");
  elements.searchHint.textContent = "Ищем совпадения…";

  const params = new URLSearchParams({ q: query });
  if (elements.weaponFilter.value) params.set("weapon", elements.weaponFilter.value);
  if (elements.rarityFilter.value) params.set("rarity", elements.rarityFilter.value);

  try {
    state.results = await api.get(`/api/skins/search?${params}`, state.request.signal);
    state.selectedIndex = -1;
    renderSuggestions();
    elements.searchHint.textContent = state.results.length
      ? `Найдено вариантов: ${state.results.length}`
      : "Совпадений не найдено";
  } catch (error) {
    if (error.name !== "AbortError") {
      closeSuggestions();
      elements.searchHint.textContent = "Поиск временно недоступен";
      elements.searchHint.classList.add("is-error");
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
  elements.searchInput.value = skin.name;
  elements.searchHint.textContent = "Загружаем качества…";
  try {
    state.selectedSkin = await api.get(`/api/skins/${encodeURIComponent(skin.id)}`);
    renderSkin(state.selectedSkin);
    elements.skinView.hidden = false;
    elements.welcomeState.hidden = true;
    elements.searchHint.textContent = "Скин выбран";
    elements.skinView.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    elements.searchHint.textContent = "Не удалось загрузить скин";
    elements.searchHint.classList.add("is-error");
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
  elements.qualityGrid.replaceChildren();
  let visibleCount = 0;

  for (const quality of skin.qualities) {
    const variants = quality.variants.filter((variant) => enabled.has(variantType(variant)));
    if (!variants.length) continue;
    visibleCount += 1;

    const card = document.createElement("article");
    card.className = "quality-card";
    const title = document.createElement("h3");
    title.textContent = quality.wear;
    const tags = document.createElement("div");
    tags.className = "variant-tags";

    for (const variant of variants) {
      const tag = document.createElement("span");
      const type = variantType(variant);
      tag.className = `variant-tag ${type}`;
      tag.textContent = type === "stattrak" ? "StatTrak™" : type === "souvenir" ? "Souvenir" : "Обычный";
      tag.title = variant.market_hash_name || variant.name;
      tags.append(tag);
    }
    card.append(title, tags);
    elements.qualityGrid.append(card);
  }
  elements.qualityEmpty.hidden = visibleCount > 0;
}

function variantType(variant) {
  if (variant.stattrak) return "stattrak";
  if (variant.souvenir) return "souvenir";
  return "normal";
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

elements.searchInput.addEventListener("input", () => {
  elements.searchHint.classList.remove("is-error");
  scheduleSearch();
});
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
    if (elements.searchInput.value.trim().length >= 2) runSearch();
  });
});
elements.resetFilters.addEventListener("click", () => {
  elements.weaponFilter.value = "";
  elements.rarityFilter.value = "";
  if (elements.searchInput.value.trim().length >= 2) runSearch();
});
elements.variantFilters.addEventListener("change", renderQualities);

initialize();
