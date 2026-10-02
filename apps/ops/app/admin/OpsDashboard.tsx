'use client';

/**
 * Operator ops dashboard (Phase 36): every number, live.
 *
 * A client component polling the same-origin /admin/numbers proxy on a
 * selectable interval. Dataviz posture (house method): headline numbers are
 * stat tiles, breakdowns are semantic tables, the one magnitude comparison
 * (outcome mix) is a single-hue proportional bar set reusing the site's
 * category fills, and pass/fail state is icon + label — never color alone.
 * Text wears text tokens; series color never carries text. All figures are
 * server-computed; this component renders and formats only.
 *
 * Live discipline is labeled per section: LIVE sections re-read parsed/raw/
 * review at every poll; PUBLISHED sections are pinned to the active published
 * run; BUILD sections are pinned to the latest completed fact build.
 */
import { useCallback, useEffect, useState } from 'react';
import { categoryFillClass } from '../components/category-fill';
import type { OpsNumbers } from './ops-types';

const INTERVALS = [
  { label: '5s', seconds: 5 },
  { label: '15s', seconds: 15 },
  { label: '60s', seconds: 60 },
  { label: 'Paused', seconds: 0 },
] as const;

const nf = new Intl.NumberFormat('en-US');
const n = (value: number | null | undefined) => nf.format(value ?? 0);

function timeOf(iso: string | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toISOString().replace('T', ' ').slice(0, 19) + 'Z';
}

