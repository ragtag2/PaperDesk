import { z } from 'zod'
import { roles } from './user.model.js'
import { paginationSchema } from '../../shared/pagination.js'
import { objectIdSchema } from '../../shared/objectId.js'

const name = z.string().trim().min(1)
const email = z.string().trim().toLowerCase().pipe(z.email())
const password = z.string().min(8)

export const signupSchema = z.strictObject({ name, email, password })
export const loginSchema = z.strictObject({ email, password: z.string() })
export const createUserSchema = z.strictObject({ name, email, password, role: z.enum(roles), teamId: objectIdSchema.nullable().optional() })
export const updateMeSchema = z.strictObject({ name, email }).partial().refine(
  (value) => Object.keys(value).length > 0, 'Provide at least one field.',
)
export const changePasswordSchema = z.strictObject({ currentPassword: z.string(), newPassword: password })
export const updateUserSchema = z.strictObject({ name, email, role: z.enum(roles), isActive: z.boolean(), teamId: objectIdSchema.nullable() }).partial().refine(
  (value) => Object.keys(value).length > 0, 'Provide at least one field.',
)
export const usersQuerySchema = z.strictObject({
  ...paginationSchema,
  role: z.enum(roles).optional(),
  isActive: z.enum(['true', 'false']).transform((value) => value === 'true').optional(),
  teamId: z.union([objectIdSchema, z.literal('none')]).optional(),
})

export type SignupInput = z.infer<typeof signupSchema>
export type LoginInput = z.infer<typeof loginSchema>
export type CreateUserInput = z.infer<typeof createUserSchema>
export type UpdateMeInput = z.infer<typeof updateMeSchema>
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>
export type UpdateUserInput = z.infer<typeof updateUserSchema>
export type UsersQuery = z.infer<typeof usersQuerySchema>
