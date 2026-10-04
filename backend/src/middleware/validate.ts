import type { RequestHandler } from 'express'
import type { ZodType } from 'zod'
import { HttpError } from '../shared/httpError.js'

export function validate(schemas: { body?: ZodType; query?: ZodType }): RequestHandler {
  return (req, _res, next) => {
    for (const part of ['body', 'query'] as const) {
      const schema = schemas[part]
      if (!schema) continue
      const result = schema.safeParse(req[part])
      if (!result.success) return next(new HttpError(400, result.error.issues[0]?.message ?? 'Invalid input.'))
      if (part === 'body') req.body = result.data
      else req.validatedQuery = result.data
    }
    next()
  }
}
