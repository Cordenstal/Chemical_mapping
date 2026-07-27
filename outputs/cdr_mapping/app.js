const DATA = {
  facilities: "public_facilities.geojson",
  records: "public_cdr_records.geojson",
  index: "chemical_index.json",
  metadata: "dashboard_metadata.json",
};

const state = {
  map: null,
  facilities: [],
  records: [],
  chemicals: [],
  facilityActivities: new Map(),
  selectedChemical: null,
  facilityLayer: null,
  recordLayer: null,
  recordRenderer: null,
  refreshTimer: null,
};

const $ = (id) => document.getElementById(id);
const number = (value) => new Intl.NumberFormat().format(value || 0);

function activityClass(activityValues) {
  const values = Array.isArray(activityValues) ? activityValues : [activityValues];
  const normalized = values.map((value) => String(value || "").toLowerCase());
  const hasImport = normalized.some((value) => value.includes("import"));
  const hasManufacture = normalized.some((value) => value.includes("manufact"));
  if (hasManufacture && !hasImport && normalized.filter(Boolean).length === 1) return "manufacture";
  if (hasImport && !hasManufacture && normalized.filter(Boolean).length === 1) return "import";
  return "other";
}

function activityColor(activityValues) {
  const classification = activityClass(activityValues);
  if (classification === "import") return "#d26b27";
  if (classification === "manufacture") return "#1167a8";
  return "#3f8b65";
}

function activityLabel(activityValues) {
  const classification = activityClass(activityValues);
  if (classification === "manufacture") return "Manufacture";
  if (classification === "import") return "Import";
  return "Other / Combined";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[character]));
}

function properties(feature) { return feature.properties || {}; }

function popup(title, values) {
  const rows = values.filter((pair) => pair[1] !== undefined && pair[1] !== "").map((pair) => `<dt>${escapeHtml(pair[0])}</dt><dd>${escapeHtml(pair[1])}</dd>`).join("");
  return `<h3 class="popup-title">${escapeHtml(title)}</h3><dl class="popup-grid">${rows}</dl>`;
}

function facilityIcon(item) {
  const p = properties(item);
  const activities = state.facilityActivities.get(p.facility_id) || [];
  const color = activityColor(activities);
  const cbi = Number(p.has_cbi_volume) ? " has-cbi" : "";
  return L.divIcon({ className: "", html: `<span class="facility-marker${cbi}" style="background:${color}"></span>`, iconSize: [15, 15], iconAnchor: [7, 7] });
}

function recordIcon(item) {
  const p = properties(item);
  return L.divIcon({ className: "", html: `<span class="record-marker" style="background:${activityColor(p.activity)}"></span>`, iconSize: [9, 9], iconAnchor: [4, 4] });
}

function currentFilters() {
  const activity = $("activity-filter").value.toLowerCase();
  const facilityText = $("facility-search").value.trim().toLowerCase();
  return { activity, facilityText, cbiOnly: $("cbi-toggle").checked };
}

function matches(p, filters) {
  const activityMatch = !filters.activity || String(p.activity || "").toLowerCase() === filters.activity;
  const facilityMatch = !filters.facilityText || [p.site_name, p.site_city, p.site_state].some((value) => String(value || "").toLowerCase().includes(filters.facilityText));
  const cbiMatch = !filters.cbiOnly || Number(p.has_cbi_volume) === 1;
  const chemicalMatch = !state.selectedChemical || p.chemical_key === state.selectedChemical.chemical_key;
  return activityMatch && facilityMatch && cbiMatch && chemicalMatch;
}

function facilityFeatures() {
  const matchingRecords = recordFeatures();
  const matchingFacilities = new Set(matchingRecords.map((feature) => properties(feature).facility_id));
  const filters = currentFilters();
  if (!state.selectedChemical && !filters.activity && !filters.facilityText && !filters.cbiOnly) return state.facilities;
  return state.facilities.filter((feature) => matchingFacilities.has(properties(feature).facility_id));
}

