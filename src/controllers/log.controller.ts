import { Request, Response, NextFunction } from 'express';
import { LogService } from '../services/log.service';
import { createLogSchema } from '../utils/validators';

export class LogController {
  constructor(private readonly logService = new LogService()) {}

  create = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const payload = createLogSchema.parse(req.body);
      const log = await this.logService.createLog(payload);
      return res.status(201).json(log);
    } catch (error) {
      return next(error);
    }
  };
}
