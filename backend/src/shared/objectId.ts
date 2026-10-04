import { Types } from 'mongoose'
import { z } from 'zod'
import { HttpError } from './httpError.js'

export const objectIdSchema = z.string().regex(/^[a-f\d]{24}$/i, 'Invalid ID.')

export function objectId(value: string): Types.ObjectId {
  if (!objectIdSchema.safeParse(value).success) throw new HttpError(400, 'Invalid ID.')
  return new Types.ObjectId(value)
}