function recordFeatures() {
  return state.records.filter((feature) => matches(properties(feature), currentFilters()));
}

function refreshLayers() {
  if (!state.map) return;
  const facilityItems = facilityFeatures();
  const facilityMarkers = facilityItems.map((feature) => {
    const p = properties(feature);
    const activities = state.facilityActivities.get(p.facility_id) || [];
    return L.marker([feature.geometry.coordinates[1], feature.geometry.coordinates[0]], { icon: facilityIcon(feature) }).bindPopup(popup(p.site_name || "Facility", [
      ["City / state", `${p.site_city || ""}${p.site_city && p.site_state ? ", " : ""}${p.site_state || ""}`],
      ["Facility ID", p.facility_id], ["Public records", number(p.source_record_count)], ["Chemicals", number(p.chemical_count)],
      ["Activity class", activityLabel(activities)], ["Reported activities", activities.join(", ") || "Unavailable"], ["CBI-volume indicator", Number(p.has_cbi_volume) ? "Present; value withheld" : "Not present in public point layer"], ["Location precision", p.location_precision]
    ]));
  });
  state.facilityLayer.clearLayers().addLayers(facilityMarkers);

  const matchingRecords = recordFeatures();
  const recordItems = $("records-toggle").checked ? matchingRecords : [];
  state.recordLayer.clearLayers();
  recordItems.forEach((feature) => {
    const p = properties(feature);
    L.circleMarker([feature.geometry.coordinates[1], feature.geometry.coordinates[0]], { renderer: state.recordRenderer, radius: 3, color: "#ffffff", weight: 0.7, fillColor: activityColor(p.activity), fillOpacity: 0.82 }).bindPopup(popup(p.chemical_name || p.chemical_key || "Record", [
      ["CAS / chemical key", p.chemical_key], ["Facility", p.site_name], ["City / state", `${p.site_city || ""}${p.site_city && p.site_state ? ", " : ""}${p.site_state || ""}`], ["Activity", p.activity], ["Source row", p.source_row_id], ["CBI-volume indicator", Number(p.has_cbi_volume) ? "Present; value withheld" : "Not indicated"], ["Location precision", p.location_precision]
    ])).addTo(state.recordLayer);
  });
  updateSummary(facilityItems, matchingRecords);
  $("load-status").textContent = `${number(facilityItems.length)} facilities shown`;
}

function scheduleRefresh() {
  window.clearTimeout(state.refreshTimer);
  state.refreshTimer = window.setTimeout(refreshLayers, 80);
}

function updateSummary(facilityItems, recordItems) {
  const selected = state.selectedChemical;
  const metadata = state.metadata || {};
  const cbiLocations = selected ? selected.withheld_location_record_count : metadata.cbi_location_record_count;
  const cbiVolume = selected ? selected.public_has_cbi_volume_record_count : recordItems.filter((feature) => Number(properties(feature).has_cbi_volume) === 1).length;
  $("summary-title").textContent = selected ? selected.chemical_name : "All public records";
  $("metric-facilities").textContent = number(facilityItems.length);
  $("metric-records").textContent = number(recordItems.length);
  $("metric-cbi-location").textContent = number(cbiLocations);
  $("metric-cbi-volume").textContent = number(cbiVolume);
  $("summary-detail").textContent = selected ? `${selected.chemical_key} · ${number(selected.public_state_count)} states · CBI location records remain unlocated.` : "Select a chemical to narrow the map. Counts are based on the Phase 2 public spatial layer.";
}

