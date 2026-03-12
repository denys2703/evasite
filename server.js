const http = require('http');
const fs = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const { URL } = require('url');

const PORT = Number(process.env.PORT || 3000);
const PUBLIC_DIR = path.join(__dirname, 'public');
const FALLBACK_DATA_PATH = path.join(__dirname, 'data', 'vehicles.json');
const VALID_STATUSES = ['Available', 'Needs Scan', 'Missing', 'Processing'];

class VehicleStore {
  constructor() {
    this.sheetId = process.env.GOOGLE_SHEET_ID || '';
    this.range = process.env.GOOGLE_SHEET_RANGE || 'Vehicles!A:H';
    this.sheetTab = process.env.GOOGLE_SHEET_TAB || this.range.split('!')[0];
    this.serviceEmail = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL || '';
    this.privateKey = (process.env.GOOGLE_PRIVATE_KEY || '').replace(/\\n/g, '\n');
    this.cachedToken = { token: null, exp: 0 };
  }

  get hasGoogleConfig() {
    return Boolean(this.sheetId && this.serviceEmail && this.privateKey);
  }

  async listVehicles() {
    if (!this.hasGoogleConfig) {
      return this.readFallbackVehicles();
    }

    const values = await this.readSheetValues();
    return this.sheetRowsToVehicles(values);
  }

  async updateVehicleStatus(id, status) {
    if (!VALID_STATUSES.includes(status)) {
      throw new Error('Invalid status value.');
    }

    if (!this.hasGoogleConfig) {
      const vehicles = await this.readFallbackVehicles();
      const target = vehicles.find((v) => v.id === id);
      if (!target) {
        return null;
      }
      target.status = status;
      await fs.writeFile(FALLBACK_DATA_PATH, JSON.stringify(vehicles, null, 2));
      return target;
    }

    const values = await this.readSheetValues();
    const { rowNumber, vehicle } = this.findVehicleInRows(values, id);
    if (!rowNumber) {
      return null;
    }

    await this.writeSheetCell(`${this.sheetTab}!F${rowNumber}`, [[status]]);
    return { ...vehicle, status };
  }

  async readFallbackVehicles() {
    const raw = await fs.readFile(FALLBACK_DATA_PATH, 'utf8');
    return JSON.parse(raw);
  }

  sheetRowsToVehicles(values) {
    if (!Array.isArray(values)) {
      return [];
    }

    const rows = this.normalizeRows(values);
    return rows.map((row) => ({
      id: (row[0] || '').trim(),
      brand: (row[1] || '').trim(),
      model: (row[2] || '').trim(),
      year: (row[3] || '').trim(),
      vin: (row[4] || '').trim(),
      status: (row[5] || '').trim(),
      location: (row[6] || '').trim(),
      description: (row[7] || '').trim()
    })).filter((vehicle) => vehicle.id);
  }

  normalizeRows(values) {
    if (values.length === 0) {
      return [];
    }

    const first = values[0][0] ? values[0][0].toString().trim().toLowerCase() : '';
    if (first === 'id') {
      return values.slice(1);
    }

    return values;
  }

  findVehicleInRows(values, id) {
    const hasHeader = values[0] && values[0][0] && values[0][0].toString().trim().toLowerCase() === 'id';
    const startIndex = hasHeader ? 1 : 0;

    for (let i = startIndex; i < values.length; i += 1) {
      const row = values[i];
      if ((row[0] || '').toString().trim() === id) {
        return {
          rowNumber: i + 1,
          vehicle: {
            id: (row[0] || '').trim(),
            brand: (row[1] || '').trim(),
            model: (row[2] || '').trim(),
            year: (row[3] || '').trim(),
            vin: (row[4] || '').trim(),
            status: (row[5] || '').trim(),
            location: (row[6] || '').trim(),
            description: (row[7] || '').trim()
          }
        };
      }
    }

    return { rowNumber: null, vehicle: null };
  }

