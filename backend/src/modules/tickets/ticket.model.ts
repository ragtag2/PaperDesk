import { model, Schema, Types } from 'mongoose'

export const categories = ['hardware', 'software', 'network', 'other'] as const
export const priorities = ['low', 'medium', 'high'] as const
export const statuses = ['open', 'in_progress', 'resolved'] as const

export type Category = typeof categories[number]
export type Priority = typeof priorities[number]
export type Status = typeof statuses[number]

export interface CoordinationRecord {
  summary: string
  relevantTeams: { teamId: Types.ObjectId; reason: string }[]
  stakeholderUserIds: Types.ObjectId[]
  analyzedAt: Date
}

export interface TicketRecord {
  _id: Types.ObjectId
  title: string
  description: string
  category: Category
  priority: Priority
  status: Status
  creatorId: Types.ObjectId
  assigneeId: Types.ObjectId | null
  coordination: CoordinationRecord | null
  createdAt: Date
  updatedAt: Date
}

const relevantTeamSchema = new Schema({
  teamId: { type: Schema.Types.ObjectId, ref: 'Team', required: true },
  reason: { type: String, required: true },
}, { _id: false })

const coordinationSchema = new Schema<CoordinationRecord>({
  summary: { type: String, required: true },
  relevantTeams: { type: [relevantTeamSchema], required: true },
  stakeholderUserIds: [{ type: Schema.Types.ObjectId, ref: 'User' }],
  analyzedAt: { type: Date, required: true },
}, { _id: false })

const schema = new Schema<TicketRecord>({
  title: { type: String, required: true },
  description: { type: String, required: true },
  category: { type: String, enum: categories, required: true },
  priority: { type: String, enum: priorities, required: true, default: 'medium' },
  status: { type: String, enum: statuses, required: true, default: 'open' },
  creatorId: { type: Schema.Types.ObjectId, ref: 'User', required: true },
  assigneeId: { type: Schema.Types.ObjectId, ref: 'User', default: null },
  coordination: { type: coordinationSchema, default: null },
}, { collection: 'tickets', timestamps: true })

schema.index({ creatorId: 1, createdAt: -1, _id: -1 })
schema.index({ assigneeId: 1, createdAt: -1, _id: -1 })
schema.index({ status: 1, createdAt: -1, _id: -1 })
schema.index({ 'coordination.stakeholderUserIds': 1, createdAt: -1, _id: -1 })

export const TicketModel = model<TicketRecord>('Ticket', schema)
