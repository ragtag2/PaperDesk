import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowLeft, ArrowRight, Ticket } from 'lucide-react'
import { api } from '../api/client'
import { Alert, Button, Field } from '../components/Ui'

export function SignUpPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('')
    if (password.length < 8) { setError('Use at least 8 characters for your password.'); return }
    if (password !== confirm) { setError('The passwords do not match.'); return }
    setBusy(true)
    try { await api.auth.signup(name, email, password); navigate('/login', { replace: true, state: { notice: 'Your account is ready. Sign in to get started.' } }) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to create your account.') }
    finally { setBusy(false) }
  }

  return <div className="auth-page signup-page"><div className="auth-story"><div className="auth-story-inner"><Link className="brand auth-brand" to="/login"><span className="brand-mark"><Ticket size={23} /></span>paperdesk<span className="brand-dot">.</span></Link><div className="story-body"><div className="story-eyebrow">✳ YOUR WORKSPACE AWAITS</div><h1>Good work<br /><span>starts here.</span></h1><p>Tell us who you are, then bring your questions, requests, and ideas to the right people.</p><div className="signup-note"><span className="note-pin" />“Finally, a support queue that feels human.”<small>— the Paperdesk team</small></div></div><div className="story-footer">A small space for big progress. <span>↗</span></div></div></div><main className="auth-form-side"><div className="auth-form-wrap"><Link to="/login" className="back-link"><ArrowLeft size={17} /> Back to sign in</Link><div className="auth-mobile-brand brand"><span className="brand-mark"><Ticket size={21} /></span>paperdesk<span className="brand-dot">.</span></div><span className="auth-kicker">JOIN THE TEAM <span aria-hidden="true">✷</span></span><h2>Make yourself<br />at home<span className="heading-period">.</span></h2><p className="auth-subtitle">Create an employee account in just a moment.</p>{error && <Alert>{error}</Alert>}<form className="auth-form" onSubmit={submit}><Field id="name" label="Your name" autoComplete="name" placeholder="Alex Morgan" value={name} onChange={(event) => setName(event.target.value)} required /><Field id="email" label="Work email" type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(event) => setEmail(event.target.value)} required /><Field id="password" label="Password" type="password" autoComplete="new-password" minLength={8} placeholder="At least 8 characters" value={password} onChange={(event) => setPassword(event.target.value)} required /><Field id="confirm" label="Confirm password" type="password" autoComplete="new-password" placeholder="Repeat your password" value={confirm} onChange={(event) => setConfirm(event.target.value)} required /><Button type="submit" busy={busy} className="auth-submit">Create account <ArrowRight size={20} /></Button></form><p className="auth-switch">Already have an account? <Link to="/login">Sign in <ArrowRight size={15} /></Link></p></div></main></div>
}
