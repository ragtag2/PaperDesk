import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { ArrowRight, Check, HardDrive, Lightbulb, Monitor, Wifi } from 'lucide-react'
import { api } from '../api/client'
import type { TicketCategory } from '../api/types'
import { Alert, BackLink, Button, Field, PageHeading, TextAreaField } from '../components/Ui'

const choices = [
  { value: 'hardware' as TicketCategory, label: 'Hardware', icon: HardDrive, help: 'Devices & equipment' },
  { value: 'software' as TicketCategory, label: 'Software', icon: Monitor, help: 'Apps & accounts' },
  { value: 'network' as TicketCategory, label: 'Network', icon: Wifi, help: 'Wi-Fi & connections' },
  { value: 'other' as TicketCategory, label: 'Other', icon: Lightbulb, help: 'Everything else' },
]

export function CreateTicketPage() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<TicketCategory>('software')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      const ticket = await api.tickets.create({ title: title.trim(), description: description.trim(), category })
      navigate(`/tickets/${ticket._id}`, { state: { notice: 'Ticket created. We’re on it!' } })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not create your ticket.') }
    finally { setBusy(false) }
  }

  return <div className="narrow-page"><BackLink to="/tickets">Back to tickets</BackLink><PageHeading eyebrow="LET'S SORT IT OUT" title="New ticket" description="Tell us what happened. We'll take it from there." /><div className="form-layout"><form className="paper-panel ticket-form" onSubmit={submit}><div className="form-section-heading"><span className="step-circle">1</span><div><h2>What do you need help with?</h2><p>A few details help the right person pick this up.</p></div></div>{error && <Alert>{error}</Alert>}<Field id="ticket-title" label="Give it a short title" placeholder="e.g. Laptop won't connect to Wi-Fi" maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} required /><TextAreaField id="ticket-description" label="Tell us a little more" hint="What happened? When did it start? Anything you've already tried?" placeholder="The more detail you can share, the faster we can help…" rows={7} maxLength={5000} value={description} onChange={(event) => setDescription(event.target.value)} required /><fieldset className="category-fieldset"><legend>Which area does this fit?</legend><div className="category-choices">{choices.map(({ value, label, icon: Icon, help }) => <label className={`category-choice ${category === value ? 'selected' : ''}`} key={value}><input type="radio" name="category" value={value} checked={category === value} onChange={() => setCategory(value)} /><span className="category-choice-icon"><Icon size={22} strokeWidth={2.4} /></span><span><strong>{label}</strong><small>{help}</small></span>{category === value && <Check size={18} className="category-check" />}</label>)}</div></fieldset><div className="form-actions"><Button type="submit" busy={busy}>Send ticket <ArrowRight size={19} /></Button></div></form><aside className="form-aside"><span className="aside-spark" aria-hidden="true">✳</span><h3>Good to know</h3><p>Your ticket starts as <strong>Open</strong> with a <strong>Medium</strong> priority. The support team can update these as they work on it.</p><div className="aside-doodle" aria-hidden="true">↝</div></aside></div></div>
}