function bytesLabel(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(1)} KB`;
  return `${bytes} B`;
}

function shortId(id: string | null): string {
  return id ? id.slice(0, 8) : '—';
}

type FetchState =
  | { kind: 'loading' }
  | { kind: 'disabled' }
  | { kind: 'unreachable' }
  | { kind: 'ready'; data: OpsNumbers; fetchedAt: Date; clientMs: number };

export function OpsDashboard() {
  const [state, setState] = useState<FetchState>({ kind: 'loading' });
  const [intervalSeconds, setIntervalSeconds] = useState<number>(15);

  const refresh = useCallback(async () => {
    const started = performance.now();
    try {
      const res = await fetch('/admin/numbers', { cache: 'no-store' });
      if (res.status === 404 || res.status === 401) {
        setState({ kind: 'disabled' });
        return;
      }
      if (!res.ok) {
        setState({ kind: 'unreachable' });
        return;
      }
      const data = (await res.json()) as OpsNumbers;
      setState({
        kind: 'ready',
        data,
        fetchedAt: new Date(),
        clientMs: Math.round(performance.now() - started),
      });
    } catch {
      setState({ kind: 'unreachable' });
    }
  }, []);

  // One effect owns the fetch cadence: an immediate tick behind a zero
  // timeout (the async boundary keeps setState out of the effect body) plus
  // the polling interval. Changing the interval re-arms both — an immediate
  // read on a cadence change is the desired behavior for a live dashboard.
  useEffect(() => {
    const tick = () => void refresh();
    const immediate = setTimeout(tick, 0);
    const interval = intervalSeconds > 0 ? setInterval(tick, intervalSeconds * 1000) : null;
    return () => {
      clearTimeout(immediate);
      if (interval) clearInterval(interval);
    };
  }, [intervalSeconds, refresh]);

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1>Operations</h1>
          <p className="text-sm text-muted">
            Every number on the canonical database. LIVE sections re-read at each refresh; PUBLISHED
            sections are pinned to the active published run; BUILD sections to the latest completed
            fact build.
          </p>
        </div>
        <RefreshControls
          state={state}
          intervalSeconds={intervalSeconds}
          onIntervalChange={setIntervalSeconds}
          onRefreshNow={() => void refresh()}
        />
      </header>

      {state.kind === 'loading' && <p className="text-muted">Loading the numbers…</p>}
      {state.kind === 'disabled' && (
        <div className="border border-hairline p-4 text-sm text-body">
          <p className="font-semibold text-ink">Ops feed is not enabled.</p>
          <p className="mt-1">
            Start the API with <code>ADMIN_OPS_ENABLED=1</code> (and <code>ADMIN_OPS_TOKEN</code> if
            you want the header check) against the local canonical database, then refresh.
          </p>
        </div>
      )}
      {state.kind === 'unreachable' && (
        <div className="border border-hairline p-4 text-sm text-body">
          <p className="font-semibold text-ink">The API is unreachable.</p>
          <p className="mt-1">Is the API running? The dashboard retries on the next refresh.</p>
        </div>
      )}
      {state.kind === 'ready' && <Sections data={state.data} />}
    </div>
  );
}

function RefreshControls({
  state,
  intervalSeconds,
  onIntervalChange,
  onRefreshNow,
}: {
  state: FetchState;
  intervalSeconds: number;
  onIntervalChange: (seconds: number) => void;
  onRefreshNow: () => void;
}) {
  return (
    <div className="space-y-1 text-right">
      <div className="flex items-center justify-end gap-2" role="group" aria-label="Refresh rate">
        <span className="text-xs font-semibold tracking-[.10em] text-faint uppercase">Refresh</span>
        {INTERVALS.map((option) => (
          <button
            key={option.label}
            type="button"
            onClick={() => onIntervalChange(option.seconds)}
            aria-pressed={intervalSeconds === option.seconds}
            className={`border px-2 py-1 text-xs font-semibold ${
              intervalSeconds === option.seconds
                ? 'border-ink bg-ink text-paper'
                : 'border-hairline text-body hover:border-ink'
            }`}
          >
            {option.label}
          </button>
        ))}
        <button
          type="button"
          onClick={onRefreshNow}
          className="border border-hairline px-2 py-1 text-xs font-semibold text-body hover:border-ink"
        >
          Now
        </button>
      </div>
      {state.kind === 'ready' && (
        <p className="text-xs text-faint" data-testid="refresh-meta">
          Updated {state.fetchedAt.toISOString().slice(11, 19)}Z · fetch {state.clientMs} ms ·
          queries {state.data.totalMs} ms · db {state.data.database}
        </p>
      )}
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border border-hairline p-3">
      <p className="text-xs font-semibold tracking-[.10em] text-faint uppercase">{label}</p>
      <p className="mt-1 font-serif text-2xl text-ink">{value}</p>
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

function Section({
  title,
  scope,
  ms,
  children,
}: {
  title: string;
  scope: 'LIVE' | 'PUBLISHED' | 'BUILD' | 'CHECKS';
  ms?: number;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 border-t-3 border-double border-ink pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-serif text-lg font-semibold text-ink">{title}</h2>
        <p className="text-xs text-faint">
          <span className="font-semibold">{scope}</span>
          {typeof ms === 'number' && <span> · {ms} ms</span>}
        </p>
      </div>
      {children}
    </section>
  );
}

function KvTable({ rows, testId }: { rows: Array<[string, string]>; testId?: string }) {
  return (
    <table className="w-full border-collapse text-left text-sm" data-testid={testId}>
      <tbody>
        {rows.map(([key, value]) => (
          <tr key={key}>
            <th scope="row" className="border-b border-hairline py-1 pr-4 font-normal text-body">
              {key}
            </th>
            <td className="border-b border-hairline py-1 text-right font-semibold text-ink">
              {value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Sections({ data }: { data: OpsNumbers }) {
  const {
    corpus,
    sourceDocuments,
    linkage,
    factBuilds,
    aggregateRuns,
    outcomes,
    charges,
    judges,
    reviewQueue,
    warnings,
    checks,
    timings,
  } = data;

  const failing = checks.filter((check) => !check.pass);

  return (
    <div className="space-y-8">
      <Section title="Every number accounted for" scope="CHECKS" ms={timings.checks}>
        <p className="text-sm text-muted">
          Each check recomputes an identity the pipeline relies on. {checks.length - failing.length}{' '}
          of {checks.length} passing.
        </p>
        <ul className="space-y-1">
          {checks.map((check) => (
            <li
              key={check.name}
              className="flex flex-wrap items-baseline justify-between gap-2 border-b border-hairline py-1 text-sm"
            >
              <span className="text-body">
                <span
                  className={`mr-2 inline-block border px-1.5 text-xs font-bold ${
                    check.pass
                      ? 'border-emerald-700 text-emerald-700'
                      : 'border-red-700 bg-red-700 text-white'
                  }`}
                >
                  {check.pass ? '✓ PASS' : '✕ FAIL'}
                </span>
                {check.detail}
              </span>
              <span className="font-mono text-xs text-muted">
                {n(check.left)} vs {n(check.right)}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Corpus" scope="LIVE" ms={timings.corpus}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Dockets" value={n(corpus.dockets)} />
          <Tile label="Charges" value={n(corpus.charges)} />
          <Tile
            label="In universe"
            value={n(corpus.chargesInUniverse)}
            hint={`filed ≥ 2025-01-01 · pre-floor ${n(corpus.chargesPreFloor)}`}
          />
          <Tile
            label="Superseded"
            value={n(corpus.chargesSuperseded)}
            hint="MC held rows traced to a CP twin"
          />
        </div>
        <div className="grid gap-6 tablet:grid-cols-2">
          <KvTable
            testId="corpus-table"
            rows={[
              ...Object.entries(corpus.docketsByCourt).map(
                ([court, count]) => [`Dockets · ${court}`, n(count)] as [string, string],
              ),
              ['Dockets with NULL filed date', n(corpus.docketsNullFiledDate)],
              ['Dockets flagged review-needed', n(corpus.docketsReviewNeeded)],
              ['Filed-date span', `${corpus.filedDateMin ?? '—'} → ${corpus.filedDateMax ?? '—'}`],
              ['Last load', timeOf(corpus.lastLoadedAt)],
            ]}
          />
          <KvTable
            rows={[
              ['Charges pending (no disposition)', n(corpus.chargesPending)],
              ['Charges disposed', n(corpus.chargesDisposed)],
              ['Distinct disposition forms', n(corpus.distinctDispositionForms)],
              [
                'Version pairs (record/envelope)',
                corpus.versionPairs
                  .map((pair) => `v${pair.record}/e${pair.envelope}: ${n(pair.dockets)}`)
                  .join(' · ') || '—',
              ],
              ['CP dockets naming an originating MC case', n(corpus.cpDocketsWithOriginating)],
              ['Charges with orig-seq captured', n(corpus.chargesWithOrigSeq)],
            ]}
          />
        </div>
      </Section>

      <Section title="Dedupe & linkage" scope="LIVE" ms={timings.linkage}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Supersession pointers" value={n(linkage.supersededPointers)} />
          <Tile label="Docket links" value={n(linkage.links)} />
          <Tile label="Resolved" value={n(linkage.resolved)} />
          <Tile
            label="Fetch list"
            value={n(linkage.unresolvedTargetNumbers)}
            hint="unresolved CP docket numbers to collect"
          />
        </div>
        <KvTable
          rows={[
            ['Unresolved links', n(linkage.unresolved)],
            ['Source dockets with links', n(linkage.sourceDockets)],
            ...Object.entries(linkage.byEvidence).map(
              ([evidence, count]) => [`Evidence · ${evidence}`, n(count)] as [string, string],
            ),
          ]}
        />
      </Section>

      <Section title="Source documents & refresh" scope="LIVE" ms={timings.sourceDocuments}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Documents" value={n(sourceDocuments.total)} />
          <Tile label="Volume" value={bytesLabel(sourceDocuments.totalBytes)} />
          <Tile label="Last import" value={timeOf(sourceDocuments.lastImportedAt)} />
          <Tile
            label="Last 14 days"
            value={n(sourceDocuments.importedPerDay.reduce((sum, day) => sum + day.documents, 0))}
            hint="documents imported"
          />
        </div>
        <div className="grid gap-6 tablet:grid-cols-2">
          <KvTable
            rows={Object.entries(sourceDocuments.byStatus).map(
              ([status, count]) => [`Status · ${status}`, n(count)] as [string, string],
            )}
          />
          <KvTable
            rows={
              sourceDocuments.importedPerDay.length > 0
                ? sourceDocuments.importedPerDay.map(
                    (day) => [day.day, n(day.documents)] as [string, string],
                  )
                : [['No imports in the last 14 days', '—']]
            }
          />
        </div>
      </Section>

      <Section title="Fact builds" scope="BUILD" ms={timings.factBuilds}>
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr>
              {['Run', 'Status', 'Started', 'Completed', 'Counts'].map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="border-b border-ink py-1 pr-3 text-xs font-semibold tracking-[.10em] text-faint uppercase"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {factBuilds.map((run) => (
              <tr key={run.id}>
                <td className="border-b border-hairline py-1 pr-3 font-mono text-xs">
                  {shortId(run.id)}
                </td>
                <td className="border-b border-hairline py-1 pr-3">{run.status}</td>
                <td className="border-b border-hairline py-1 pr-3 font-mono text-xs">
                  {timeOf(run.startedAt)}
                </td>
                <td className="border-b border-hairline py-1 pr-3 font-mono text-xs">
                  {timeOf(run.completedAt)}
                </td>
                <td className="border-b border-hairline py-1 font-mono text-[11px] break-all">
                  {run.counts ? JSON.stringify(run.counts) : '—'}
                </td>
              </tr>
            ))}
            {factBuilds.length === 0 && (
              <tr>
                <td colSpan={5} className="py-2 text-muted">
                  No fact builds yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Section>

      <Section title="Aggregate runs" scope="PUBLISHED" ms={timings.aggregateRuns}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Active run" value={shortId(aggregateRuns.activePublishedRunId)} />
          <Tile label="Published" value={timeOf(aggregateRuns.publishedAt)} />
          <Tile
            label="Data range"
            value={`${aggregateRuns.dataRangeStart ?? '—'} → ${aggregateRuns.dataRangeEnd ?? '—'}`}
          />
          <Tile
            label="Build run"
            value={shortId(aggregateRuns.buildRunId)}
            hint={`taxonomy ${aggregateRuns.taxonomyVersion ?? '—'}`}
          />
        </div>
        <div className="grid gap-6 tablet:grid-cols-2">
          <KvTable
            rows={Object.entries(aggregateRuns.rowsByTable).map(
              ([table, count]) => [table, n(count)] as [string, string],
            )}
          />
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr>
                {['Run', 'Status', 'Published', 'Invalidated'].map((header) => (
                  <th
                    key={header}
                    scope="col"
                    className="border-b border-ink py-1 pr-3 text-xs font-semibold tracking-[.10em] text-faint uppercase"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {aggregateRuns.recent.map((run) => (
                <tr key={run.id}>
                  <td className="border-b border-hairline py-1 pr-3 font-mono text-xs">
                    {shortId(run.id)}
                  </td>
                  <td className="border-b border-hairline py-1 pr-3">{run.status}</td>
                  <td className="border-b border-hairline py-1 pr-3 font-mono text-xs">
                    {timeOf(run.publishedAt)}
                  </td>
                  <td className="border-b border-hairline py-1 font-mono text-xs">
                    {timeOf(run.invalidatedAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Outcomes & rates" scope="PUBLISHED" ms={timings.outcomes}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Records (published)" value={n(outcomes.published.totalRecords)} />
          <Tile
            label="Dismissed + withdrawn"
            value={
              outcomes.published.dismissedOrWithdrawnShare === null
                ? '—'
                : `${outcomes.published.dismissedOrWithdrawnShare}%`
            }
            hint="historical share of recorded outcomes"
          />
          <Tile label="Public facts (latest build)" value={n(outcomes.latestBuildPublicFacts)} />
          <Tile
            label="Categories"
            value={n(outcomes.published.byCategory.length)}
            hint="in the published mix"
          />
        </div>
        <div aria-hidden="true" className="space-y-1">
          {outcomes.published.byCategory.map((row) => (
            <div key={row.category} className="space-y-0.5">
              <div className="flex justify-between gap-4 text-sm text-body">
                <span>{row.category}</span>
                <span className="text-xs font-semibold text-ink">
                  {n(row.count)} · {row.share}%
                </span>
              </div>
              <div className="chart-track h-3 w-full overflow-hidden">
                <div
                  className={`h-full ${categoryFillClass('outcome', row.category)}`}
                  style={{ width: `${row.share}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <KvTable
          rows={outcomes.published.byCategory.map(
            (row) => [row.category, `${n(row.count)} (${row.share}%)`] as [string, string],
          )}
        />
      </Section>

      <Section title="Charges" scope="PUBLISHED" ms={timings.charges}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Roster (active)" value={n(charges.rosterActive)} />
          <Tile label="Aliases" value={n(charges.aliases)} />
          <Tile label="With outcomes" value={n(charges.withOutcomeAggregates)} />
          <Tile
            label="With volume rows"
            value={n(charges.withVolumeRows)}
            hint={`thin outcome charges ${n(charges.thinOutcomeCharges)}`}
          />
        </div>
        {charges.volumeTotals && (
          <KvTable
            testId="volume-totals"
            rows={[
              ['Charges seen (deduplicated)', n(charges.volumeTotals.chargesSeen)],
              ['With recorded outcomes', n(charges.volumeTotals.outcomesRecorded)],
              ['Held for court (untraced)', n(charges.volumeTotals.heldForCourt)],
              ['Still pending', n(charges.volumeTotals.stillPending)],
              ['Disposed, excluded', n(charges.volumeTotals.disposedExcluded)],
              ['Folded into CP twins', n(charges.volumeTotals.heldSuperseded)],
            ]}
          />
        )}
        <div className="grid gap-6 tablet:grid-cols-2">
          <table className="w-full border-collapse text-left text-sm">
            <caption className="pb-1 text-left text-xs font-semibold tracking-[.10em] text-faint uppercase">
              Top charges by volume
            </caption>
            <tbody>
              {charges.topByVolume.map((row) => (
                <tr key={row.slug}>
                  <th
                    scope="row"
                    className="border-b border-hairline py-1 pr-3 font-normal text-body"
                  >
                    {row.slug}
                  </th>
                  <td className="border-b border-hairline py-1 pr-3 text-right font-semibold text-ink">
                    {n(row.chargesSeen)}
                  </td>
                  <td className="border-b border-hairline py-1 text-right text-xs text-muted">
                    {n(row.outcomesRecorded)} outcomes · {n(row.heldSuperseded)} folded
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <table className="w-full border-collapse text-left text-sm">
            <caption className="pb-1 text-left text-xs font-semibold tracking-[.10em] text-faint uppercase">
              Top charges by outcome sample
            </caption>
            <tbody>
              {charges.topBySample.map((row) => (
                <tr key={row.slug}>
                  <th
                    scope="row"
                    className="border-b border-hairline py-1 pr-3 font-normal text-body"
                  >
                    {row.slug}
                  </th>
                  <td className="border-b border-hairline py-1 text-right font-semibold text-ink">
                    {n(row.sampleSize)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Judges" scope="PUBLISHED" ms={timings.judges}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Roster (active)" value={n(judges.rosterActive)} />
          <Tile label="Aliases" value={n(judges.aliases)} />
          <Tile label="With aggregates" value={n(judges.withAggregates)} />
          <Tile
            label="Charge × judge pairs"
            value={n(judges.chargeJudgePairs)}
            hint={`thin pairs ${n(judges.thinPairs)}`}
          />
        </div>
        <KvTable
          rows={judges.topBySample.map(
            (row) => [row.slug, `${n(row.records)} records`] as [string, string],
          )}
        />
      </Section>

      <Section title="Review queue" scope="LIVE" ms={timings.reviewQueue}>
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          <Tile label="Total items" value={n(reviewQueue.total)} />
          {Object.entries(reviewQueue.byStatus).map(([status, count]) => (
            <Tile key={status} label={`Status · ${status}`} value={n(count)} />
          ))}
        </div>
        <div className="grid gap-6 tablet:grid-cols-2">
          <KvTable
            rows={Object.entries(reviewQueue.openByType).map(
              ([type, count]) => [type, n(count)] as [string, string],
            )}
          />
          <KvTable
            rows={Object.entries(reviewQueue.openBySeverity).map(
              ([severity, count]) => [`Severity · ${severity}`, n(count)] as [string, string],
            )}
          />
        </div>
      </Section>

      <Section title="Parser warnings" scope="LIVE" ms={timings.warnings}>
        <KvTable
          rows={Object.entries(warnings).map(
            ([code, count]) => [code, n(count)] as [string, string],
          )}
        />
      </Section>

      <Section title="Query timings" scope="LIVE">
        <KvTable
          rows={Object.entries(timings).map(
            ([section, ms]) => [section, `${n(ms)} ms`] as [string, string],
          )}
        />
      </Section>
    </div>
  );
}
