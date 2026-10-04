import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { ArrowRight, KeyRound, LogOut, Mail, UserRound } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../app/AuthContext'
import { Alert, Button, Field, PageHeading } from '../components/Ui'

export function ProfilePage() {
  const { user, setUser, signOut } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState(user?.name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [profileBusy, setProfileBusy] = useState(false)
  const [passwordBusy, setPasswordBusy] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [profileNotice, setProfileNotice] = useState('')
  const [passwordNotice, setPasswordNotice] = useState('')

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setProfileError(''); setProfileNotice(''); setProfileBusy(true)
    try { const updated = await api.profile.update(name.trim(), email.trim()); setUser(updated); setProfileNotice('Your profile is up to date.') }
    catch (reason) { setProfileError(reason instanceof Error ? reason.message : 'Could not save your profile.') }
    finally { setProfileBusy(false) }
  }
  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPasswordError(''); setPasswordNotice('')
    if (newPassword.length < 8) { setPasswordError('Use at least 8 characters for your new password.'); return }
    if (newPassword !== confirmPassword) { setPasswordError('The new passwords do not match.'); return }
    setPasswordBusy(true)
    try { await api.profile.changePassword(currentPassword, newPassword); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); setPasswordNotice('Password changed successfully.') }
    catch (reason) { setPasswordError(reason instanceof Error ? reason.message : 'Could not change your password.') }
    finally { setPasswordBusy(false) }
  }
  async function logout() { try { await signOut() } finally { navigate('/login', { replace: true }) } }

  return <div className="profile-page"><PageHeading eyebrow="YOUR CORNER" title="My profile" description="Keep your details current and your account yours." /><div className="profile-banner"><div className="profile-avatar">{user?.name.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</div><div><span className="section-kicker">HELLO THERE</span><h2>{user?.name}</h2><p>{user?.email}</p></div><span className="profile-role">{user?.role}</span><span className="profile-banner-spark" aria-hidden="true">✳</span></div><div className="profile-grid"><section className="paper-panel profile-panel"><div className="profile-panel-header"><span className="profile-panel-icon"><UserRound size={22} /></span><div><h2>Personal details</h2><p>How your teammates know you.</p></div></div>{profileError && <Alert>{profileError}</Alert>}{profileNotice && <Alert kind="success">{profileNotice}</Alert>}<form onSubmit={saveProfile}><Field id="profile-name" label="Full name" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required /><Field id="profile-email" label="Email address" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><Button type="submit" busy={profileBusy}><Mail size={18} /> Save details</Button></form></section><section className="paper-panel profile-panel"><div className="profile-panel-header"><span className="profile-panel-icon icon-red"><KeyRound size={22} /></span><div><h2>Change password</h2><p>A little account housekeeping.</p></div></div>{passwordError && <Alert>{passwordError}</Alert>}{passwordNotice && <Alert kind="success">{passwordNotice}</Alert>}<form onSubmit={savePassword}><Field id="current-password" label="Current password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /><Field id="new-password" label="New password" type="password" autoComplete="new-password" minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /><Field id="confirm-password" label="Confirm new password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required /><Button type="submit" busy={passwordBusy}>Update password <ArrowRight size={18} /></Button></form></section></div><div className="logout-strip"><div><LogOut size={20} /><span>All done for now?</span></div><Button type="button" variant="quiet" onClick={logout}>Log out <ArrowRight size={17} /></Button></div></div>
}
