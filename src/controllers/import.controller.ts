import { Request, Response, NextFunction } from 'express';
import { GoogleSheetsImportService } from '../services/google-sheets-import.service';

export class ImportController {
  constructor(private readonly importService = new GoogleSheetsImportService()) {}

  runGoogleSheetsImport = async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const result = await this.importService.importFromGoogleSheets();
      return res.json(result);
    } catch (error) {
      return next(error);
    }
  };
}
