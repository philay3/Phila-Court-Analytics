import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'About',
};

export default function AboutPage() {
  return (
    <>
      <h1>About</h1>
      <p>
        This page will describe the project: who is behind it, why it exists, and the principles
        that guide it — transparency about sources and methods, and responsible presentation of
        historical court data.
      </p>
    </>
  );
}
