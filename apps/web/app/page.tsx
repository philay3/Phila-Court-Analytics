import Link from 'next/link';
import { SearchForm } from './components/SearchForm';
import { HOME_COPY } from './components/home-copy';

export default function HomePage() {
  return (
    <>
      <h1>{HOME_COPY.heading}</h1>
      <p className="text-muted">{HOME_COPY.intro}</p>

      <SearchForm />

      <p className="mt-8 text-muted">{HOME_COPY.disclaimer}</p>

      <p className="mt-4 text-muted">
        {HOME_COPY.linksIntro}{' '}
        <Link
          href="/methodology"
          className="text-accent underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {HOME_COPY.methodologyLinkText}
        </Link>{' '}
        ({HOME_COPY.methodologyLinkDescription}) ·{' '}
        <Link
          href="/data-coverage"
          className="text-accent underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {HOME_COPY.dataCoverageLinkText}
        </Link>{' '}
        ({HOME_COPY.dataCoverageLinkDescription}).
      </p>
    </>
  );
}
