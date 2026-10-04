import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ArrowRight, Filter, Plus, Search, Ticket as TicketIcon } from 'lucide-react'
import { api } from '../api/client'
import type { Assignee, Page, Ticket, TicketCategory, TicketPriority, TicketStatus } from '../api/types'
import { useAuth } from '../app/AuthContext'
import { useNotifications } from '../app/NotificationsContext'
import { Alert, Badge, EmptyState, LoadingScreen, PageHeading, Pagination } from '../components/Ui'
import { categories, priorities, shortDate, statuses } from '../features/tickets'

const pageSize = 8

export function TicketsPage() {
  const { user } = useAuth()
  const { revision } = useNotifications()
  const [searchParams, setSearchParams] = useSearchParams()
  const [result, setResult] = useState<Page<Ticket> | null>(null)
  const [counts, setCounts] = useState({ all: 0, open: 0, in_progress: 0, resolved: 0 })
  const [assignees, setAssignees] = useState<Assignee[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const status = searchParams.get('status') ?? ''
  const priority = searchParams.get('priority') ?? ''
  const category = searchParams.get('category') ?? ''
  const assigneeId = searchParams.get('assigneeId') ?? ''
  const involvingMe = searchParams.get('involvingMe') === 'true'
  const canAssign = user?.role === 'support' || user?.role === 'admin'

  useEffect(() => {
    let active = true
    api.tickets.list({ page, limit: pageSize, status: status as TicketStatus | '', priority: priority as TicketPriority | '', category: category as TicketCategory | '', assigneeId: canAssign ? assigneeId : '', involvingMe: involvingMe ? 'true' : undefined })
      .then((data) => { if (active) { setResult(data); setError('') } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Could not load tickets.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, status, priority, category, assigneeId, involvingMe, canAssign, revision])

  useEffect(() => {
    let active = true
    Promise.all([
      api.tickets.list({ page: 1, limit: 1, involvingMe: involvingMe ? 'true' : undefined }),
      api.tickets.list({ page: 1, limit: 1, status: 'open', involvingMe: involvingMe ? 'true' : undefined }),
      api.tickets.list({ page: 1, limit: 1, status: 'in_progress', involvingMe: involvingMe ? 'true' : undefined }),
      api.tickets.list({ page: 1, limit: 1, status: 'resolved', involvingMe: involvingMe ? 'true' : undefined }),
    ]).then(([all, open, progress, resolved]) => {
      if (active) setCounts({ all: all.total, open: open.total, in_progress: progress.total, resolved: resolved.total })
    }).catch(() => {})
    if (canAssign) api.tickets.assignees().then((items) => { if (active) setAssignees(items) }).catch(() => {})
    return () => { active = false }
  }, [canAssign, involvingMe, revision])

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value); else next.delete(key)
    next.delete('page')
    setSearchParams(next)
    setLoading(true)
  }
  function setPage(nextPage: number) {
    const next = new URLSearchParams(searchParams)
    next.set('page', String(nextPage)); setSearchParams(next); setLoading(true)
  }
  function reset() { setSearchParams({}); setLoading(true) }

  return <>
    <PageHeading eyebrow="YOUR WORKSPACE" title="Ticket board" description="Every little request has a place to land." action={<Link className="button button-primary" to="/tickets/new"><Plus size={19} strokeWidth={2.7} /> New ticket</Link>} />
    <section className="overview-grid" aria-label="Ticket overview">
      <div className="overview-card overview-all"><span className="overview-label">{involvingMe ? 'Involving me' : 'All tickets'}</span><strong>{counts.all}</strong><span className="overview-mark" aria-hidden="true"><TicketIcon size={30} /></span><span className="overview-foot">{involvingMe ? 'Tickets affecting you' : 'Everything in view'}</span></div>
      <div className="overview-card overview-open"><span className="overview-label">Open</span><strong>{counts.open}</strong><span className="overview-mark" aria-hidden="true">✳</span><span className="overview-foot">Ready for action</span></div>
      <div className="overview-card overview-progress"><span className="overview-label">In progress</span><strong>{counts.in_progress}</strong><span className="overview-mark" aria-hidden="true">↗</span><span className="overview-foot">Making headway</span></div>
      <div className="overview-card overview-resolved"><span className="overview-label">Resolved</span><strong>{counts.resolved}</strong><span className="overview-mark" aria-hidden="true">✓</span><span className="overview-foot">All wrapped up</span></div>
    </section>
    <section className="ticket-section" aria-labelledby="ticket-list-heading"><div className="section-top"><div><div className="section-kicker">THE RUNNING LIST</div><h2 id="ticket-list-heading">Tickets <span className="section-count">{result?.total ?? 0}</span></h2></div><p>A clear view of what needs doing.</p></div>
      <div className="filter-bar"><div className="filter-title"><Filter size={19} /><span>Filter by</span></div><label className="sr-only" htmlFor="filter-involvement">Ticket involvement</label><select id="filter-involvement" value={involvingMe ? 'true' : ''} onChange={(event) => setFilter('involvingMe', event.target.value)}><option value="">All visible tickets</option><option value="true">Involving me</option></select><label className="sr-only" htmlFor="filter-status">Status</label><select id="filter-status" value={status} onChange={(event) => setFilter('status', event.target.value)}><option value="">All statuses</option>{statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><label className="sr-only" htmlFor="filter-priority">Priority</label><select id="filter-priority" value={priority} onChange={(event) => setFilter('priority', event.target.value)}><option value="">All priorities</option>{priorities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><label className="sr-only" htmlFor="filter-category">Category</label><select id="filter-category" value={category} onChange={(event) => setFilter('category', event.target.value)}><option value="">All categories</option>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>{canAssign && <><label className="sr-only" htmlFor="filter-assignee">Assignee</label><select id="filter-assignee" value={assigneeId} onChange={(event) => setFilter('assigneeId', event.target.value)}><option value="">Any assignee</option>{assignees.map((item) => <option key={item._id} value={item._id}>{item.name}</option>)}</select></>}{(status || priority || category || assigneeId || involvingMe) && <button className="clear-filters" type="button" onClick={reset}>Clear filters</button>}</div>
      {error && <Alert>{error}</Alert>}
      {loading ? <LoadingScreen label="Finding your tickets…" /> : result?.items.length ? <><div className="ticket-table-wrap"><table className="ticket-table"><thead><tr><th>Ticket</th><th>Status</th><th>Priority</th><th>Category</th><th>Updated</th><th><span className="sr-only">View</span></th></tr></thead><tbody>{result.items.map((ticket) => <tr key={ticket._id}><td><Link className="ticket-title" to={`/tickets/${ticket._id}`}>{ticket.title}</Link><div className="ticket-meta">#{ticket._id.replace(/^t-/, '')} <span>·</span> {ticket.creator?.name ?? (ticket.creatorId === user?._id ? 'You' : 'Team member')}</div></td><td><Badge value={ticket.status} /></td><td><Badge value={ticket.priority} kind="priority" /></td><td><span className="category-cell">{categories.find((item) => item.value === ticket.category)?.label}</span></td><td className="date-cell">{shortDate(ticket.updatedAt)}</td><td><Link className="row-arrow" to={`/tickets/${ticket._id}`} aria-label={`View ${ticket.title}`}><ArrowRight size={19} /></Link></td></tr>)}</tbody></table></div><div className="ticket-cards">{result.items.map((ticket) => <Link className="ticket-mobile-card" to={`/tickets/${ticket._id}`} key={ticket._id}><div className="ticket-mobile-top"><span>#{ticket._id.replace(/^t-/, '')}</span><Badge value={ticket.status} /></div><h3>{ticket.title}</h3><div className="ticket-mobile-bottom"><Badge value={ticket.priority} kind="priority" /><span>{shortDate(ticket.updatedAt)}</span><ArrowRight size={19} /></div></Link>)}</div><Pagination page={result.page} limit={result.limit} total={result.total} onPage={setPage} /></> : !error && <EmptyState title={involvingMe ? 'No tickets involving you' : 'No tickets on this page'} description={status || priority || category || assigneeId || involvingMe ? 'Try changing a filter to see more requests.' : 'When a request comes in, it will appear here.'} action={status || priority || category || assigneeId || involvingMe ? <button type="button" className="button button-secondary" onClick={reset}><Search size={18} /> Clear filters</button> : <Link className="button button-primary" to="/tickets/new"><Plus size={18} /> Create a ticket</Link>} />}
    </section>
  </>
}
