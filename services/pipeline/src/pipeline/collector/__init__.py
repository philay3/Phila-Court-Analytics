"""Automated docket-collection command (Task COL-1).

Ports Capstone's portal-fetch logic into a code-enforced pacing/stop regime:
a hard 240-minute ceiling, a jittered per-request delay, post-block and
inter-batch cooldowns, a consecutive-block streak stop and a consecutive-error
streak stop, and per-attempt outcome logging. Pacing that Capstone left to a
shell wrapper (``run_loop.sh``) and operator attention is enforced here in code.

Import-safety: no module in this package imports Playwright at import time
(``transport`` imports it lazily inside its methods), so the whole package —
and therefore the test suite — imports cleanly without the optional
``collector`` dependency group installed. Production parse/extract stages
import nothing from here.
"""
