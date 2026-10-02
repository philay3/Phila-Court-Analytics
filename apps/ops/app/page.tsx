import { redirect } from 'next/navigation';

// The dashboard keeps its /admin URL from the web app (byte-identical move);
// the ops root just forwards to it.
export default function OpsHome() {
  redirect('/admin');
}
