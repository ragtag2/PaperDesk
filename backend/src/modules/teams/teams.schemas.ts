import { z } from 'zod'

export const createTeamSchema = z.strictObject({
  name: z.string().trim().min(1).max(120),
  responsibilities: z.string().trim().min(1).max(5000),
})
export const updateTeamSchema = createTeamSchema.partial().refine(
  (value) => Object.keys(value).length > 0, 'Provide at least one field.',
)
export const teamsQuerySchema = z.strictObject({})

export type CreateTeamInput = z.infer<typeof createTeamSchema>
export type UpdateTeamInput = z.infer<typeof updateTeamSchema>
