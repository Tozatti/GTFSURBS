/* ---- State ---- */
let state = {
  routes: [],
  stopsGeo: null,
  activeRouteId: null,
  activeStopId: null,
  dayFilter: 'weekday',
  typeFilter: 'all',
  searchQuery: '',
  clustersVisible: false,
};

let map, markerCluster, shapeLayer, stopMarkers;
let routesCache = null;
let stopsCache = null;

/* ---- Map ---- */
function initMap() {
  map = L.map('map', {
    center: [-25.4284, -49.2733],
    zoom: 12,
    zoomControl: true,
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map);

  markerCluster = L.markerClusterGroup({
    chunkedLoading: true,
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    disableClusteringAtZoom: 16,
  });

  shapeLayer = L.layerGroup().addTo(map);
  stopMarkers = L.layerGroup().addTo(map);
}

/* ---- Data ---- */
async function loadJson(path) {
  const resp = await fetch(path);
  return resp.json();
}

/* ---- Routes ---- */
async function loadRoutes() {
  if (routesCache) {
    renderRoutes(routesCache);
    return;
  }

  const data = await loadJson('data/routes.json');
  routesCache = data.features || [];
  renderRoutes(routesCache);
}

function renderRoutes(features) {
  const container = document.getElementById('routes-list');
  const countEl = document.getElementById('route-count');

  let filtered = features;
  const q = state.searchQuery.toLowerCase().trim();

  if (q) {
    filtered = filtered.filter(f => {
      const p = f.properties;
      return p.short_name.toLowerCase().includes(q) || p.long_name.toLowerCase().includes(q);
    });
  }

  if (state.typeFilter !== 'all') {
    filtered = filtered.filter(f => f.properties.route_type === parseInt(state.typeFilter));
  }

  container.innerHTML = '';
  countEl.textContent = `(${filtered.length})`;

  filtered.sort((a, b) => {
    const an = parseInt(a.properties.short_name) || 9999;
    const bn = parseInt(b.properties.short_name) || 9999;
    return an - bn;
  });

  for (const f of filtered) {
    const p = f.properties;
    const el = document.createElement('div');
    el.className = 'route-item';
    el.dataset.routeId = p.route_id;

    const isActive = p.route_id === state.activeRouteId;
    if (isActive) el.classList.add('active');

    el.innerHTML = `
      <span class="route-badge" style="background:${p.color}">${escHtml(p.short_name)}</span>
      <span class="route-name">${escHtml(p.long_name)}</span>
      <span class="route-type-icon">${p.route_type === 11 ? '⚡' : '🚌'}</span>
    `;

    el.addEventListener('click', () => selectRoute(p.route_id));
    container.appendChild(el);
  }
}

/* ---- Select Route ---- */
async function selectRoute(routeId) {
  state.activeRouteId = routeId;
  state.activeStopId = null;

  document.querySelectorAll('.route-item').forEach(el => {
    el.classList.toggle('active', el.dataset.routeId === routeId);
  });

  const [shapeData, stopsData, detailData] = await Promise.all([
    loadJson(`data/routes/${routeId}/shape.json`),
    loadJson(`data/routes/${routeId}/stops.json`),
    loadJson(`data/routes/${routeId}/detail.json`),
  ]);

  shapeLayer.clearLayers();
  stopMarkers.clearLayers();

  if (shapeData.features) {
    for (const feat of shapeData.features) {
      if (feat.geometry && feat.geometry.type === 'LineString') {
        const coords = feat.geometry.coordinates.map(c => [c[1], c[0]]);
        const color = detailData.color || '#00d4aa';
        const polyline = L.polyline(coords, {
          color: color,
          weight: 4,
          opacity: 0.8,
        }).addTo(shapeLayer);
        map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
      }
    }
  }

  if (stopsData.stops) {
    for (const s of stopsData.stops) {
      if (!s.stop_lat || !s.stop_lon) continue;
      const marker = L.circleMarker([s.stop_lat, s.stop_lon], {
        radius: 6,
        color: detailData.color || '#00d4aa',
        fillColor: '#fff',
        fillOpacity: 1,
        weight: 2,
      }).addTo(stopMarkers);

      marker.bindPopup(`<b>${escHtml(s.stop_name)}</b><br><small>Cód: ${escHtml(s.stop_id)}</small>`);
      marker.on('click', () => selectStop(s.stop_id));
    }
  }

  showRouteDetail(detailData);
}

/* ---- Route Detail Panel ---- */
function showRouteDetail(data) {
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  const days = {
    monday: 'Seg', tuesday: 'Ter', wednesday: 'Qua',
    thursday: 'Qui', friday: 'Sex', saturday: 'Sáb', sunday: 'Dom',
  };
  const daysStr = (data.operating_days || []).map(d => days[d]).filter(Boolean).join(', ');

  content.innerHTML = `
    <div class="detail-header">
      <span class="detail-badge" style="background:${data.color}">${escHtml(data.short_name)}</span>
      <h2>${escHtml(data.long_name)}</h2>
    </div>
    <div class="detail-info">
      <div><span class="label">Tipo</span><br>${data.route_type === 11 ? 'Trolebus' : 'Ônibus'}</div>
      <div><span class="label">Agência</span><br>${escHtml(data.agency)}</div>
      <div><span class="label">Opera em</span><br>${daysStr || '—'}</div>
    </div>
  `;

  panel.classList.remove('hidden');
}

/* ---- Stops (cluster) ---- */
async function loadStops() {
  if (stopsCache) {
    renderStops(stopsCache);
    return;
  }

  const data = await loadJson('data/stops.json');
  stopsCache = data;
  renderStops(data);
}

function renderStops(data) {
  markerCluster.clearLayers();

  if (data.features) {
    for (const feat of data.features) {
      if (!feat.geometry) continue;
      const coords = feat.geometry.coordinates;
      const p = feat.properties;
      if (!coords) continue;

      const marker = L.circleMarker([coords[1], coords[0]], {
        radius: 5,
        color: '#7c5cfc',
        fillColor: '#7c5cfc',
        fillOpacity: 0.8,
        weight: 1,
      });

      marker.bindPopup(`<b>${escHtml(p.stop_name)}</b><br><small>Cód: ${escHtml(p.stop_id)}</small>`);
      marker.on('click', () => selectStop(p.stop_id));
      markerCluster.addLayer(marker);
    }
  }
}

/* ---- Select Stop ---- */
async function selectStop(stopId) {
  state.activeStopId = stopId;

  const data = await loadJson(`data/stops/${stopId}/times.json`);
  showStopDetail(data, stopId);
}

/* ---- Stop Detail Panel ---- */
async function showStopDetail(data, stopId) {
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  // Find stop name from cache
  let stopName = stopId;
  let stopCode = '';
  if (stopsCache && stopsCache.features) {
    for (const f of stopsCache.features) {
      if (f.properties.stop_id === stopId) {
        stopName = f.properties.stop_name;
        stopCode = f.properties.stop_code;
        break;
      }
    }
  }

  const dayLabels = {
    weekday: 'Dias Úteis',
    saturday: 'Sábado',
    sunday: 'Domingo',
  };

  let rows = '';
  if (data.times && data.times.length) {
    for (const t of data.times) {
      rows += `
        <li>
          <span class="route-badge" style="background:${t.route_color};min-width:36px;height:20px;font-size:10px">${escHtml(t.route_short_name)}</span>
          <span class="time">${escHtml(t.departure_time)}</span>
          <span class="headsign">${escHtml(t.headsign)}</span>
        </li>
      `;
    }
  } else {
    rows = '<li style="color:var(--text2)">Nenhum horário encontrado para hoje</li>';
  }

  content.innerHTML = `
    <div class="detail-header">
      <h2>${escHtml(stopName)}</h2>
    </div>
    <div class="detail-info">
      <div><span class="label">Código</span><br>${escHtml(stopCode || '—')}</div>
      <div><span class="label">Dia</span><br>${dayLabels[data.day] || data.day}</div>
    </div>
    <div class="detail-section-title">Próximos horários</div>
    <ul class="times-list">${rows}</ul>
  `;

  panel.classList.remove('hidden');
}

/* ---- Search ---- */
let searchTimeout;

document.getElementById('search-input').addEventListener('input', function () {
  clearTimeout(searchTimeout);
  const q = this.value.trim();

  if (q.length < 2) {
    document.getElementById('search-results').classList.add('hidden');
    state.searchQuery = '';
    renderRoutes(routesCache || []);
    return;
  }

  state.searchQuery = q;

  searchTimeout = setTimeout(async () => {
    if (state.searchQuery !== q) return;

    const container = document.getElementById('search-results');
    container.innerHTML = '';

    renderRoutes(routesCache || []);

    const results = { routes: [], stops: [] };
    const ql = q.toLowerCase();

    if (routesCache) {
      for (const f of routesCache) {
        const p = f.properties;
        if (p.short_name.toLowerCase().includes(ql) || p.long_name.toLowerCase().includes(ql)) {
          results.routes.push({
            route_id: p.route_id,
            short_name: p.short_name,
            long_name: p.long_name,
            color: p.color,
          });
        }
      }
    }

    if (stopsCache && stopsCache.features) {
      for (const f of stopsCache.features) {
        if (f.properties.stop_name.toLowerCase().includes(ql)) {
          results.stops.push({
            stop_id: f.properties.stop_id,
            stop_name: f.properties.stop_name,
            stop_lat: f.geometry.coordinates[1],
            stop_lon: f.geometry.coordinates[0],
          });
        }
      }
    }

    if (!results.routes.length && !results.stops.length) {
      container.innerHTML = '<div class="search-result-item" style="color:var(--text2)">Nenhum resultado</div>';
      container.classList.remove('hidden');
      return;
    }

    for (const r of results.routes.slice(0, 10)) {
      const el = document.createElement('div');
      el.className = 'search-result-item';
      el.innerHTML = `
        <span class="badge" style="background:${r.color}">${escHtml(r.short_name)}</span>
        <span>${escHtml(r.long_name)}</span>
        <span class="type-icon">🚌</span>
      `;
      el.addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        container.classList.add('hidden');
        state.searchQuery = '';
        selectRoute(r.route_id);
      });
      container.appendChild(el);
    }

    for (const s of results.stops.slice(0, 10)) {
      const el = document.createElement('div');
      el.className = 'search-result-item';
      el.innerHTML = `
        <span class="type-icon">📍</span>
        <span>${escHtml(s.stop_name)}</span>
      `;
      el.addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        container.classList.add('hidden');
        state.searchQuery = '';
        if (s.stop_lat && s.stop_lon) {
          map.flyTo([s.stop_lat, s.stop_lon], 16);
        }
        selectStop(s.stop_id);
      });
      container.appendChild(el);
    }

    container.classList.remove('hidden');
  }, 250);
});

