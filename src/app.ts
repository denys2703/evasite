import express from 'express';
import routes from './routes';
import { errorHandler, notFoundHandler } from './middlewares/error-handler';

export const app = express();

app.use(express.json());
app.use('/api', routes);

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

app.use(notFoundHandler);
app.use(errorHandler);
