# CDR Mapping Phase 3 Interactive Dashboard

## Scope

Phase 3 turns the validated Phase 2 spatial layer into a portable, local interactive map. It is a dashboard prototype, not an external facility-resolution or FRS matching service.

## Current build

- Source dashboard: `app/cdr_mapping_dashboard/`
- Checked-in generated dashboard: `outputs/cdr_mapping/`
- Public chemicals indexed: 7,404
- Source-record points available: 50,056
- Facility points available: 4,279
- CBI locations: summarized but not mapped
- Numeric volume/value fields: not displayed

## Dashboard behavior

- Searches by chemical name, CAS/chemical key, and partial text.
- Filters by facility/city and reported activity.
- Colors facility markers by the activity mix across their public records: blue for Manufacture-only, orange for Import-only, and green for Other / Combined.
- Switches between grouped facility points and source-record points.
- Highlights records carrying a CBI-volume indicator without assigning a numeric value.
- Shows facility and record details with source row IDs and location precision.
- Uses USGS Topo and USGS Imagery National Map services as selectable basemaps.
- Uses clustering for national-scale navigation.
- Supports direct opening of `index.html` through an embedded local data payload; no local HTTP server is required.

## Trust and limitations

The default map uses public Phase 2 source coordinates. The dashboard labels the coordinate precision and does not treat a reporting location as a port of entry or downstream-use location. CBI locations are not inferred from company names, neighboring facilities, or related records. FRS enrichment and numeric volume symbology remain outside this phase.

## Run locally

Double-click `app/cdr_mapping_dashboard/index.html` (or `outputs/cdr_mapping/index.html`). The browser needs network access to load Leaflet, MarkerCluster, and USGS basemap tiles from their public services.
