import type { Metadata } from 'next';
import { PUBLIC_ERROR_CODES } from '@pca/shared';

export const metadata: Metadata = {
  title: 'Import proof',
};

// Task 11.1 packaging proof: a value import (not a type-only import) from the
// built @pca/shared package, referenced in a server component so `next build`
// exercises real runtime resolution of the workspace package. This route
// carries no product copy and is slated for deletion in task 11.2, which
// replaces it with the real API client module.
const sharedErrorCodeCount = Object.keys(PUBLIC_ERROR_CODES).length;

export default function ImportProofPage() {
  return (
    <>
      <h1>Import proof</h1>
      <p>Shared package resolved with {sharedErrorCodeCount} error codes.</p>
    </>
  );
}
