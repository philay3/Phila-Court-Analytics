import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Methodology',
};

export default function MethodologyPage() {
  return (
    <>
      <h1>Methodology</h1>
      <p>
        This page will describe how the data is collected, processed, and aggregated: the source
        court records, how charges and outcomes are categorized, how historical outcome
        distributions are computed, and how sample sizes and thin data are handled and disclosed.
      </p>
    </>
  );
}