  async readSheetValues() {
    const token = await this.getAccessToken();
    const encodedRange = encodeURIComponent(this.range);
    const url = `https://sheets.googleapis.com/v4/spreadsheets/${this.sheetId}/values/${encodedRange}`;
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Unable to read Google Sheet: ${response.status} ${errText}`);
    }

    const data = await response.json();
    return data.values || [];
  }

  async writeSheetCell(range, values) {
    const token = await this.getAccessToken();
    const encodedRange = encodeURIComponent(range);
    const url = `https://sheets.googleapis.com/v4/spreadsheets/${this.sheetId}/values/${encodedRange}?valueInputOption=RAW`;

    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ range, values })
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Unable to update Google Sheet: ${response.status} ${errText}`);
    }
  }

  async getAccessToken() {
    const now = Math.floor(Date.now() / 1000);
    if (this.cachedToken.token && this.cachedToken.exp - 60 > now) {
      return this.cachedToken.token;
    }

    const jwt = this.buildJwt(now);
    const body = new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: jwt
    });

    const response = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Unable to authenticate with Google: ${response.status} ${errText}`);
    }

    const data = await response.json();
    this.cachedToken = {
      token: data.access_token,
      exp: now + Number(data.expires_in || 3600)
    };

    return this.cachedToken.token;
  }

  buildJwt(now) {
    const header = { alg: 'RS256', typ: 'JWT' };
    const payload = {
      iss: this.serviceEmail,
      scope: 'https://www.googleapis.com/auth/spreadsheets',
      aud: 'https://oauth2.googleapis.com/token',
      exp: now + 3600,
      iat: now
    };

    const encodedHeader = this.base64url(JSON.stringify(header));
    const encodedPayload = this.base64url(JSON.stringify(payload));
    const content = `${encodedHeader}.${encodedPayload}`;

    const signer = crypto.createSign('RSA-SHA256');
    signer.update(content);
    signer.end();
    const signature = signer.sign(this.privateKey);

    return `${content}.${this.base64url(signature)}`;
  }

  base64url(input) {
    const buff = Buffer.isBuffer(input) ? input : Buffer.from(input);
    return buff.toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  }
}

const store = new VehicleStore();

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  });
  res.end(JSON.stringify(payload));
}

async function readJsonBody(req) {
  let raw = '';
  for await (const chunk of req) {
    raw += chunk;
  }
  return raw ? JSON.parse(raw) : {};
}

function mimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.html': return 'text/html; charset=utf-8';
    case '.css': return 'text/css; charset=utf-8';
    case '.js': return 'application/javascript; charset=utf-8';
    case '.json': return 'application/json; charset=utf-8';
    default: return 'text/plain; charset=utf-8';
  }
}

async function serveStatic(req, res, pathname) {
  const target = pathname === '/' ? '/index.html' : pathname;
  const safePath = path.normalize(target).replace(/^\.+/, '');
  const filePath = path.join(PUBLIC_DIR, safePath);

  if (!filePath.startsWith(PUBLIC_DIR)) {
    sendJson(res, 403, { error: 'Forbidden' });
    return;
  }

  try {
    const data = await fs.readFile(filePath);
    res.writeHead(200, { 'Content-Type': mimeType(filePath) });
    res.end(data);
  } catch (error) {
    sendJson(res, 404, { error: 'Not found' });
  }
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/api/vehicles' && req.method === 'GET') {
      const vehicles = await store.listVehicles();
      sendJson(res, 200, { vehicles, source: store.hasGoogleConfig ? 'google-sheets' : 'local-fallback' });
      return;
    }

    if (url.pathname.startsWith('/api/vehicles/') && url.pathname.endsWith('/status') && req.method === 'PATCH') {
      const id = decodeURIComponent(url.pathname.split('/')[3] || '');
      const body = await readJsonBody(req);
      const vehicle = await store.updateVehicleStatus(id, body.status);
      if (!vehicle) {
        sendJson(res, 404, { error: 'Vehicle not found' });
        return;
      }
      sendJson(res, 200, { vehicle });
      return;
    }

    if (url.pathname === '/api/statuses' && req.method === 'GET') {
      sendJson(res, 200, { statuses: VALID_STATUSES });
      return;
    }

    await serveStatic(req, res, url.pathname);
  } catch (error) {
    sendJson(res, 500, { error: error.message || 'Unexpected server error' });
  }
});

server.listen(PORT, () => {
  console.log(`Vehicle catalog server running on http://localhost:${PORT}`);
});
