(function () {
  const $ = (id) => document.getElementById(id);

  const citySelect = $("city");
  const operation = $("operation");
  const priceMin = $("priceMin");
  const priceMax = $("priceMax");
  const sizeMin = $("sizeMin");
  const sizeMax = $("sizeMax");
  const rooms = $("rooms");
  const baths = $("baths");
  const portalsEl = $("portals");
  const telegramEl = $("telegram");
  const zonesGood = $("zonesGood");
  const zonesBad = $("zonesBad");
  const zoneCityLabel = $("zoneCityLabel");

  function fillCities() {
    citySelect.innerHTML = window.PISOS_CITIES.map(
      (c) => `<option value="${c.id}">${c.label}</option>`
    ).join("");
  }

  function numOrNull(el) {
    const v = el.value.trim();
    if (!v) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function getCity() {
    return window.PISOS_CITIES.find((c) => c.id === citySelect.value);
  }

  function idealistaFilters(op) {
    const parts = [];
    const pMin = numOrNull(priceMin);
    const pMax = numOrNull(priceMax);
    const sMin = numOrNull(sizeMin);
    const sMax = numOrNull(sizeMax);
    const r = rooms.value;
    const b = baths.value;

    if (pMin != null) parts.push(`precio-desde_${Math.round(pMin)}`);
    if (pMax != null) parts.push(`precio-hasta_${Math.round(pMax)}`);
    if (sMin != null) parts.push(`metros-cuadrados-mas-de_${Math.round(sMin)}`);
    if (sMax != null) parts.push(`metros-cuadrados-menos-de_${Math.round(sMax)}`);
    if (b && b !== "any") parts.push(`banos-mas_de_${b}`);

    // dormitorios: Idealista often uses de-N-dormitorios or mas-de
    if (r && r !== "any") {
      const n = Number(r);
      if (n === 1) parts.push("de-un-dormitorio");
      else if (n >= 4) parts.push("de-cuatro-cinco-seis-o-mas-dormitorios");
      else if (n === 2) parts.push("de-dos-dormitorios");
      else if (n === 3) parts.push("de-tres-dormitorios");
    }

    void op;
    return parts.length ? `con-${parts.join(",")}` : "";
  }

  function buildIdealista(city) {
    const op = operation.value === "rent" ? "alquiler-viviendas" : "venta-viviendas";
    const filt = idealistaFilters(operation.value);
    const base = `https://www.idealista.com/${op}/${city.idealista}/`;
    return filt ? `${base}${filt}/` : base;
  }

  function buildFotocasa(city) {
    const op = operation.value === "rent" ? "alquiler" : "comprar";
    const params = new URLSearchParams();
    const pMin = numOrNull(priceMin);
    const pMax = numOrNull(priceMax);
    const sMin = numOrNull(sizeMin);
    const sMax = numOrNull(sizeMax);
    if (pMin != null) params.set("minPrice", String(Math.round(pMin)));
    if (pMax != null) params.set("maxPrice", String(Math.round(pMax)));
    if (sMin != null) params.set("minSurface", String(Math.round(sMin)));
    if (sMax != null) params.set("maxSurface", String(Math.round(sMax)));
    if (rooms.value !== "any") params.set("minRooms", rooms.value);
    if (baths.value !== "any") params.set("minBathrooms", baths.value);
    const q = params.toString();
    return `https://www.fotocasa.es/es/${op}/viviendas/${city.fotocasa}/l${q ? `?${q}` : ""}`;
  }

  function buildHabitaclia(city) {
    const op = operation.value === "rent" ? "alquiler" : "viviendas";
    // Habitaclia paths vary; city landing + query text is a resilient fallback
    const params = new URLSearchParams();
    const pMax = numOrNull(priceMax);
    const sMin = numOrNull(sizeMin);
    if (pMax != null) params.set("pmax", String(Math.round(pMax)));
    if (sMin != null) params.set("sm", String(Math.round(sMin)));
    const q = params.toString();
    return `https://www.habitaclia.com/${op}-${city.habitaclia}.htm${q ? `?${q}` : ""}`;
  }

  function buildMilanuncios(city) {
    const op = operation.value === "rent" ? "alquiler" : "venta";
    const params = new URLSearchParams();
    params.set("s", city.milanuncios);
    const pMax = numOrNull(priceMax);
    const pMin = numOrNull(priceMin);
    if (pMin != null) params.set("desde", String(Math.round(pMin)));
    if (pMax != null) params.set("hasta", String(Math.round(pMax)));
    return `https://www.milanuncios.com/viviendas-en-${op}/?${params.toString()}`;
  }

  function buildWallapop(city) {
    const params = new URLSearchParams();
    params.set("category_ids", "200"); // home
    params.set("longitude", "0");
    params.set("latitude", "0");
    // Wallapop geo is complex; use text search as practical deep-link
    const bits = [city.label, "piso"];
    const pMax = numOrNull(priceMax);
    if (pMax != null) bits.push(`hasta ${Math.round(pMax)}`);
    params.set("keywords", bits.join(" "));
    return `https://es.wallapop.com/search?${params.toString()}`;
  }

  function renderPortals() {
    const city = getCity();
    if (!city) {
      portalsEl.innerHTML = `<p class="empty">Tria una localitat.</p>`;
      return;
    }

    const links = [
      { name: "Idealista", blurb: "Portal principal", url: buildIdealista(city) },
      { name: "Fotocasa", blurb: "Cerca amb filtres", url: buildFotocasa(city) },
      { name: "Habitaclia", blurb: "Alternativa ES", url: buildHabitaclia(city) },
      { name: "Milanuncios", blurb: "Particulars / mixt", url: buildMilanuncios(city) },
      { name: "Wallapop", blurb: "Cerca per paraules", url: buildWallapop(city) },
    ];

    portalsEl.innerHTML = links
      .map(
        (l) => `
      <div class="portal-item">
        <div>
          <strong>${l.name}</strong>
          <span>${l.blurb}</span>
        </div>
        <a class="btn btn-primary" href="${l.url}" target="_blank" rel="noopener noreferrer">Obrir cerca</a>
      </div>`
      )
      .join("");
  }

  function renderTelegram() {
    const city = getCity();
    const items = (window.PISOS_TELEGRAM.channels || []).filter(
      (c) => c.city === "general" || c.city === city?.id
    );

    const cityQuery = city?.telegramQuery || "libertad inmobiliaria";
    const extra = [
      {
        label: `Telegram web · ${city?.label || "ciutat"}`,
        href: `https://www.google.com/search?q=${encodeURIComponent(cityQuery + " telegram")}`,
        note: "Cerca canals/grupos públics per ciutat",
      },
      {
        label: "Obrir Telegram (app)",
        href: `tg://search?query=${encodeURIComponent(cityQuery)}`,
        note: "Si tens l’app instal·lada",
      },
    ];

    const channelHtml = items
      .map((c) => {
        const href =
          c.kind === "channel" && c.handle
            ? `https://t.me/${c.handle.replace(/^@/, "")}`
            : `https://www.google.com/search?q=${encodeURIComponent(c.query || cityQuery)}`;
        return `
        <div class="tg-item">
          <div>
            <strong>${c.label}</strong>
            <span>${c.kind === "channel" ? "Canal/grup" : "Cerca guiada"}</span>
          </div>
          <a class="btn btn-ghost" href="${href}" target="_blank" rel="noopener noreferrer">Obrir</a>
        </div>`;
      })
      .join("");

    const extraHtml = extra
      .map(
        (e) => `
      <div class="tg-item">
        <div>
          <strong>${e.label}</strong>
          <span>${e.note}</span>
        </div>
        <a class="btn btn-ghost" href="${e.href}" target="_blank" rel="noopener noreferrer">Obrir</a>
      </div>`
      )
      .join("");

    const tips = (window.PISOS_TELEGRAM.tips || [])
      .map((t) => `<li>${t}</li>`)
      .join("");

    telegramEl.innerHTML = `
      <div class="card" style="margin-bottom:0.8rem">
        <h3>Com usar Telegram</h3>
        <ul>${tips}</ul>
      </div>
      <div class="tg-list">${channelHtml}${extraHtml}</div>
    `;
  }

  function renderZones() {
    const city = getCity();
    zoneCityLabel.textContent = city?.label || "—";
    const z = window.PISOS_ZONES[city?.id];
    if (!z) {
      zonesGood.innerHTML = "<li>Sense notes encara per aquesta ciutat.</li>";
      zonesBad.innerHTML = "<li>Afegeix notes a data/zones.js</li>";
      return;
    }
    zonesGood.innerHTML = z.bones.map((x) => `<li>${x}</li>`).join("");
    zonesBad.innerHTML = z.cautela.map((x) => `<li>${x}</li>`).join("");
  }

  function refresh() {
    renderPortals();
    renderTelegram();
    renderZones();
  }

  function openAll() {
    const city = getCity();
    if (!city) return;
    const urls = [
      buildIdealista(city),
      buildFotocasa(city),
      buildHabitaclia(city),
      buildMilanuncios(city),
    ];
    // Browsers may block multiple popups: open sequentially with slight delay
    urls.forEach((url, i) => {
      window.setTimeout(() => {
        window.open(url, "_blank", "noopener,noreferrer");
      }, i * 400);
    });
  }

  fillCities();
  citySelect.value = "barcelona";
  ["city", "operation", "priceMin", "priceMax", "sizeMin", "sizeMax", "rooms", "baths"].forEach(
    (id) => $(id).addEventListener("input", refresh)
  );
  $("openAll").addEventListener("click", openAll);
  refresh();
})();
