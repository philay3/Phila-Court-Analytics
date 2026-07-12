"""Committed, repeatable corpus-reporting tools (Task 22.2).

Curation/acceptance tooling that reads the loaded corpus DB and writes detailed
reports to ``~/court-data/reports/`` (outside the repo tree). Every tool here:

- refuses to run in a CI environment (``running_in_ci`` guard, 21.3 pattern);
- reads ``DATABASE_URL`` at the run boundary only, never at import, never logged;
- keeps console output to counts / match methods / statute-code cites — never
  offense-text or other free-text values (those land only in the report files);
- embeds NO corpus-derived data in the committed code.
"""
