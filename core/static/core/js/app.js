(function () {
  'use strict';

  const MAP_CENTER = [-25.429, -49.267];
  const MAP_ZOOM = 12;
  const TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
  const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> / CARTO';

  // --- State ---
  let map, markerCluster, routeLayers = {}, stopLayers = [];
  let allRoutes = [], allStops = [];
  let activeRouteId = null, activeDay = 'weekday', activeType = 'all';
  let detailPanelOpen = false;

  // --- Init Map ---
  function initMap() {
    map = L.map('map', {
      center: MAP_CENTER,
      zoom: MAP_ZOOM,
      zoomControl: true,
      attributionControl: false,
    });
    L.tileLayer(TILE_URL, {
      maxZoom: 19,
      attribution: TILE_ATTR,
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    markerCluster = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 40,
      spiderfyOnMaxZoom: true,
      disableClusteringAtZoom: 16,
      polygonOptions: { color: 'rgba(245,197,24,0.3)', weight: 1 },
    });
    map.addLayer(markerCluster);
  }

  // --- Panel ---
  function initPanel() {
    const toggle = document.getElementById('menu-toggle');
    const panel = document.getElementById('panel');
    const overlay = document.getElementById('panel-overlay');

    toggle.addEventListener('click', () => {
      panel.classList.toggle('open');
      toggle.classList.toggle('active');
      overlay.classList.toggle('show');
    });

    overlay.addEventListener('click', () => {
      panel.classList.remove('open');
      toggle.classList.remove('active');
      overlay.classList.remove('show');
    });
  }

  // --- Day Selector ---
  function initDaySelector() {
    const selector = document.getElementById('day-selector');
    selector.addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      selector.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeDay = btn.dataset.day;
    });
  }

  // --- Type Filter ---
  function initTypeFilter() {
    const filter = document.getElementById('type-filter');
    filter.addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      filter.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeType = btn.dataset.type;
      renderRouteList();
      updateMapVisibility();
    });
  }

  // --- Load Data ---
  async function loadRoutes() {
    const res = await fetch('/api/routes/');
    const data = await res.json();
    allRoutes = data.features || [];
    return allRoutes;
  }

  async function loadStops() {
    const res = await fetch('/api/stops/');
    const data = await res.json();
    allStops = data.features || [];
    return allStops;
  }

  // --- Render Route List ---
  function renderRouteList() {
    const container = document.getElementById('routes-list');
    const count = document.getElementById('route-count');

    let filtered = allRoutes;
    if (activeType !== 'all') {
      filtered = filtered.filter(r => r.properties.route_type == activeType);
    }

    count.textContent = `(${filtered.length})`;

    container.innerHTML = '';
    filtered.sort((a, b) => {
      const na = parseInt(a.properties.short_name) || 9999;
      const nb = parseInt(b.properties.short_name) || 9999;
      return na - nb;
    });

    filtered.forEach(r => {
      const p = r.properties;
      const div = document.createElement('div');
      div.className = 'route-item';
      div.dataset.routeId = p.route_id;
      if (p.route_id === activeRouteId) div.classList.add('active');

      div.innerHTML = `
        <div class="route-color-bar" style="background:${p.color}"></div>
        <div class="route-number">${p.short_name}</div>
        <div class="route-name">${p.long_name}</div>
      `;
      div.addEventListener('click', () => onRouteClick(p.route_id));
      container.appendChild(div);
    });
  }

  // --- Map: Routes ---
  function renderRouteShapes(routeId) {
    if (routeLayers[routeId]) {
      highlightRoute(routeId);
      return;
    }

    fetch(`/api/routes/${routeId}/shape/`)
      .then(r => r.json())
      .then(geo => {
        if (!geo.features || geo.features.length === 0) return;

        const routeInfo = allRoutes.find(r => r.properties.route_id === routeId);
        const color = routeInfo ? routeInfo.properties.color : '#F5C518';

        const layer = L.geoJSON(geo, {
          style: {
            color: color,
            weight: 4,
            opacity: 1,
          }
        });
        routeLayers[routeId] = layer;
        highlightRoute(routeId);
      });
  }

  function highlightRoute(routeId) {
    Object.keys(routeLayers).forEach(id => {
      if (id === routeId) {
        map.addLayer(routeLayers[id]);
      } else {
        map.removeLayer(routeLayers[id]);
      }
    });

    document.querySelectorAll('.route-item').forEach(el => {
      el.classList.toggle('active', el.dataset.routeId === routeId);
    });
    activeRouteId = routeId;

    const bounds = routeLayers[routeId]?.getBounds();
    if (bounds) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 14 });
  }

  // --- Map: Stops ---
  function renderAllStops() {
    markerCluster.clearLayers();

    const geoLayer = L.geoJSON(null, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 4,
          fillColor: '#F5C518',
          color: 'rgba(245,197,24,0.3)',
          weight: 1,
          fillOpacity: 0.8,
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        layer.bindPopup(`
          <h3>${p.stop_name}</h3>
          <div class="popup-meta">Cód: ${p.stop_code || p.stop_id}</div>
          <button class="popup-action" onclick="window._showStopTimes('${p.stop_id}')">Ver Horários</button>
        `);
      }
    });

    geoLayer.addData({
      type: 'FeatureCollection',
      features: allStops,
    });

    markerCluster.addLayer(geoLayer);
  }

  // --- Route Click ---
  async function onRouteClick(routeId) {
    renderRouteShapes(routeId);
    showRouteDetail(routeId);
    closePanel();
  }

  async function showRouteDetail(routeId) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    panel.classList.remove('hidden');
    panel.classList.add('open');
    detailPanelOpen = true;

    content.innerHTML = '<div class="loading-spinner"></div>';

    const [detailRes, stopsRes] = await Promise.all([
      fetch(`/api/routes/${routeId}/`),
      fetch(`/api/routes/${routeId}/stops/`),
    ]);
    const detail = await detailRes.json();
    const stopsData = await stopsRes.json();

    let daysLabel = '';
    if (detail.operating_days && detail.operating_days.length) {
      const dayMap = { monday: 'Seg', tuesday: 'Ter', wednesday: 'Qua', thursday: 'Qui', friday: 'Sex', saturday: 'Sáb', sunday: 'Dom' };
      daysLabel = detail.operating_days.map(d => dayMap[d] || d).join(', ');
    }

    content.innerHTML = `
      <div class="detail-header">
        <h2 style="color:${detail.color}">${detail.short_name}</h2>
        <div class="detail-meta">${detail.long_name}</div>
        <div class="detail-meta" style="font-size:11px">${detail.agency} &middot; Opera: ${daysLabel}</div>
      </div>
      <div class="detail-section">
        <h3>Paradas (${stopsData.stops.length})</h3>
        <div class="route-stops-list">
          ${stopsData.stops.map((s, i) => `
            <div class="route-stop-item">
              <div class="stop-dot ${i === 0 ? 'first' : i === stopsData.stops.length - 1 ? 'last' : ''}"></div>
              <span>${s.stop_name}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // --- Stop Times ---
  window._showStopTimes = async function (stopId) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    panel.classList.remove('hidden');
    panel.classList.add('open');
    detailPanelOpen = true;

    content.innerHTML = '<div class="loading-spinner"></div>';

    const [stopRes, timesRes] = await Promise.all([
      fetch(`/api/stops/${stopId}/`),
      fetch(`/api/stops/${stopId}/times/`),
    ]);
    const stop = await stopRes.json();
    const times = await timesRes.json();

    content.innerHTML = `
      <div class="detail-header">
        <h2>${stop.stop_name}</h2>
        <div class="detail-meta">Cód: ${stop.stop_code || stop.stop_id}</div>
      </div>
      <div class="detail-section">
        <h3>Próximos Horários</h3>
        ${times.times && times.times.length ? `
        <div class="stop-times-list">
          ${times.times.map(t => `
            <div class="stop-time-item">
              <span class="route-label" style="background:${t.route_color};color:#000">${t.route_short_name}</span>
              <span class="headsign">${t.headsign || ''}</span>
              <span class="time">${t.departure_time || t.arrival_time}</span>
            </div>
          `).join('')}
        </div>
        ` : '<div style="color:var(--text-muted);font-size:13px">Nenhum horário encontrado para hoje.</div>'}
      </div>
    `;
  };

  function closeDetail() {
    const panel = document.getElementById('detail-panel');
    panel.classList.remove('open');
    detailPanelOpen = false;
    setTimeout(() => panel.classList.add('hidden'), 350);
  }

  function closePanel() {
    const panel = document.getElementById('panel');
    const toggle = document.getElementById('menu-toggle');
    const overlay = document.getElementById('panel-overlay');
    panel.classList.remove('open');
    toggle.classList.remove('active');
    overlay.classList.remove('show');
  }

  // --- Search ---
  function initSearch() {
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');

    let debounceTimer;

    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (q.length < 2) {
        results.classList.add('hidden');
        return;
      }
      debounceTimer = setTimeout(() => doSearch(q, results), 200);
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search-box') && !e.target.closest('#search-results')) {
        results.classList.add('hidden');
      }
    });
  }

  async function doSearch(q, resultsEl) {
    const res = await fetch(`/api/search/?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    resultsEl.innerHTML = '';
    resultsEl.classList.remove('hidden');

    if (data.routes.length === 0 && data.stops.length === 0) {
      resultsEl.innerHTML = '<div class="search-result-item" style="color:var(--text-muted)">Nenhum resultado</div>';
      return;
    }

    data.routes.forEach(r => {
      const div = document.createElement('div');
      div.className = 'search-result-item';
      div.innerHTML = `<span class="badge route-badge" style="background:${r.color}22;color:${r.color}">${r.short_name}</span><span>${r.long_name}</span>`;
      div.addEventListener('click', () => {
        onRouteClick(r.route_id);
        resultsEl.classList.add('hidden');
        document.getElementById('search-input').value = '';
      });
      resultsEl.appendChild(div);
    });

    data.stops.forEach(s => {
      const div = document.createElement('div');
      div.className = 'search-result-item';
      div.innerHTML = `<span class="badge stop-badge">P</span><span>${s.stop_name}</span>`;
      div.addEventListener('click', () => {
        window._showStopTimes(s.stop_id);
        map.setView([s.stop_lat, s.stop_lon], 16);
        resultsEl.classList.add('hidden');
        document.getElementById('search-input').value = '';
      });
      resultsEl.appendChild(div);
    });
  }

  // --- Update route visibility based on type filter ---
  function updateMapVisibility() {
    if (!activeRouteId) return;
    const route = allRoutes.find(r => r.properties.route_id === activeRouteId);
    if (!route) return;
    if (activeType !== 'all' && route.properties.route_type != activeType) {
      Object.keys(routeLayers).forEach(id => {
        map.removeLayer(routeLayers[id]);
      });
      activeRouteId = null;
      document.querySelectorAll('.route-item').forEach(el => el.classList.remove('active'));
    }
  }

  // --- Keyboard shortcuts ---
  function initKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const panel = document.getElementById('detail-panel');
        if (detailPanelOpen) {
          closeDetail();
        } else {
          closePanel();
        }
      }
    });
  }

  // --- Init ---
  async function init() {
    initMap();
    initPanel();
    initDaySelector();
    initTypeFilter();
    initSearch();
    initKeyboard();

    document.getElementById('detail-close').addEventListener('click', closeDetail);

    const [routes] = await Promise.all([loadRoutes(), loadStops()]);

    renderRouteList();
    renderAllStops();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
