import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Data Coverage',
};

export default function DataCoveragePage() {
  return (
    <>
      <h1>Data Coverage</h1>
      <p>
        Outcome data on this site is anchored to disposition and sentencing event dates on or after
        January 1, 2025. This page will detail which courts, case types, and time periods are
        covered, and how coverage grows over time.
      </p>
    </>
  );
}
