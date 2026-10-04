import type { Role } from '../modules/users/user.model.js'

declare module 'express-session' {
  interface SessionData {
    userId?: string
    sessionVersion?: number
  }
}

declare global {
  namespace Express {
    interface Request {
      validatedQuery?: unknown
      auth?: { userId: string; role: Role }
    }
  }
}

export {}
