import { z } from 'zod'

const positiveInteger = z.string().regex(/^[1-9]\d*$/).transform(Number).pipe(z.number().int().positive())

export const paginationSchema = {
  page: positiveInteger.default(1),
  limit: positiveInteger.pipe(z.number().max(100)).default(10),
}

export function pageResult<T>(items: T[], page: number, limit: number, total: number) {
  return { items, page, limit, total }
}
