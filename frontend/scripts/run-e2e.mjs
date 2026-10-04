import { spawn } from 'node:child_process'
import { createServer } from 'vite'

process.env.VITE_DEMO_MODE = 'true'
const server = await createServer({ server: { host: '127.0.0.1', port: 5173, strictPort: true } })
await server.listen()

const result = await new Promise((resolve) => {
  const test = spawn(process.execPath, ['node_modules/@playwright/test/cli.js', 'test', ...process.argv.slice(2)], { stdio: 'inherit', env: process.env })
  test.on('close', (code) => resolve(code ?? 1))
  test.on('error', () => resolve(1))
})

await server.close()
process.exitCode = result
