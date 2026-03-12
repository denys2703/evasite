import { Request, Response, NextFunction } from 'express';
import { HangerService } from '../services/hanger.service';
import { hangerNumberParamSchema } from '../utils/validators';

export class HangerController {
  constructor(private readonly hangerService = new HangerService()) {}

  list = async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const data = await this.hangerService.listHangers();
      return res.json(data);
    } catch (error) {
      return next(error);
    }
  };

  carsByHanger = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { number } = hangerNumberParamSchema.parse(req.params);
      const data = await this.hangerService.carsByHangerNumber(number);
      return res.json(data);
    } catch (error) {
      return next(error);
    }
  };
}
