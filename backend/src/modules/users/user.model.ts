import { model, Schema, Types } from 'mongoose'

export const roles = ['employee', 'support', 'admin'] as const
export type Role = typeof roles[number]

export interface UserRecord {
  _id: Types.ObjectId
  name: string
  email: string
  passwordHash: string
  role: Role
  isActive: boolean
  sessionVersion: number
  teamId: Types.ObjectId | null
  createdAt: Date
  updatedAt: Date
}

const schema = new Schema<UserRecord>({
  name: { type: String, required: true },
  email: { type: String, required: true },
  passwordHash: { type: String, required: true, select: false },
  role: { type: String, enum: roles, required: true, default: 'employee' },
  isActive: { type: Boolean, required: true, default: true },
  sessionVersion: { type: Number, required: true, default: 0 },
  teamId: { type: Schema.Types.ObjectId, ref: 'Team', default: null },
}, { collection: 'users', timestamps: true })

schema.index({ email: 1 }, { unique: true })
schema.index({ teamId: 1 })

export const UserModel = model<UserRecord>('User', schema)
