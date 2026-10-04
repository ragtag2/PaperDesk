import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { ArrowRight, CircleCheck, MoveUpRight, Sparkles, Ticket } from 'lucide-react'
import { demoAccounts } from '../api/demo'
import { isDemoMode } from '../api/client'
import { useAuth } from '../app/AuthContext'
import { Alert, Button, Field } from '../components/Ui'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/tickets'
  const notice = (location.state as { notice?: string } | null)?.notice

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true)
    try { await signIn(email, password); navigate(from, { replace: true }) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to sign in.') }
    finally { setBusy(false) }
  }

  return <div className="auth-page">
    <div className="auth-story">
      <div className="auth-story-inner">
        <Link className="brand auth-brand" to="/login"><span className="brand-mark"><Ticket size={23} strokeWidth={2.5} /></span>paperdesk<span className="brand-dot">.</span></Link>
        <div className="story-body"><div className="story-eyebrow"><Sparkles size={18} /> A calmer way to get help</div><h1>A little less<br /><span>ticket chaos.</span></h1><p>All your requests, updates, and small victories in one friendly place.</p><div className="sketch-card" aria-hidden="true"><div className="sketch-tape" /><div className="sketch-card-top"><span className="sketch-circle"><CircleCheck size={29} /></span><span className="sketch-lines"><i /><i /></span><MoveUpRight size={22} /></div><div className="sketch-divider" /><div className="sketch-card-bottom"><span className="sketch-pill" /><span className="sketch-avatars"><i>A</i><i>M</i><i>S</i></span></div></div><span className="story-arrow" aria-hidden="true">↗</span></div>
        <div className="story-footer">Made for the people who keep things moving. <span>✳</span></div>
      </div>
    </div>
    <main className="auth-form-side"><div className="auth-form-wrap"><div className="auth-mobile-brand brand"><span className="brand-mark"><Ticket size={21} /></span>paperdesk<span className="brand-dot">.</span></div><span className="auth-kicker">WELCOME BACK <span aria-hidden="true">✷</span></span><h2>Pick up where<br />you left off<span className="heading-period">.</span></h2><p className="auth-subtitle">Sign in to see what needs your attention.</p>{notice && <Alert kind="success">{notice}</Alert>}{error && <Alert>{error}</Alert>}<form onSubmit={submit} className="auth-form"><Field id="email" label="Email address" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} required /><Field id="password" label="Password" type="password" autoComplete="current-password" placeholder="Your password" value={password} onChange={(event) => setPassword(event.target.value)} required /><Button type="submit" busy={busy} className="auth-submit">Sign in <ArrowRight size={20} /></Button></form><p className="auth-switch">New to Paperdesk? <Link to="/signup">Create an account <ArrowRight size={15} /></Link></p>{isDemoMode && <div className="demo-login"><div className="demo-login-title"><span>✳</span> TRY THE SAMPLE WORKSPACE</div><p>Choose a role to explore. Password: <code>password123</code></p><div className="demo-account-list">{demoAccounts.map((account) => <button type="button" key={account.role} onClick={() => { setEmail(account.email); setPassword('password123'); setError('') }}><strong>{account.name}</strong><span>{account.role}</span><ArrowRight size={16} /></button>)}</div></div>}</div></main>
  </div>
}
