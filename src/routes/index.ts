import { Router } from 'express';
import { CarController } from '../controllers/car.controller';
import { HangerController } from '../controllers/hanger.controller';
import { LogController } from '../controllers/log.controller';
import { ImportController } from '../controllers/import.controller';

const router = Router();

const carController = new CarController();
const hangerController = new HangerController();
const logController = new LogController();
const importController = new ImportController();

router.get('/cars', carController.listCars);
router.get('/cars/:eva', carController.getCar);
router.get('/cars/:eva/modifications', carController.listModifications);
router.post('/cars/:eva/status', carController.updateStatus);

router.get('/hangers', hangerController.list);
router.get('/hangers/:number', hangerController.carsByHanger);

router.post('/logs', logController.create);
router.post('/imports/google-sheets', importController.runGoogleSheetsImport);

export default router;
