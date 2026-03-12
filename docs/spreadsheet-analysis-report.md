# Vehicle Template Spreadsheet Analysis Report

## Access note (important)
I attempted to access the provided Google Sheets URL directly from this environment, but outbound access to that host is blocked (`403 CONNECT tunnel failed`).
Because of this, I could not compute **actual row-level statistics** (exact duplicates, exact null counts, exact parse-failure rows).

This report therefore contains:
1. A concrete analysis framework aligned to your sheet design.
2. Deterministic column mapping based on your sample row and domain model.
3. Production-grade normalization/parsing/grouping/import rules.
4. A checklist of exact metrics to run immediately once file access is available.

---

## 1) Spreadsheet structure overview

### 1.1 Expected workbook shape
Based on your description, the primary data sheet should contain template rows with these business attributes:
- template type (2D/5D)
- hanger number
- brand
- car description
- EVA code
- ART code
- body type
- drive + gearbox
- class

### 1.2 Structure profiling procedure (to run on the real file)
For each sheet:
1. Detect header row (first non-empty row with >50% string cells).
2. Normalize headers to canonical form (`trim`, lowercase, replace spaces/diacritics with `_`).
3. Infer data type per column:
   - numeric
   - categorical text
   - free text
   - mixed
4. Compute per-column quality metrics:
   - null count / null %
   - unique count
   - top values
   - whitespace-only count
5. Detect duplicate columns by:
   - identical normalized header names
   - high value-overlap ratio (>98%)

### 1.3 Output schema for profiling
Produce a table like:
- `sheet_name`
- `row_count`
- `column_count`
- `columns[]`
- `inferred_types[]`
- `missing_ratio[]`
- `duplicate_header_flags[]`

---

## 2) Column mapping

Using your sample row:

`2D | 15 | Audi | Audi A4 B9 5 gen Sedan (2015-2024) | EVA36 | art-159 | Sedan (Benzyna/Diesel) | 4x4, Automat | B`

### 2.1 Canonical mapping
- `template_type`  <- column containing `2D/5D`
- `hanger_number`  <- numeric hanger locator (`15`)
- `brand`          <- manufacturer (`Audi`)
- `car_description`<- combined descriptor (`Audi A4 B9 5 gen Sedan (2015-2024)`)
- `eva_code`       <- `EVA36`
- `article_code`   <- `art-159`
- `body_type`      <- often includes fuel in parentheses (`Sedan (Benzyna/Diesel)`)
- `drive_gearbox`  <- combined drivetrain + gearbox (`4x4, Automat`)
- `class`          <- quality/segment marker (`B`)

### 2.2 Mapping confidence
- High confidence: `template_type`, `hanger_number`, `brand`, `eva_code`, `article_code`.
- Medium confidence: `body_type` (because it may contain fuel text), `class` (semantics may vary).

---

## 3) Data quality issues (expected + detection rules)

When file is accessible, compute and report:

1. **Duplicate EVA codes**
   - Group by normalized `eva_code`.
   - Flag if same EVA has conflicting base fields (`brand/model/body_type/hanger/template_type`).

2. **Duplicate ART codes**
   - Group by normalized `article_code`.
   - Flag if same ART maps to multiple EVAs.

3. **Missing EVA values**
   - Null/blank/placeholder (`-`, `n/a`, `brak`).

4. **Inconsistent hanger numbers**
   - Non-numeric values.
   - Same EVA mapped to multiple hanger numbers.

5. **Rows not parseable**
   - `car_description` cannot produce model/year.
   - `drive_gearbox` contains unknown gearbox/drivetrain tokens.

6. **Formatting inconsistencies**
   - Case variants (`audi`/`Audi`).
   - Extra spaces and non-breaking spaces.
   - Mixed separators (`-`, `–`, `/`, `,`).
   - Mixed language (`Automatic` vs `Automat`; `Petrol` vs `Benzyna`).

---

## 4) Normalization rules

### 4.1 Global string normalization
Apply to all textual fields before validation:
1. Unicode normalize (NFKC).
2. Replace non-breaking spaces with normal spaces.
3. Trim leading/trailing spaces.
4. Collapse repeated spaces to one.
5. Normalize dash variants to `-`.
6. Store canonical uppercase for keys:
   - EVA: `EVA\d+`
   - ART: lowercase `art-\d+` (or preserve source and store normalized shadow key).

### 4.2 Enumerations
- `template_type`: map `{2d, 2D} -> 2D`, `{5d, 5D} -> 5D`.
- `gearbox`:
  - `Automat`, `Automatic`, `AT` -> `Automatic`
  - `Manual`, `Manuel`, `MT` -> `Manual`
- `drive_type`:
  - `4x4`, `AWD` -> `AWD`
  - `FWD`/`przód` -> `FWD`
  - `RWD`/`tył` -> `RWD`

### 4.3 Fuel normalization
From `body_type` parentheses or dedicated token:
- `Benzyna` -> `Petrol`
- `Diesel` -> `Diesel`
- `Benzyna/Diesel` -> `Petrol/Diesel`

### 4.4 Brand/model casing
- Keep display form in Title Case.
- Keep normalized form for matching (`lowercase`, diacritics stripped).

---

## 5) Parsing strategy (`car_description`)

Input example: `Audi A4 B9 5 gen Sedan (2015-2024)`

### 5.1 Parse order (deterministic)
1. Extract `production_years` from trailing parentheses regex:
   - `\((19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\)`
