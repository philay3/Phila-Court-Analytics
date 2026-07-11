"""Task 18.5 corpus evidence tooling — charge-line disposition-token scan.

Enumerates every DISTINCT non-empty charge-line disposition token that appears
under a NOT-FINAL event across the extracted corpus, and cross-references each
occurrence against the Capstone baseline so the ARD_CLASS / NON_TERMINAL
partition is derived from evidence, not from semantic labelling (Task 18.5
REQUIRED FIX 1). The committed routing vocabulary (two frozensets in
``docket_parser``) is finalized by hand from this scan's output; only the token
LIST is committable — the per-docket occurrences stay in the out-of-repo report.

Why the cross-reference is attribution-based, not final-state-based
------------------------------------------------------------------
Capstone routed at the EVENT level: when a Not-Final event's case-status row
contained "ard", every charge line under it routed regardless of token. The
18.5 redesign routes at the CHARGE-LINE level (token in ARD_CLASS). The two are
equivalent only if every token the baseline disposed *under a Not-Final event*
is in ARD_CLASS. A charge held at "Held for Court" (Not Final) and later found
guilty at a Final event is DISPOSED in its final baseline state, so a naive
final-state split would mark "Held for Court" both disposed (progressed charges)
and held (held-forever charges) — a false MIXED on the commonest non-terminal.
So an occurrence counts as ``disposed_under_event`` only when the disposition is
ATTRIBUTABLE to this Not-Final event:

    baseline.disposition_raw == token                       (token survived as
                                                             the final raw), OR
    baseline.disposition_date in this event block's judge-line dates
                                                            (the event sourced
                                                             the disposition).

Partition rule (mechanical; MIXED is a plan-level STOP per the task):

    disposed_under_event == corpus_count (> 0)          -> ARD_CLASS  (must route)
    disposed_under_event == 0 and raw_equals_token == 0 -> NON_TERMINAL
    otherwise                                            -> MIXED  (STOP)

``raw_equals_token`` decides the wrapped revoked token specifically: if any
docket ENDS on a revoked event, the baseline disposed that charge with the wrap
token as raw, so the token must be ARD_CLASS or the 18.5 fix would itself
un-dispose it. Only the cross-reference can see this — the inspected progression
docket cannot (its revoked write was masked by the terminal overwrite).

Privacy
-------
Console prints CPCMS tokens and structural counts ONLY — never docket numbers,
defendant text, dates, or sequences. The detailed artifact is written OUTSIDE
the git worktree (default ``~/court-data/scan-disposition-tokens/``); it keys
dockets by source-hash prefix (never docket number), as the tier-2 report does.
Refuses to run in CI and refuses to write inside the worktree. Requires
DEFENDANT_HASH_SALT (the parser hashes the defendant name); the salt is never
printed or written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from pipeline.docket_parser import HEADERS, parse_docket_text
from pipeline.equivalence_check import SALT_ENV_VAR, BaselineError, load_baseline
from pipeline.helpers import parse_date
from pipeline.paths import inside_git_worktree
from pipeline.seam_check import running_in_ci

# Regexes mirroring the docket_parser disposition loop (source of truth:
# docket_parser.py:649-715). Scan-only — the shipped routing uses the real
# parser; this replication exists so the scan can see the RAW charge-line token
# under Not-Final events, which the (v5) parser record no longer exposes.
EVENT_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(?:Final Disposition|Not Final)$")
CHARGE_RE = re.compile(r"^(\d+)\s*/\s*(.*)$")
JUDGE_LINE_RE = re.compile(r"^(.*?)\s+(\d{2}/\d{2}/\d{4})$")

HASH_PREFIX_LEN = 12

# Page furniture stripped before sectioning — mirrors docket_parser.py:323-354
# so stray page-break furniture (e.g. a "... Printed: MM/DD/YYYY" footer) never
# pollutes a Not-Final event block's judge-line dates.
_FURNITURE_EXACT = frozenset(
    {
        "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY",
        "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
        "DOCKET",
        "CRIMINAL DOCKET",
        "Court Case",
        "Commonwealth of Pennsylvania",
    }
)
_FURNITURE_CONTAINS = (
    "Recent entries made in the court",
    "Neither the courts of the Unified Judicial",
    "System of the Commonwealth of Pennsylvania",
    "data, errors or omissions on these reports",
    "only be provided by the Pennsylvania State Police",
    "Moreover an employer who does not comply",
    "Information Act may be subject to civil liability",
)
_FURNITURE_PREFIX = ("Docket Number:",)
_FURNITURE_RE = (
    re.compile(r"^Page \d+ of \d+$"),
    re.compile(r"^CPCMS .* Printed:.*$", re.IGNORECASE),
)


def _is_furniture(line_str: str) -> bool:
    if line_str in _FURNITURE_EXACT:
        return True
    if any(line_str.startswith(prefix) for prefix in _FURNITURE_PREFIX):
        return True
    if any(needle in line_str for needle in _FURNITURE_CONTAINS):
        return True
    return any(pattern.match(line_str) for pattern in _FURNITURE_RE)


def disposition_lines(pages_text: list[str]) -> list[str]:
    """The stripped, furniture-filtered lines of the DISPOSITION section.

    Mirrors the docket_parser section split (docket_parser.py:296-359) for the
    one section this scan needs. Header/footer furniture is dropped first so it
    cannot appear inside an event block.
    """
    out: list[str] = []
    current_section: str | None = None
    for text in pages_text:
        for raw in text.splitlines():
            line_str = raw.strip()
            if not line_str or _is_furniture(line_str):
                continue
            if line_str in HEADERS:
                current_section = line_str
            elif current_section == "DISPOSITION SENTENCING/PENALTIES":
                out.append(line_str)
    return out


def charge_line_token(text: str, charge: dict | None) -> str:
    """The charge-line disposition token: text minus offense/statute/grade.

    Byte-identical algorithm to docket_parser.py:694-708 (longest offense prefix
    off the front, then statute and grade off the tail). The stripping charge
    fields come from the parsed record so the token matches what the shipped
    router will compute. Returns "" when the charge is unknown (defensive; a
    charge line under an event should always be in the record).
    """
    if charge is None:
        return ""
    offense = charge.get("offense") or ""
    matched_prefix = ""
    for i in range(len(offense), 0, -1):
        prefix = offense[:i].strip()
        if text.startswith(prefix):
            matched_prefix = prefix
            break
    remaining = text[len(matched_prefix) :].strip()

    statute = charge.get("statute") or ""
    if statute and remaining.endswith(statute):
        remaining = remaining[: -len(statute)].strip()
    grade = charge.get("grade") or ""
    if grade and remaining.endswith(grade):
        remaining = remaining[: -len(grade)].strip()
    return remaining


def _not_final_blocks(lines: list[str]) -> list[list[str]]:
    """Split DISPOSITION lines into the body lines of each NOT-FINAL event.

    A block is the lines between one event header and the next. Final
    Disposition events are dropped — this scan is only about Not-Final routing.
    Lines before the first event header (rare) are ignored.
    """
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if EVENT_RE.search(line):
            if line.endswith("Final Disposition"):
                current = None  # a Final event: stop collecting
            else:
                current = []
                blocks.append(current)
            continue
        if current is not None:
            current.append(line)
    return blocks


def _iter_charge_occurrences(block: list[str]):
    """Yield (seq, charge_text, judge_dates) for each charge line in a block.

    ``judge_dates`` is the set of ISO dates on judge lines that follow this
    charge line up to the next charge line — the disposition_date the parser
    would attribute to this charge under this event.
    """
    i = 0
    n = len(block)
    while i < n:
        charge_match = CHARGE_RE.match(block[i])
        if not charge_match:
            i += 1
            continue
        seq = int(charge_match.group(1))
        text = charge_match.group(2).strip()
        judge_dates: set[str] = set()
        j = i + 1
        while j < n and not CHARGE_RE.match(block[j]):
            judge_match = JUDGE_LINE_RE.match(block[j])
            if judge_match:
                iso = parse_date(judge_match.group(2))
                if iso:
                    judge_dates.add(iso)
            j += 1
        yield seq, text, judge_dates
        i = j


def _new_token_row() -> dict:
    return {
        "corpus_count": 0,
        "disposed_under_event": 0,
        "held_under_event": 0,
        "raw_equals_token": 0,
        "baseline_missing": 0,
        # Out-of-repo detail only (hash-prefix ids, CPCMS raws) — never printed.
        "dockets_disposed": set(),
        "baseline_raws": set(),
        "mixed_examples": [],
    }


def _partition(row: dict) -> str:
    corpus = row["corpus_count"]
    disposed = row["disposed_under_event"]
    if corpus > 0 and disposed == corpus:
        return "ARD_CLASS"
    if disposed == 0 and row["raw_equals_token"] == 0:
        return "NON_TERMINAL"
    return "MIXED"


def scan(artifacts_dir: Path, baseline_dir: Path, salt: str) -> dict:
    """Walk the extracted artifacts, classify every Not-Final charge-line token."""
    baseline = load_baseline(baseline_dir)

    tokens: dict[str, dict] = defaultdict(_new_token_row)
    artifacts_scanned = 0
    parse_failures = 0

    for artifact_path in sorted(artifacts_dir.glob("*.json")):
        artifact = json.loads(artifact_path.read_text())
        if artifact.get("status") != "extracted":
            continue
        pages_text = list(artifact.get("pages", []))
        # Docket number from the filename stem (import convention, 17.3 /
        # envelope._artifact_docket_number).
        docket_number = Path(str(artifact.get("original_filename", ""))).stem
        source_sha256 = str(artifact.get("source_sha256", ""))
        hash_prefix = (source_sha256 or "unknown")[:HASH_PREFIX_LEN]
        artifacts_scanned += 1

        try:
            record, _sentinels, _warnings = parse_docket_text(
                docket_number, pages_text, salt=salt
            )
        except Exception:  # noqa: BLE001 - one bad docket must not abort the scan
            parse_failures += 1
            continue

        charges_by_seq = {c["sequence"]: c for c in record.get("charges", [])}
        baseline_record = baseline.index.get(docket_number)
        baseline_by_seq = {}
        if baseline_record is not None:
            baseline_by_seq = {
                c.get("sequence"): c for c in baseline_record.get("charges", [])
            }

        for block in _not_final_blocks(disposition_lines(pages_text)):
            for seq, text, judge_dates in _iter_charge_occurrences(block):
                token = charge_line_token(text, charges_by_seq.get(seq))
                if not token:
                    continue  # empty token = normal held rendering (RF2)
                row = tokens[token]
                row["corpus_count"] += 1

                baseline_charge = baseline_by_seq.get(seq)
                if baseline_record is None or baseline_charge is None:
                    row["baseline_missing"] += 1
                    row["held_under_event"] += 1
                    continue

                raw = baseline_charge.get("disposition_raw")
                disp_date = baseline_charge.get("disposition_date")
                raw_equals = raw is not None and raw == token
                if raw_equals:
                    row["raw_equals_token"] += 1
                    row["baseline_raws"].add(raw)

                disposed = raw is not None and (
                    raw_equals or (disp_date is not None and disp_date in judge_dates)
                )
                if disposed:
                    row["disposed_under_event"] += 1
                    row["dockets_disposed"].add(hash_prefix)
                    if raw is not None:
                        row["baseline_raws"].add(raw)
                else:
                    row["held_under_event"] += 1
                    if len(row["mixed_examples"]) < 20:
                        row["mixed_examples"].append(
                            {"docket": hash_prefix, "sequence": seq, "held": True}
                        )

    return {
        "artifacts_scanned": artifacts_scanned,
        "parse_failures": parse_failures,
        "baseline_records_loaded": baseline.records_loaded,
        "baseline_unique_dockets": len(baseline.index),
        "tokens": tokens,
    }


def _render(result: dict) -> tuple[str, dict]:
    """Build the console report (tokens + counts only) and the JSON artifact."""
    tokens: dict[str, dict] = result["tokens"]
    ard_class, non_terminal, mixed = [], [], []
    for token in sorted(tokens):
        part = _partition(tokens[token])
        {"ARD_CLASS": ard_class, "NON_TERMINAL": non_terminal, "MIXED": mixed}[
            part
        ].append(token)

    lines: list[str] = []
    lines.append(
        f"artifacts_scanned={result['artifacts_scanned']} "
        f"parse_failures={result['parse_failures']} "
        f"baseline_records={result['baseline_records_loaded']} "
        f"baseline_dockets={result['baseline_unique_dockets']}"
    )
    lines.append("")
    header = (
        f"{'TOKEN':<40} {'corpus':>7} {'disp':>6} {'held':>6} {'raw=':>5}  PARTITION"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for part_name, bucket in (
        ("ARD_CLASS", ard_class),
        ("NON_TERMINAL", non_terminal),
        ("MIXED", mixed),
    ):
        for token in bucket:
            row = tokens[token]
            lines.append(
                f"{token[:40]:<40} {row['corpus_count']:>7} "
                f"{row['disposed_under_event']:>6} {row['held_under_event']:>6} "
                f"{row['raw_equals_token']:>5}  {part_name}"
            )

    # Restoration aggregate: what ARD_CLASS routing recovers.
    restored_charges = sum(tokens[t]["disposed_under_event"] for t in ard_class)
    restored_dockets: set[str] = set()
    for t in ard_class:
        restored_dockets |= tokens[t]["dockets_disposed"]
    lines.append("")
    lines.append(
        f"ARD_CLASS tokens={len(ard_class)} "
        f"restore {restored_charges} charges across {len(restored_dockets)} dockets"
    )
    lines.append(f"NON_TERMINAL tokens={len(non_terminal)}")
    lines.append(f"MIXED tokens={len(mixed)}  (STOP — plan-level adjudication)")
    if mixed:
        lines.append("MIXED tokens require adjudication before frozensets finalize:")
        for token in mixed:
            row = tokens[token]
            lines.append(
                f"  {token[:60]!r}: corpus={row['corpus_count']} "
                f"disposed={row['disposed_under_event']} "
                f"held={row['held_under_event']} "
                f"raw_equals_token={row['raw_equals_token']}"
            )

    artifact = {
        "summary": {
            "artifacts_scanned": result["artifacts_scanned"],
            "parse_failures": result["parse_failures"],
            "baseline_records_loaded": result["baseline_records_loaded"],
            "baseline_unique_dockets": result["baseline_unique_dockets"],
            "ard_class_tokens": ard_class,
            "non_terminal_tokens": non_terminal,
            "mixed_tokens": mixed,
            "restored_charges": restored_charges,
            "restored_dockets": len(restored_dockets),
        },
        "tokens": {
            token: {
                "corpus_count": row["corpus_count"],
                "disposed_under_event": row["disposed_under_event"],
                "held_under_event": row["held_under_event"],
                "raw_equals_token": row["raw_equals_token"],
                "baseline_missing": row["baseline_missing"],
                "partition": _partition(row),
                "dockets_disposed": sorted(row["dockets_disposed"]),
                "baseline_raws": sorted(row["baseline_raws"]),
                "mixed_examples": row["mixed_examples"],
            }
            for token, row in sorted(tokens.items())
        },
    }
    return "\n".join(lines) + "\n", artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan charge-line disposition tokens under Not-Final events and "
            "classify them against the Capstone baseline (Task 18.5 RF1)."
        )
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path.home() / "court-data" / "extracted",
        help="Extraction artifacts (*.json). Default: ~/court-data/extracted/.",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path.home() / "court-data" / "capstone-baseline",
        help="Capstone baseline records. Default: ~/court-data/capstone-baseline/.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path.home() / "court-data" / "scan-disposition-tokens",
        help=(
            "Out-of-repo dir for the detailed JSON artifact. "
            "Default: ~/court-data/scan-disposition-tokens/."
        ),
    )
    args = parser.parse_args(argv)

    if running_in_ci():
        print(
            "refusing to run in CI: this scan reads local court data", file=sys.stderr
        )
        return 2
    if inside_git_worktree(args.out):
        print(
            "refusing to write inside the git worktree: --out must be out-of-repo",
            file=sys.stderr,
        )
        return 2
    salt = os.environ.get(SALT_ENV_VAR, "")
    if not salt:
        print(
            f"{SALT_ENV_VAR} is required (the parser hashes the defendant name); "
            "set it in the environment. It is never printed or written.",
            file=sys.stderr,
        )
        return 2
    if not args.artifacts_dir.is_dir():
        print(f"artifacts dir not found: {args.artifacts_dir}", file=sys.stderr)
        return 2
    if not args.baseline_dir.is_dir():
        print(f"baseline dir not found: {args.baseline_dir}", file=sys.stderr)
        return 2

    try:
        result = scan(args.artifacts_dir, args.baseline_dir, salt)
    except BaselineError as exc:
        print(f"baseline load failed: {type(exc).__name__}", file=sys.stderr)
        return 2

    console, artifact = _render(result)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "disposition-token-scan.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n"
    )
    print(console, end="")
    print(f"detail written: {args.out / 'disposition-token-scan.json'}")
    return 1 if artifact["summary"]["mixed_tokens"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
