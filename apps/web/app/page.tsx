import Link from 'next/link';

export default function HomePage() {
  return (
    <>
      <h1>Philadelphia Court Outcomes</h1>
      <p>
        Philadelphia Court Outcomes presents historical aggregate outcomes in Philadelphia criminal
        court cases. It summarizes how charges were resolved in the past — historical outcome
        distributions and historical sentencing distributions, shown Philadelphia-wide and as
        judge-specific results — always with the sample size behind each figure.
      </p>
      <p>
        This site describes what happened in past cases. It is not legal advice, and it is not a
        prediction of what will happen in any current or future case. Where the underlying data is
        thin, we say so rather than draw conclusions.
      </p>
      <p>
        To understand how these figures are produced, see the{' '}
        <Link href="/methodology">Methodology</Link>. For the time window and courts the data
        covers, see <Link href="/data-coverage">Data Coverage</Link>.
      </p>
      <p>Search is coming soon.</p>
    </>
  );
}
