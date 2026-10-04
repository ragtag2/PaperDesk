import { model, Schema, Types } from 'mongoose'

export const notificationTypes = ['ticket_involvement', 'ticket_resolved'] as const
export type NotificationType = typeof notificationTypes[number]

export interface NotificationRecord {
  _id: Types.ObjectId
  userId: Types.ObjectId
  ticketId: Types.ObjectId
  ticketTitle: string
  type: NotificationType
  eventKey: string
  createdAt: Date
  readAt: Date | null
}

const schema = new Schema<NotificationRecord>({
  userId: { type: Schema.Types.ObjectId, ref: 'User', required: true },
  ticketId: { type: Schema.Types.ObjectId, ref: 'Ticket', required: true },
  ticketTitle: { type: String, required: true },
  type: { type: String, enum: notificationTypes, required: true },
  eventKey: { type: String, required: true },
  createdAt: { type: Date, required: true, default: Date.now },
  readAt: { type: Date, default: null },
}, { collection: 'notifications' })

schema.index({ userId: 1, ticketId: 1, type: 1, eventKey: 1 }, { unique: true })
schema.index({ userId: 1, createdAt: -1, _id: -1 })
schema.index({ userId: 1, readAt: 1, createdAt: -1, _id: -1 })

export const NotificationModel = model<NotificationRecord>('Notification', schema)