document.addEventListener('click', function (e) {
  const results = document.getElementById('search-results');
  if (!e.target.closest('.search-box')) {
    results.classList.add('hidden');
  }
});

/* ---- UI Controls ---- */

document.getElementById('menu-toggle').addEventListener('click', function () {
  const panel = document.getElementById('panel');
  const overlay = document.getElementById('panel-overlay');
  this.classList.toggle('open');
  panel.classList.toggle('closed');
  overlay.classList.toggle('visible');
});

document.getElementById('panel-overlay').addEventListener('click', function () {
  document.getElementById('panel').classList.add('closed');
  document.getElementById('menu-toggle').classList.remove('open');
  this.classList.remove('visible');
});

document.getElementById('toggle-clusters').addEventListener('click', function () {
  state.clustersVisible = !state.clustersVisible;
  this.classList.toggle('active');
  this.textContent = state.clustersVisible ? 'Exibir' : 'Ocultar';

  if (state.clustersVisible) {
    map.addLayer(markerCluster);
  } else {
    map.removeLayer(markerCluster);
  }
});

document.getElementById('detail-close').addEventListener('click', function () {
  document.getElementById('detail-panel').classList.add('hidden');
  shapeLayer.clearLayers();
  stopMarkers.clearLayers();
  state.activeRouteId = null;
  document.querySelectorAll('.route-item').forEach(el => el.classList.remove('active'));
});

/* ---- Helpers ---- */
function escHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function debounce(fn, ms) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}

/* ---- Init ---- */
initMap();
loadRoutes();
loadStops();
