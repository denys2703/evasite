# Vehicle Catalog Web App

Minimal Apple-style vehicle catalog with automatic Google Sheets sync.

## Features
- Catalog cards with `ID Brand` label and status badge.
- Vehicle detail page with clean table layout and description section.
- Inline status updates (`Available`, `Needs Scan`, `Missing`, `Processing`).
- Filters for brand, status, location, and year.
- Google Sheets as the system of record (read + write sync).

## Google Sheets setup
1. Create a Google Cloud service account with Sheets API access.
2. Share your Google Sheet with the service account email.
3. Set environment variables:

```bash
export GOOGLE_SHEET_ID="your-sheet-id"
export GOOGLE_SHEET_RANGE="Vehicles!A:H"
export GOOGLE_SHEET_TAB="Vehicles"
export GOOGLE_SERVICE_ACCOUNT_EMAIL="service-account@project.iam.gserviceaccount.com"
export GOOGLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

Each row in the selected range must follow this order:

`ID | Brand | Model | Year | VIN | Status | Location | Description`

## Run
```bash
npm start
```

Open http://localhost:3000.

> If Google credentials are missing, the app uses `data/vehicles.json` as a local fallback dataset.
