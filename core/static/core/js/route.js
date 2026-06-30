(function () {
  "use strict";

  const map = L.map("map", {
    center: [-25.45, -49.27],
    zoom: 13,
    zoomControl: false,
  });

  L.control.zoom({ position: "bottomright" }).addTo(map);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OSM</a>",
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);

  let originMarker = null;
  let destMarker = null;
  let routeLines = [];
  let routeMarkers = [];
  let activePick = null;

  const originLat = document.getElementById("origin-lat");
  const originLon = document.getElementById("origin-lon");
  const destLat = document.getElementById("dest-lat");
  const destLon = document.getElementById("dest-lon");
  const planBtn = document.getElementById("plan-route");
  const swapBtn = document.getElementById("swap-coords");
  const resultsDiv = document.getElementById("route-results");
  const summaryDiv = document.getElementById("route-summary");
  const detailDiv = document.getElementById("route-detail");
  const statusDiv = document.getElementById("route-status");
  const pickBar = document.getElementById("pick-mode-bar");

  function setMarker(type, lat, lon) {
    const color = type === "origin" ? "#30D158" : "#FF453A";
    const icon = L.divIcon({
      html: `<div style="width:20px;height:20px;background:${color};border:3px solid #fff;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.5);"></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
      className: "",
    });

    if (type === "origin") {
      if (originMarker) map.removeLayer(originMarker);
      originMarker = L.marker([lat, lon], { icon }).addTo(map);
      originLat.value = lat.toFixed(6);
      originLon.value = lon.toFixed(6);
    } else {
      if (destMarker) map.removeLayer(destMarker);
      destMarker = L.marker([lat, lon], { icon }).addTo(map);
      destLat.value = lat.toFixed(6);
      destLon.value = lon.toFixed(6);
    }
  }

  document.getElementById("pick-origin").addEventListener("click", function () {
    activePick = "origin";
    pickBar.classList.remove("hidden");
    map.getContainer().style.cursor = "crosshair";
  });

  document.getElementById("pick-dest").addEventListener("click", function () {
    activePick = "dest";
    pickBar.classList.remove("hidden");
    map.getContainer().style.cursor = "crosshair";
  });

  document.getElementById("cancel-pick").addEventListener("click", function () {
    activePick = null;
    pickBar.classList.add("hidden");
    map.getContainer().style.cursor = "";
  });

  map.on("click", function (e) {
    if (!activePick) return;
    setMarker(activePick, e.latlng.lat, e.latlng.lng);
    activePick = null;
    pickBar.classList.add("hidden");
    map.getContainer().style.cursor = "";
  });

  swapBtn.addEventListener("click", function () {
    const olat = originLat.value,
      olon = originLon.value;
    const dlat = destLat.value,
      dlon = destLon.value;
    if (olat && olon && dlat && dlon) {
      originLat.value = dlat;
      originLon.value = dlon;
      destLat.value = olat;
      destLon.value = olon;
      if (originMarker && destMarker) {
        const oLat = originMarker.getLatLng();
        const dLat = destMarker.getLatLng();
        originMarker.setLatLng(dLat);
        destMarker.setLatLng(oLat);
      }
    }
  });

  function clearRoute() {
    routeLines.forEach(function (l) {
      map.removeLayer(l);
    });
    routeLines = [];
    routeMarkers.forEach(function (m) {
      map.removeLayer(m);
    });
    routeMarkers = [];
    resultsDiv.classList.add("hidden");
    statusDiv.classList.add("hidden");
  }

  function renderRoute(data) {
    clearRoute();

    if (data.error) {
      statusDiv.textContent = data.error;
      statusDiv.className = "route-status error";
      statusDiv.classList.remove("hidden");
      return;
    }

    const gj = data.geojson;

    gj.features.forEach(function (f) {
      if (f.geometry.type === "LineString") {
        const props = f.properties;
        let color, weight, dash;

        if (props.type === "walk") {
          color = "#8E8E93";
          weight = 3;
          dash = [8, 8];
        } else if (props.type === "bus") {
          color = props.color || "#F5C518";
          weight = 5;
          dash = false;
        } else {
          color = "#F5C518";
          weight = 4;
          dash = false;
        }

        const opts = {
          color: color,
          weight: weight,
          opacity: 0.9,
          dashArray: dash,
        };
        const line = L.polyline(f.geometry.coordinates.map(function (c) {
          return [c[1], c[0]];
        }), opts).addTo(map);
        routeLines.push(line);
      } else if (f.geometry.type === "Point") {
        const props = f.properties;
        let icon;

        if (props.type === "stop") {
          icon = L.divIcon({
            html: `<div style="width:10px;height:10px;background:#fff;border:2px solid #F5C518;border-radius:50%;"></div>`,
            iconSize: [10, 10],
            iconAnchor: [5, 5],
            className: "",
          });
        } else if (props.type === "transfer_point") {
          const tColor = props.transfer_type === "terminal" ? "#30D158" : "#FF9F0A";
          icon = L.divIcon({
            html: `<div style="width:16px;height:16px;background:${tColor};border:2px solid #fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:700;color:#000;">T</div>`,
            iconSize: [16, 16],
            iconAnchor: [8, 8],
            className: "",
          });
        } else {
          return;
        }

        const marker = L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]], {
          icon: icon,
        }).addTo(map);

        if (props.type === "stop" && props.stop_name) {
          marker.bindTooltip(props.stop_name, { direction: "top" });
        }
        routeMarkers.push(marker);
      }
    });

    const s = data.summary;
    const totalWalk = Math.round(s.origin_walk_m + s.dest_walk_m);
    let stopLines = "";
    if (s.num_buses > 0) {
      stopLines = `
        <div class="summary-stop-line">
          <span class="marker-dot origin"></span>
          <span>${s.origin_stop.stop_name || "Origem"}</span>
        </div>
        <div class="summary-arrow">&darr;</div>
        <div class="summary-stop-line">
          <span class="marker-dest"></span>
          <span>${s.dest_stop.stop_name || "Destino"}</span>
        </div>`;
    } else {
      stopLines = `
        <div class="summary-walk-only">
          <span class="walk-icon">&#x1F6B6;</span>
          <span>Rota a pé &mdash; ${totalWalk}m</span>
        </div>`;
    }
    summaryDiv.innerHTML = `
      <div class="summary-stats">
        <div class="stat">
          <span class="stat-value">${s.num_buses}</span>
          <span class="stat-label">ônibus</span>
        </div>
        <div class="stat">
          <span class="stat-value">${s.num_transfers}</span>
          <span class="stat-label">transferências</span>
        </div>
        <div class="stat">
          <span class="stat-value">${totalWalk}m</span>
          <span class="stat-label">a pé</span>
        </div>
        <div class="stat">
          <span class="stat-value">${s.total_stops}</span>
          <span class="stat-label">pontos</span>
        </div>
      </div>
      <div class="summary-stops">
        ${stopLines}
      </div>
    `;

    let detailHtml = '<div class="segments">';
    data.segments.forEach(function (seg, idx) {
      if (seg.type === "bus") {
        detailHtml += `
          <div class="segment bus-segment">
            <div class="seg-header" style="border-left: 3px solid ${seg.color};">
              <span class="seg-icon">&#x1F68D;</span>
              <span class="seg-route" style="color:${seg.color};">${seg.short_name}</span>
              <span class="seg-dir">${seg.long_name}</span>
            </div>
            <div class="seg-stops">
              <div class="seg-stop first">
                <span class="stop-dot"></span>
                <span class="stop-name">${seg.stop_details[0].stop_name}</span>
              </div>
              <div class="seg-stop-mid hidden" data-idx="${idx}">
                <button class="toggle-stops" data-idx="${idx}">+${seg.stops.length - 2} paradas intermediárias</button>
              </div>
              <div class="seg-stops-list hidden" data-idx="${idx}">
                ${seg.stop_details.slice(1, -1).map(function(s) {
                  return '<div class="seg-stop"><span class="stop-dot"></span><span class="stop-name">' + (s.stop_name || "") + '</span></div>';
                }).join("")}
              </div>
              <div class="seg-stop last">
                <span class="stop-dot"></span>
                <span class="stop-name">${seg.stop_details[seg.stop_details.length - 1].stop_name}</span>
              </div>
            </div>
          </div>
        `;
      } else if (seg.type === "transfer") {
        const label = seg.transfer_type === "terminal" ? "Transferência no terminal" : "Caminhar até";
        detailHtml += `
          <div class="segment transfer-segment">
            <div class="seg-header">
              <span class="seg-icon">&#x1F504;</span>
              <span class="seg-label">${label}</span>
            </div>
            <div class="seg-stops">
              <div class="seg-stop"><span class="stop-dot"></span>${seg.from_info.stop_name}</div>
              <div class="seg-transfer-arrow">&darr;</div>
              <div class="seg-stop"><span class="stop-dot"></span>${seg.to_info.stop_name}</div>
            </div>
          </div>
        `;
      } else if (seg.type === "walk") {
        detailHtml += `
          <div class="segment walk-segment">
            <div class="seg-header">
              <span class="seg-icon">&#x1F6B6;</span>
              <span class="seg-label">Caminhada</span>
            </div>
            <div class="seg-stops">
              <div class="seg-stop"><span class="stop-dot"></span>${seg.from_info.stop_name}</div>
              <div class="seg-stop"><span class="stop-dot"></span>${seg.to_info.stop_name}</div>
            </div>
          </div>
        `;
      }
    });
    detailHtml += "</div>";
    detailDiv.innerHTML = detailHtml;

    detailDiv.querySelectorAll(".toggle-stops").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const idx = this.dataset.idx;
        const list = detailDiv.querySelector('.seg-stops-list[data-idx="' + idx + '"]');
        const mid = detailDiv.querySelector('.seg-stop-mid[data-idx="' + idx + '"]');
        if (list.classList.contains("hidden")) {
          list.classList.remove("hidden");
          mid.classList.add("hidden");
        } else {
          list.classList.add("hidden");
          mid.classList.remove("hidden");
        }
      });
    });

    resultsDiv.classList.remove("hidden");
    statusDiv.classList.add("hidden");

    const allCoords = [];
    gj.features.forEach(function (f) {
      if (f.geometry.type === "LineString") {
        f.geometry.coordinates.forEach(function (c) {
          allCoords.push([c[1], c[0]]);
        });
      }
    });
    if (originMarker) allCoords.push(originMarker.getLatLng());
    if (destMarker) allCoords.push(destMarker.getLatLng());

    if (allCoords.length > 0) {
      map.fitBounds(L.latLngBounds(allCoords).pad(0.15));
    }
  }

  function doPlanRoute() {
    const olat = parseFloat(originLat.value);
    const olon = parseFloat(originLon.value);
    const dlat = parseFloat(destLat.value);
    const dlon = parseFloat(destLon.value);

    if (isNaN(olat) || isNaN(olon) || isNaN(dlat) || isNaN(dlon)) {
      statusDiv.textContent = "Preencha as coordenadas de origem e destino.";
      statusDiv.className = "route-status error";
      statusDiv.classList.remove("hidden");
      return;
    }

    setMarker("origin", olat, olon);
    setMarker("dest", dlat, dlon);

    planBtn.disabled = true;
    planBtn.textContent = "Calculando...";

    const url = "/api/route/plan/?origin_lat=" + olat + "&origin_lon=" + olon + "&dest_lat=" + dlat + "&dest_lon=" + dlon;

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderRoute(data);
      })
      .catch(function (err) {
        statusDiv.textContent = "Erro ao calcular rota: " + err.message;
        statusDiv.className = "route-status error";
        statusDiv.classList.remove("hidden");
      })
      .finally(function () {
        planBtn.disabled = false;
        planBtn.textContent = "Calcular Rota";
      });
  }

  planBtn.addEventListener("click", doPlanRoute);

  // pre-fill sample coords on first visit
  originLat.value = "-25.4284";
  originLon.value = "-49.2733";
  destLat.value = "-25.4353";
  destLon.value = "-49.2706";
  setMarker("origin", -25.4284, -49.2733);
  setMarker("dest", -25.4353, -49.2706);

  const menuToggle = document.getElementById("menu-toggle");
  const panel = document.getElementById("panel");
  const overlay = document.getElementById("panel-overlay");

  menuToggle.addEventListener("click", function () {
    panel.classList.toggle("open");
    menuToggle.classList.toggle("active");
    overlay.classList.toggle("show");
  });

  overlay.addEventListener("click", function () {
    panel.classList.remove("open");
    menuToggle.classList.remove("active");
    overlay.classList.remove("show");
  });
})();
