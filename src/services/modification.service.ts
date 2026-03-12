import { ModificationRepository } from '../repositories/modification.repository';

export class ModificationService {
  constructor(private readonly modificationRepo = new ModificationRepository()) {}

  listByEva(eva: string) {
    return this.modificationRepo.findByEvaCode(eva);
  }
}
