import { google } from 'googleapis';
import { env } from '../config/env';
import { HangerRepository } from '../repositories/hanger.repository';
import { CarRepository } from '../repositories/car.repository';
import { ModificationRepository } from '../repositories/modification.repository';
import { LogRepository } from '../repositories/log.repository';
import { importSheetRowSchema } from '../utils/validators';

interface ImportSummary {
  processed: number;
  cars_upserted: number;
  modifications_upserted: number;
  errors: Array<{ row: number; message: string }>;
}

export class GoogleSheetsImportService {
  constructor(
    private readonly hangerRepo = new HangerRepository(),
    private readonly carRepo = new CarRepository(),
    private readonly modificationRepo = new ModificationRepository(),
    private readonly logRepo = new LogRepository(),
  ) {}

  private parseCarDescription(description: string): { model: string; generation: string | null; production_years: string | null } {
    const yearsMatch = description.match(/(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}/);
    const production_years = yearsMatch ? yearsMatch[0].replace(/\s+/g, '') : null;

    const clean = description.replace(yearsMatch?.[0] ?? '', '').trim();
    const tokens = clean.split(/\s+/);

    if (tokens.length <= 1) {
      return { model: clean, generation: null, production_years };
    }

    const generationToken = tokens[tokens.length - 1];
    const generation = /^(B\d+|MK\d+|GEN\d+|\d+gen)$/i.test(generationToken) ? generationToken : null;
    const model = generation ? tokens.slice(0, -1).join(' ') : clean;

    return { model, generation, production_years };
  }

  private parseDriveGearbox(value: string): { drive_type: string | null; gearbox: string | null } {
    const normalized = value.toUpperCase();
    const drive_type = ['FWD', 'RWD', 'AWD'].find((x) => normalized.includes(x)) ?? null;
    const gearbox = normalized.includes('MANUAL') ? 'Manual' : normalized.includes('AUTO') ? 'Automatic' : null;
    return { drive_type, gearbox };
  }

  async importFromRows(rawRows: unknown[][]): Promise<ImportSummary> {
    const summary: ImportSummary = {
      processed: 0,
      cars_upserted: 0,
      modifications_upserted: 0,
      errors: [],
    };

    for (let i = 0; i < rawRows.length; i += 1) {
      const rowNumber = i + 1;
      const row = rawRows[i];
      const mapped = {
        template_type: row[0],
        hanger_number: row[1],
        brand: row[2],
        car_description: row[3],
        eva_code: row[4],
        article_code: row[5],
        body_type: row[6],
        drive_gearbox: row[7],
        class: row[8],
      };

      const parsed = importSheetRowSchema.safeParse(mapped);
      if (!parsed.success) {
        summary.errors.push({ row: rowNumber, message: parsed.error.issues.map((x) => x.message).join('; ') });
        continue;
      }

      try {
        const item = parsed.data;
        const { model, generation, production_years } = this.parseCarDescription(item.car_description);
        const { drive_type, gearbox } = this.parseDriveGearbox(item.drive_gearbox);

        await this.hangerRepo.upsertHanger({
          hanger_number: item.hanger_number,
          brand: item.brand,
          warehouse_section: item.class ?? 'default',
        });

        const car = await this.carRepo.upsertCar({
          eva_code: item.eva_code,
          brand: item.brand,
          model,
          generation,
          body_type: item.body_type,
          production_years,
          hanger_number: item.hanger_number,
          template_type: item.template_type,
          status: 'active',
        });

        await this.modificationRepo.upsertModification({
          car_id: car.id,
          article_code: item.article_code,
          drive_type,
          gearbox,
          fuel_type: null,
          facelift_version: null,
        });

        await this.logRepo.create({
          car_id: car.id,
          event_type: 'imported_from_google_sheets',
          description: `Imported article ${item.article_code} for ${item.eva_code}`,
        });

        summary.processed += 1;
        summary.cars_upserted += 1;
        summary.modifications_upserted += 1;
      } catch (error) {
        summary.errors.push({ row: rowNumber, message: error instanceof Error ? error.message : 'Unknown error' });
      }
    }

    return summary;
  }

  async importFromGoogleSheets(): Promise<ImportSummary> {
    if (!env.GOOGLE_SHEETS_ID || !env.GOOGLE_SERVICE_ACCOUNT_EMAIL || !env.GOOGLE_PRIVATE_KEY) {
      throw new Error('Google Sheets credentials are not configured');
    }

    const auth = new google.auth.JWT({
      email: env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      key: env.GOOGLE_PRIVATE_KEY.replace(/\\n/g, '\n'),
      scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
    });

    const sheets = google.sheets({ version: 'v4', auth });
    const result = await sheets.spreadsheets.values.get({
      spreadsheetId: env.GOOGLE_SHEETS_ID,
      range: env.GOOGLE_SHEETS_RANGE,
    });

    const rows = result.data.values ?? [];
    if (rows.length <= 1) {
      return { processed: 0, cars_upserted: 0, modifications_upserted: 0, errors: [] };
    }

    return this.importFromRows(rows.slice(1));
  }
}
