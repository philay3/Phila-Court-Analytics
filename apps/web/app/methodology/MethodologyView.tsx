/**
 * Methodology page presentational views (task 14.2). No data fetching lives
 * here — the server component (page.tsx) fetches via the 11.2 client and
 * branches; these components are fully testable under jsdom.
 *
 * Pinned behaviour:
 *   - Sections render in the exact presentation order fixed by the shared
 *     `METHODOLOGY_SECTION_KEYS` constant (the same order the schema pins), so
 *     there is no client-side reordering.
 *   - Every section's `heading` and `body` render exactly as served — this
 *     component adds no prose of its own inside a section. The only page copy is
 *     the h1 / error / loading chrome in METHODOLOGY_COPY.
 *   - Single-column, mobile-first, semantic heading hierarchy: h1 → h2 per
 *     section.
 *
 * The error body is a shared @pca/shared constant selected upstream by failure
 * arm (see methodology-failure.ts); it is never composed here.
 */
import { METHODOLOGY_SECTION_KEYS, type MethodologyResponse } from '@pca/shared';
import { METHODOLOGY_COPY } from './methodology-copy';

interface MethodologyViewProps {
  data: MethodologyResponse;
}

export function MethodologyView({ data }: MethodologyViewProps) {
  return (
    <div className="section-counter-reset flex flex-col gap-10 desktop:gap-12">
      <header>
        <h1>{METHODOLOGY_COPY.heading}</h1>
      </header>

      {METHODOLOGY_SECTION_KEYS.map((key) => {
        const section = data.sections[key];
        return (
          <section key={key} className="space-y-3">
            <h2 className="section-counter border-t-3 border-double border-ink pt-2 text-sm font-semibold tracking-[.12em] text-ink uppercase">
              {section.heading}
            </h2>
            <p className="leading-relaxed text-body">{section.body}</p>
          </section>
        );
      })}
    </div>
  );
}

interface MethodologyErrorStateProps {
  /** User-facing message, pre-selected from @pca/shared constants by failure arm. */
  message: string;
}

export function MethodologyErrorState({ message }: MethodologyErrorStateProps) {
  return (
    <div className="space-y-4">
      <h1>{METHODOLOGY_COPY.errorHeading}</h1>
      <p role="alert" className="text-muted">
        {message}
      </p>
    </div>
  );
}
