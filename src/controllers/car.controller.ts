import { Request, Response, NextFunction } from 'express';
import { CarService } from '../services/car.service';
import { ModificationService } from '../services/modification.service';
import { evaParamSchema, paginationQuerySchema, updateCarStatusSchema } from '../utils/validators';

export class CarController {
  constructor(
    private readonly carService = new CarService(),
    private readonly modificationService = new ModificationService(),
  ) {}

  listCars = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const query = paginationQuerySchema.parse(req.query);
      const result = await this.carService.listCars(query.page, query.limit, {
        search: query.search,
        brand: query.brand,
        template_type: query.template_type,
        status: query.status,
      });

      return res.json({
        page: query.page,
        limit: query.limit,
        total: result.total,
        data: result.data,
      });
    } catch (error) {
      return next(error);
    }
  };

  getCar = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { eva } = evaParamSchema.parse(req.params);
      const car = await this.carService.getCarByEva(eva);
      return res.json(car);
    } catch (error) {
      return next(error);
    }
  };

  listModifications = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { eva } = evaParamSchema.parse(req.params);
      await this.carService.getCarByEva(eva);
      const data = await this.modificationService.listByEva(eva);
      return res.json(data);
    } catch (error) {
      return next(error);
    }
  };

  updateStatus = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { eva } = evaParamSchema.parse(req.params);
      const body = updateCarStatusSchema.parse(req.body);
      const updated = await this.carService.updateStatus(eva, body.status, body.description);
      return res.json(updated);
    } catch (error) {
      return next(error);
    }
  };
}
