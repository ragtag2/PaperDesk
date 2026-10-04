import { RefreshCw } from 'lucide-react'
import type { TicketCoordination } from '../api/types'
import { Alert, Button } from './Ui'

export function CoordinationPanel({ coordination, updatedAt, refreshing, error, onRefresh }: {
  coordination: TicketCoordination | null
  updatedAt: string
  refreshing: boolean
  error: string
  onRefresh: () => void
}) {
  const stale = coordination && Date.parse(coordination.analyzedAt) < Date.parse(updatedAt)
  return <section className="paper-panel coordination-panel" aria-labelledby="coordination-heading">
    <div className="detail-section-top">
      <div><span className="section-kicker">INCIDENT COORDINATION</span><h2 id="coordination-heading">Who's involved?</h2></div>
      <Button type="button" variant="quiet" busy={refreshing} onClick={onRefresh} aria-label="Refresh coordination"><RefreshCw size={17} aria-hidden="true" /> Refresh</Button>
    </div>
    {error && <Alert>{error}</Alert>}
    {coordination ? <>
      <p className="coordination-summary">{coordination.summary}</p>
      {stale && <p className="field-hint">This ticket has changed since the last analysis. Refresh to check for a newer result.</p>}
      <h3>Relevant teams</h3>
      {coordination.relevantTeams.length ? <ul className="coordination-teams">{coordination.relevantTeams.map((team) => <li key={team.teamId}><strong>{team.name ?? 'Team unavailable'}</strong></li>)}</ul> : <p>No relevant teams identified.</p>}
      <h3>Stakeholders</h3>
      <p className="field-hint">People to keep informed as this incident evolves.</p>
      {coordination.stakeholders.length ? <ul className="stakeholder-list">{coordination.stakeholders.map((person) => <li key={person._id}>{person.name}</li>)}</ul> : <p>No stakeholders identified.</p>}
      <p className="coordination-date">Last analyzed <time dateTime={coordination.analyzedAt}>{new Date(coordination.analyzedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></p>
    </> : <div className="coordination-empty"><p>No analysis available yet.</p><span>Relevant teams and people will appear here when an analysis is available.</span></div>}
  </section>
}