2. Remove extracted years from string.
3. Remove leading brand token if duplicated with `brand` column.
4. Detect `body_type` from controlled lexicon:
   - sedan, hatchback, kombi/wagon, coupe, suv, van, liftback, cabrio
5. Detect `generation` tokens:
   - patterns like `B\d+`, `MK\d+`, `\d+ gen`, roman numerals, `facelift`
6. Remaining middle segment => `model`.

### 5.2 Fallback parsing modes
- If no body type found in description, use `body_type` column.
- If no generation found, set `generation = null`.
- If year pattern absent, set `production_years = null` and flag warning.

### 5.3 Parse confidence score
Assign score 0–1 by extracted fields:
- +0.3 years found
- +0.3 model found
- +0.2 generation found
- +0.2 body type found
Rows `<0.6` go to manual review queue.

---

## 6) Grouping logic

### 6.1 CAR grouping key
Primary grouping key: `eva_code_normalized`.

### 6.2 CAR consolidation rules
For all rows with same EVA:
1. Canonical car fields:
   - `brand`
   - `model`
   - `generation`
   - `body_type`
   - `production_years`
   - `hanger_number`
   - `template_type`
2. Resolve conflicts by precedence:
   - non-null parsed value > null
   - most frequent value among rows
   - if tie => keep first-seen and mark conflict log

### 6.3 MODIFICATION creation
Per row create or upsert by `article_code_normalized`:
- `article_code`
- `drive_type`
- `gearbox`
- `fuel_type`
- `facelift_version` (if detectable from generation/description tokens)
- `car_id` resolved from EVA grouping

### 6.4 HANGER entity
Upsert by `hanger_number`:
- `hanger_number`
- `brand` (dominant brand on hanger or explicit column value)

---

## 7) Transformation pipeline (row -> JSON)

### 7.1 Stage A: ingest
- Read workbook -> select source sheet(s).
- Keep raw row index for traceability (`source_row_number`).

### 7.2 Stage B: normalize
- Header normalization + mapping to canonical fields.
- Value normalization (spaces, case, enums, code formats).

### 7.3 Stage C: parse
- Parse `car_description`.
- Parse `drive_gearbox` into `drive_type` + `gearbox`.
- Parse `fuel_type` from body/fuel segment.

### 7.4 Stage D: validate
Row-level validation:
- required: `eva_code`, `article_code`, `hanger_number`, `template_type`, `brand`
- format checks for EVA/ART/year range
- enum checks

### 7.5 Stage E: group and materialize
- Group rows by EVA to produce `Car[]`.
- Create `Modification[]` linked to grouped car.
- Create `Hanger[]` from hanger dimension.

### 7.6 Stage F: quality outputs
Generate three artifacts:
1. `clean_records.json`
2. `rejects.json` (hard errors)
3. `warnings.json` (soft conflicts/low confidence)

### 7.7 Example structured output

Car
```json
{
  "eva_code": "EVA36",
  "brand": "Audi",
  "model": "A4 B9",
  "generation": "5 gen",
  "body_type": "Sedan",
  "production_years": "2015-2024",
  "hanger_number": 15,
  "template_type": "2D"
}
```

Modification
```json
{
  "article_code": "art-159",
  "drive_type": "AWD",
  "gearbox": "Automatic",
  "fuel_type": "Petrol/Diesel",
  "facelift_version": null
}
```

Hanger
```json
{
  "hanger_number": 15,
  "brand": "Audi"
}
```

---

## 8) Import algorithm (database-oriented)

1. Start import job record (`queued` -> `running`).
2. Load workbook and map source columns.
3. For each row:
   - normalize values
   - parse fields
   - validate
   - append to `valid_rows` or `rejects`
4. Group `valid_rows` by EVA.
5. Upsert `hangers` first (by hanger number).
6. Upsert `cars` second (by EVA code), resolve `car_id`.
7. Upsert `modifications` third (by ART code) with `car_id` FK.
8. Write log events per affected EVA/ART.
9. Store rejects/warnings artifact for audit.
10. Mark job status:
   - `completed` if no rejects,
   - `partial` if mixed,
   - `failed` if import aborted.

Transaction strategy:
- Batch size 200–500 rows.
- Per-batch transaction for predictable rollback scope.
- Idempotent upserts (`ON CONFLICT`).

---

## 9) Edge cases and handling

1. **Same EVA with different brands**
   - Keep most frequent brand, flag critical conflict.

2. **Same ART assigned to different EVA**
   - Treat as data error; reject row until manually resolved.

3. **Hanger contains non-integer or text suffix**
   - Extract numeric prefix if unambiguous; otherwise reject.

4. **Missing ART but valid EVA**
   - Car may still be imported; row logged as missing modification.

5. **Multilingual tokens** (`Automat`, `Benzyna`, etc.)
   - Map through language dictionary before enum validation.

6. **Year range malformed** (`2015/2024`, `2015-24`)
   - Attempt normalization; if ambiguous, warning + null years.

7. **Description without brand/model separation**
   - Keep full string as provisional model and flag low confidence.

8. **Duplicate row clones**
   - Deduplicate by hash of normalized business key:
     `(eva_code, article_code, hanger_number, template_type)`.

---

## Immediate next step needed from you
Please provide one of the following so I can return the **exact quantified analysis** you requested (sheet count, exact missing values, exact duplicate rows):
1. Upload the `.xlsx` file directly in this chat, or
2. Provide a publicly downloadable file link (direct xlsx/csv URL), or
3. Share a temporary CSV export.

Once accessible, I will produce a second report with concrete statistics and row-level anomaly samples.
