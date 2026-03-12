import { AppError } from '../middlewares/error-handler';
import { CarRepository } from '../repositories/car.repository';
import { LogRepository } from '../repositories/log.repository';

export class LogService {
  constructor(
    private readonly logRepo = new LogRepository(),
    private readonly carRepo = new CarRepository(),
  ) {}

  async createLog(input: { car_id?: number | null; event_type: string; description: string }) {
    if (input.car_id) {
      const carExists = await this.carRepo.findById(input.car_id);
      if (!carExists) {
        throw new AppError(`Car with id ${input.car_id} does not exist`, 400);
      }
    }

    return this.logRepo.create(input);
  }
}
