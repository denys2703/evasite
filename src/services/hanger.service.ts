import { HangerRepository } from '../repositories/hanger.repository';

export class HangerService {
  constructor(private readonly hangerRepo = new HangerRepository()) {}

  listHangers() {
    return this.hangerRepo.list();
  }

  carsByHangerNumber(number: number) {
    return this.hangerRepo.carsByHangerNumber(number);
  }
}
