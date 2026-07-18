/**
 * Definitions page presentational views (task 14.1). No data fetching lives
 * here — the server component (page.tsx) fetches via the 11.2 client and
 * branches; these components are fully testable under jsdom.
 *
 * Pinned behaviour:
 *   - Categories render in the exact order the API served them (already in
 *     taxonomy sortOrder). There is NO client-side sort or grouping beyond the
 *     two server-provided sections.
 *   - Each entry's heading carries a stable element id minted from the shared
 *     `definitionAnchorId` helper — the same source the 13.1 result-page links
 *     build their `/definitions#<kind>-<code>` fragments from — so fragment
 *     navigation from a result page lands on the entry. Because this is a server
 *     component render, those ids are present in the server-rendered HTML.
 *   - Single-column, mobile-first, semantic heading hierarchy: h1 → h2 per
 *     section → h3 per category entry.
 *
 * All framing copy comes from `DEFINITIONS_COPY`; the category display names and
 * definitions come straight from the typed API response. The error body is a
 * shared @pca/shared constant selected upstream by failure arm.
 */
import type { DefinitionEntry, DefinitionsResponse } from '@pca/shared';
import { definitionAnchorId, type DistributionKind } from '../lib/definition-anchor';
import { DEFINITIONS_COPY } from './definitions-copy';

interface DefinitionsSectionProps {
  kind: DistributionKind;
  heading: string;
  entries: readonly DefinitionEntry[];
}

function DefinitionsSection({ kind, heading, entries }: DefinitionsSectionProps) {
  return (
    <section className="space-y-6">
      <h2 className="section-counter border-t-3 border-double border-ink pt-2 text-sm font-semibold tracking-[.12em] text-ink uppercase">
        {heading}
      </h2>
      <dl className="space-y-6">
        {entries.map((entry) => (
          <div
            key={entry.code}
            className="space-y-1 border-b border-hairline pb-4 md:grid md:grid-cols-[185px_1fr] md:gap-x-4 md:space-y-0"
          >
            <dt>
              <h3
                id={definitionAnchorId(kind, entry.code)}
                className="scroll-mt-24 font-serif text-base font-semibold text-ink"
              >
                {entry.displayName}
              </h3>
            </dt>
            <dd className="text-sm leading-relaxed text-body">{entry.definition}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

interface DefinitionsViewProps {
  data: DefinitionsResponse;
}

export function DefinitionsView({ data }: DefinitionsViewProps) {
  return (
    <div className="section-counter-reset flex flex-col gap-10">
      <header className="space-y-3">
        <h1>{DEFINITIONS_COPY.heading}</h1>
        <p className="text-muted">{DEFINITIONS_COPY.intro}</p>
      </header>

      <DefinitionsSection
        kind="outcome"
        heading={DEFINITIONS_COPY.outcomeSectionHeading}
        entries={data.outcomes}
      />

      <DefinitionsSection
        kind="sentencing"
        heading={DEFINITIONS_COPY.sentencingSectionHeading}
        entries={data.sentencing}
      />

      <footer>
        <p className="text-sm text-faint">
          {DEFINITIONS_COPY.taxonomyVersionLabel}: {data.taxonomyVersion}
        </p>
      </footer>
    </div>
  );
}

interface DefinitionsErrorStateProps {
  /** User-facing message, pre-selected from @pca/shared constants by failure arm. */
  message: string;
}

export function DefinitionsErrorState({ message }: DefinitionsErrorStateProps) {
  return (
    <div className="space-y-4">
      <h1>{DEFINITIONS_COPY.errorHeading}</h1>
      <p role="alert" className="text-muted">
        {message}
      </p>
    </div>
  );
}
