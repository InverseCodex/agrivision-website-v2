// static/map.js
// - Loads GeoJSON from /geojson/targets
// - Clicking a GeoJSON feature sets #latitude-value and #longitude-value
// - Clicking ANYWHERE on the map also sets #latitude-value and #longitude-value
// - Adds/moves a marker to the selected target
// - Works with hidden tabs (invalidateSize)

window.leafletMap = null;
window.leafletMarker = null;

function setLatLngUI(lat, lng) {
  const latEl = document.getElementById("latitude-value");
  const lngEl = document.getElementById("longitude-value");

  if (latEl) latEl.textContent = Number(lat).toFixed(6);
  if (lngEl) lngEl.textContent = Number(lng).toFixed(6);
}

function setMarker(lat, lng) {
  if (!window.leafletMarker) return;
  window.leafletMarker.setLatLng([lat, lng]);
}

function hardInvalidate() {
  if (!window.leafletMap) return;
  requestAnimationFrame(() => {
    window.leafletMap.invalidateSize(true);
    setTimeout(() => window.leafletMap.invalidateSize(true), 150);
    setTimeout(() => window.leafletMap.invalidateSize(true), 400);
  });
}

async function loadAndBindGeoJSON() {
  const res = await fetch("/geojson/targets");
  if (!res.ok) throw new Error(`GeoJSON fetch failed: ${res.status}`);
  const geojson = await res.json();

  const layer = L.geoJSON(geojson, {
    onEachFeature: (feature, lyr) => {
      lyr.on("click", (e) => {
        // ✅ Prevent the map click handler from also firing
        L.DomEvent.stop(e);

        // Point feature: use geometry coords [lng, lat]
        if (feature.geometry?.type === "Point") {
          const [lng, lat] = feature.geometry.coordinates;
          setLatLngUI(lat, lng);
          setMarker(lat, lng);
          window.leafletMap.panTo([lat, lng]);
          return;
        }

        // Other types: use clicked location
        const { lat, lng } = e.latlng;
        setLatLngUI(lat, lng);
        setMarker(lat, lng);
      });
    },
  }).addTo(window.leafletMap);

  // zoom to features if possible
  try {
    window.leafletMap.fitBounds(layer.getBounds());
  } catch (_) {}
}

window.initMissionMap = async function initMissionMap() {
  if (window.leafletMap) return;

  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  // Create map
  window.leafletMap = L.map("map").setView([14.5995, 120.9842], 11);

  // Tiles (use OSM; if you ever get blocked, switch to CARTO)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(window.leafletMap);

  // Default marker
  window.leafletMarker = L.marker([14.5995, 120.9842]).addTo(window.leafletMap);

  // ✅ NEW: Click anywhere on the map to set target lat/lng
  window.leafletMap.on("click", (e) => {
    const { lat, lng } = e.latlng;
    setLatLngUI(lat, lng);
    setMarker(lat, lng);
  });

  // Load GeoJSON + click-to-fill
  try {
    await loadAndBindGeoJSON();
  } catch (err) {
    console.error("GeoJSON error:", err);
  }

  hardInvalidate();
};

window.fixMissionMapSize = function fixMissionMapSize() {
  hardInvalidate();
};
