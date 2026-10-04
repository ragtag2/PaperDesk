import { model, Schema, Types } from 'mongoose'

export interface TeamRecord {
  _id: Types.ObjectId
  name: string
  responsibilities: string
  createdAt: Date
  updatedAt: Date
}

const schema = new Schema<TeamRecord>({
  name: { type: String, required: true },
  responsibilities: { type: String, required: true },
}, { collection: 'teams', timestamps: true })

export const TeamModel = model<TeamRecord>('Team', schema)
