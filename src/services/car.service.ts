import { AppError } from '../middlewares/error-handler';
import { CarRepository } from '../repositories/car.repository';
import { LogRepository } from '../repositories/log.repository';

export class CarService {
  constructor(
    private readonly carRepo = new CarRepository(),
    private readonly logRepo = new LogRepository(),
  ) {}

  listCars(page: number, limit: number, filters: { search?: string; brand?: string; template_type?: '2D' | '5D'; status?: string }) {
    return this.carRepo.list(page, limit, filters);
  }

  async getCarByEva(eva: string) {
    const car = await this.carRepo.findByEvaCode(eva);
    if (!car) throw new AppError(`Car with EVA code ${eva} not found`, 404);
    return car;
  }

  async updateStatus(eva: string, status: string, description?: string) {
    const updated = await this.carRepo.updateStatusByEvaCode(eva, status);
    if (!updated) throw new AppError(`Car with EVA code ${eva} not found`, 404);

    await this.logRepo.create({
      car_id: updated.id,
      event_type: 'status_updated',
      description: description ?? `Status changed to ${status}`,
    });

    return updated;
  }
}
