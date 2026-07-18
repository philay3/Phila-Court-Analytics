'use client';

/**
 * Judge-filter disclosure (task DP-3, bglad §14.3 adapted per the approved
 * plan). A native-button disclosure hiding the judge control on the charge
 * page (inside the metadata aside, wrapping JudgeFilterEntry from the
 * OUTSIDE) and on the homepage (inside the search card's judge region). The
 * wrapped content — combobox ARIA, testids, staged-commit logic, strings —
 * is byte-identical to DP-2; only its visibility is new.
 *
 * Contract (DP-3 acceptance criterion 4):
 *   - native <button type="button"> with aria-expanded + aria-controls;
 *   - default closed; state lives in the component, so it naturally resets
 *     on route change (bglad §7.4);
 *   - closed content uses the `hidden` attribute (display:none) — never
 *     visually-hidden duplication, so nothing is double-exposed to AT;
 *   - NO height animation (the sanctioned simpler option), which trivially
 *     respects prefers-reduced-motion;
 *   - the plus/minus glyph is CSS generated content (disclosure-glyph
 *     utility) keyed off aria-expanded, excluded from the accessible name —
 *     the button's name is the sanctioned trigger string alone;
 *   - open content appears immediately below with a 12px gap (§14.3);
 *   - ≥44px target height (§7.4).
 */
import { useId, useState, type ReactNode } from 'react';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

interface JudgeDisclosureProps {
  /** The existing judge control region, rendered unchanged when open. */
  children: ReactNode;
}

export function JudgeDisclosure({ children }: JudgeDisclosureProps) {
  const contentId = useId();
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={contentId}
        onClick={() => setExpanded((open) => !open)}
        className="disclosure-glyph min-h-11 text-left text-sm font-semibold text-accent hover:text-accent-hover hover:underline"
      >
        {CHARGE_RESULT_COPY.judgeDisclosureTriggerText}
      </button>
      <div id={contentId} hidden={!expanded} className="mt-3">
        {children}
      </div>
    </div>
  );
}
