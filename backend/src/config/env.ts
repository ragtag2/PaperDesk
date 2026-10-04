import 'dotenv/config'
import { z } from 'zod'

const schema = z.object({
  MONGODB_URI: z.string().startsWith('mongodb').min(1),
  MONGODB_DB_NAME: z.string().min(1).default('paperdesk'),
  MONGODB_DNS_SERVERS: z.string().optional(),
  AGENT_BASE_URL: z.preprocess((value) => value === '' ? undefined : value, z.url().optional()),
  SESSION_SECRET: z.string().min(32),
  FRONTEND_ORIGIN: z.url().default('http://localhost:5173'),
  PORT: z.coerce.number().int().positive().default(3000),
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  TRUST_PROXY: z.coerce.number().int().min(0).default(0),
})

export const env = schema.parse(process.env)
