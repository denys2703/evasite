import { z } from 'zod';

export const paginationQuerySchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().positive().max(100).default(20),
  search: z.string().optional(),
  brand: z.string().optional(),
  template_type: z.enum(['2D', '5D']).optional(),
  status: z.string().optional(),
});

export const evaParamSchema = z.object({
  eva: z.string().min(1),
});

export const hangerNumberParamSchema = z.object({
  number: z.coerce.number().int().positive(),
});

export const updateCarStatusSchema = z.object({
  status: z.enum(['active', 'draft', 'archived']),
  description: z.string().optional(),
});

export const createLogSchema = z.object({
  car_id: z.number().int().positive().nullable().optional(),
  event_type: z.string().min(1).max(60),
  description: z.string().min(1),
});

export const importSheetRowSchema = z.object({
  template_type: z.enum(['2D', '5D']),
  hanger_number: z.coerce.number().int().positive(),
  brand: z.string().min(1),
  car_description: z.string().min(1),
  eva_code: z.string().min(1),
  article_code: z.string().min(1),
  body_type: z.string().min(1),
  drive_gearbox: z.string().min(1),
  class: z.string().optional(),
});
