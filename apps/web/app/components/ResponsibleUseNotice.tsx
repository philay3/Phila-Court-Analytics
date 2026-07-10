/**
 * Responsible-use notice (task 13.1). Renders the four required framing
 * statements — historical-aggregate context, the two guarded disclaimers, and
 * the reminder that individual cases vary — assembled in order from the copy
 * module. All four strings live in `RESULT_DISPLAY_COPY`; none is typed inline.
 */
import { RESULT_DISPLAY_COPY } from './result-display-copy';

const STATEMENTS = [
  RESULT_DISPLAY_COPY.responsibleUseHistorical,
  RESULT_DISPLAY_COPY.responsibleUseNotLegalAdvice,
  RESULT_DISPLAY_COPY.responsibleUseNotPrediction,
  RESULT_DISPLAY_COPY.responsibleUseCasesVary,
];

export function ResponsibleUseNotice() {
  return (
    <aside className="text-sm text-muted">
      <ul className="list-disc space-y-1 pl-5">
        {STATEMENTS.map((statement) => (
          <li key={statement}>{statement}</li>
        ))}
      </ul>
    </aside>
  );
}