function renderSearchResults(query) {
  const normalized = query.trim().toLowerCase();
  const results = normalized ? state.chemicals.filter((item) => `${item.chemical_key} ${item.chemical_name}`.toLowerCase().includes(normalized)).slice(0, 12) : [];
  $("chemical-results").innerHTML = results.map((item) => `<button class="search-result" data-chemical="${escapeHtml(item.chemical_key)}" type="button"><strong>${escapeHtml(item.chemical_name)}</strong><small>${escapeHtml(item.chemical_key)} · ${number(item.public_record_count)} public records</small></button>`).join("");
  document.querySelectorAll("[data-chemical]").forEach((button) => button.addEventListener("click", () => selectChemical(button.dataset.chemical)));
}

function selectChemical(chemicalKey) {
  state.selectedChemical = state.chemicals.find((item) => item.chemical_key === chemicalKey) || null;
  $("chemical-search").value = state.selectedChemical ? `${state.selectedChemical.chemical_name} (${state.selectedChemical.chemical_key})` : "";
  $("chemical-results").innerHTML = "";
  refreshLayers();
  const visible = facilityFeatures();
  if (visible.length) {
    const bounds = L.latLngBounds(visible.map((feature) => [feature.geometry.coordinates[1], feature.geometry.coordinates[0]]));
    state.map.fitBounds(bounds.pad(.12), { maxZoom: 10 });
  }
}

function initMap() {
  state.map = L.map("map", { preferCanvas: true }).setView([39.5, -98.35], 4);
  const topo = L.tileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}", { maxZoom: 16, attribution: "USGS The National Map" });
  const imagery = L.tileLayer("https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}", { maxZoom: 16, attribution: "USGS The National Map" });
  topo.addTo(state.map);
  L.control.layers({ "USGS Topo": topo, "USGS Imagery": imagery }).addTo(state.map);
  state.facilityLayer = L.markerClusterGroup({ chunkedLoading: true, showCoverageOnHover: false });
  state.recordLayer = L.layerGroup();
  state.recordRenderer = L.canvas({ padding: 0.5 });
  state.facilityLayer.addTo(state.map);
  state.recordLayer.addTo(state.map);
}

function bindControls() {
  $("chemical-search").addEventListener("input", (event) => renderSearchResults(event.target.value));
  ["facility-search", "activity-filter", "records-toggle", "cbi-toggle"].forEach((id) => $(id).addEventListener("input", scheduleRefresh));
  $("clear-selection").addEventListener("click", () => { state.selectedChemical = null; $("chemical-search").value = ""; $("chemical-results").innerHTML = ""; refreshLayers(); state.map.setView([39.5, -98.35], 4); });
}

async function load() {
  initMap();
  bindControls();
  let facilities;
  let records;
  let index;
  let metadata;
  if (window.CDR_DASHBOARD_DATA) {
    ({ facilities, records, index, metadata } = window.CDR_DASHBOARD_DATA);
  } else {
    [facilities, records, index, metadata] = await Promise.all(Object.values(DATA).map((path) => fetch(path).then((response) => { if (!response.ok) throw new Error(`${path}: ${response.status}`); return response.json(); })));
  }
  state.facilities = facilities.features || [];
  state.records = records.features || [];
  state.chemicals = index.chemicals || [];
  state.metadata = metadata;
  state.facilityActivities = new Map();
  state.records.forEach((feature) => {
    const p = properties(feature);
    if (!state.facilityActivities.has(p.facility_id)) state.facilityActivities.set(p.facility_id, new Set());
    if (p.activity) state.facilityActivities.get(p.facility_id).add(p.activity);
  });
  state.facilityActivities = new Map(Array.from(state.facilityActivities.entries()).map(([facilityId, activities]) => [facilityId, Array.from(activities).sort()]));
  const activities = new Set(state.records.map((feature) => properties(feature).activity).filter(Boolean));
  Array.from(activities).sort().forEach((activity) => $("activity-filter").insertAdjacentHTML("beforeend", `<option value="${escapeHtml(activity)}">${escapeHtml(activity)}</option>`));
  refreshLayers();
}

load().catch((error) => { $("load-status").textContent = "Map data failed to load"; $("summary-detail").textContent = error.message; console.error(error); });
