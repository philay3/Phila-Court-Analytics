import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Definitions',
};

export default function DefinitionsPage() {
  return (
    <>
      <h1>Definitions</h1>
      <p>
        This page will define the terms used across the site — charge categories, disposition types,
        sentencing terms, and measures such as sample size — in plain English.
      </p>
    </>
  );
}
