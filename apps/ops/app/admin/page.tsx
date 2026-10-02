import type { Metadata } from 'next';
import { OpsDashboard } from './OpsDashboard';

/**
 * Operator ops dashboard (Phase 36). Server shell only — the dashboard is a
 * client component polling the same-origin /admin/numbers proxy. The page is
 * operator-facing: it renders its disabled state unless the API runs with
 * ADMIN_OPS_ENABLED=1 (never the case in the deployed topology, where the
 * internal tables don't exist). Site-wide noindex is inherited from the root
 * layout, and nothing here is linked from any public page.
 */
export const metadata: Metadata = {
  title: 'Operations',
};

export default function AdminPage() {
  return <OpsDashboard />;
}
