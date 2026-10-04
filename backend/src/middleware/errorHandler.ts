import type { ErrorRequestHandler, RequestHandler } from 'express'
import { HttpError } from '../shared/httpError.js'

export const notFound: RequestHandler = (_req, _res, next) => next(new HttpError(404, 'Not found.'))

export const errorHandler: ErrorRequestHandler = (error: unknown, _req, res, _next) => {
  if (error instanceof HttpError) {
    res.status(error.status).json({ message: error.message })
    return
  }
  if (typeof error === 'object' && error !== null && 'code' in error && error.code === 11000) {
    res.status(409).json({ message: 'An account with this email already exists.' })
    return
  }
  if (error instanceof SyntaxError && 'body' in error) {
    res.status(400).json({ message: 'Invalid JSON body.' })
    return
  }
  if (typeof error === 'object' && error !== null && 'type' in error && error.type === 'entity.too.large') {
    res.status(400).json({ message: 'Request body is too large.' })
    return
  }
  console.error(error)
  res.status(500).json({ message: 'Internal server error.' })
}
