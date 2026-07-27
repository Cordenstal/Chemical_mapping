# CDR Normalization Plan

- Canonical source path: `cleaned data/2024 CDR Consumer and Commercial Use Information_clean.csv`
- Source type: working data plan
- Why it matters: the current sheet is clean enough to parse, but it is not normalized enough for reliable analysis, joins, or maintainable workbook design.

## What Still Needs Normalization

1. Fix text encoding.
   - Correct mojibake such as `â€“` in headers and range values.
   - Re-save or re-import as UTF-8 so dash and range characters are stable.

2. Split lookup codes from descriptions.
   - Keep codes as keys.
   - Move labels into lookup tables.
   - This applies to fields such as:
     - `PCT BYP CODE` / `PERCENT BYPRODUCT`
     - `WORKERS CODE` / `WORKERS REASONABLY LIKELY EXPOSED`
     - `MAX CONC CODE` / `MAXIMUM CONCENTRATION`
     - `C / C PROD CAT CODE` / `CONSUMER / COMMERCIAL PRODUCT CATEGORY`
     - `C / C FC CODE` / `CONSUMER / COMMERCIAL FUNCTION CATEGORY`
     - `JOINT FC CODE` / `JOINT FUNCTION CATEGORY`

3. Split multi-valued fields into child rows.
   - `PHYSICAL FORM(S) LIST` is not atomic.
   - Values like `Dry Powder; Liquid` should be unpivoted into one row per physical form.

4. Separate sparse conditional sections.
   - Consumer/commercial columns are populated on only part of the file.
   - Joint-function columns are even sparser.
   - These should become child tables rather than remain as mostly blank columns in the core sheet.

5. Convert types deliberately.
   - Latitude and longitude should be numeric.
   - Percent and range fields should be normalized into analyzable numeric or bounded formats.
   - IDs, postal codes, and codes should remain text.

6. Treat sentinel values as explicit states.
   - `CBI`
   - `NKRA`
   - blanks vs unknown vs confidential values

7. Resolve inconsistent code-label mappings.
   - `WORKERS CODE` maps multiple labels for the same code in the current file.
   - `MAX CONC CODE` also has a code-label inconsistency.
   - These need canonical lookup values before any final normalization.

## Recommended Target Structure

- `chemical`
  - Chemical identity and identifier fields.
- `company_parent`
  - Standardized parent company records.
- `site`
  - Facility and location data.
- `site_activity`
  - NAICS and activity fields tied to a site.
- `chemical_use`
  - Activity, production volume, exposure, and consumer/commercial use records.
- `physical_form_lookup`
  - Standard forms and code mappings.
- `consumer_product_category_lookup`
  - Consumer/commercial product category codes.
- `consumer_function_lookup`
  - Consumer/commercial function codes.
- `joint_function_lookup`
  - Joint-use function codes.

## Practical Cleanup Order

1. Fix encoding.
2. Normalize code/description pairs.
3. Standardize datatypes and sentinel values.
4. Split multi-valued physical form data.
5. Break the wide sheet into core and child tables.

## Validation Checks

- Every code should map to exactly one canonical description.
- Every multi-valued field should be decomposed into atomic rows.
- Every numeric column should be parseable as numeric after cleanup.
- Every blank column group should be checked for whether it belongs in a separate child table.

- Last reviewed date: 2026-06-18
