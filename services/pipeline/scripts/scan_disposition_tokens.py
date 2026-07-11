"""Task 18.5 corpus evidence tooling — charge-line disposition-token scan.

Enumerates every DISTINCT non-empty charge-line disposition token that appears
under a NOT-FINAL event across the extracted corpus, and cross-references each
occurrence against the Capstone baseline so the ARD_CLASS / NON_TERMINAL
partition is derived from evidence, not from semantic labelling (Task 18.5
REQUIRED FIX 1). The committed routing vocabulary (two frozensets in
``docket_parser``) is finalized by hand from this scan's output; only the token
LIST is committable — the per-docket occurrences stay in the out-of-repo report.

Why the partition keys on Final-event coverage
----------------------------------------------
The 18.5 redesign routes at the CHARGE-LINE level (token in ARD_CLASS); Final
Disposition events ALWAYS route regardless of token. So a Not-Final token needs
to be in ARD_CLASS only for charges whose baseline disposition the Final path
canNOT reproduce. Two real-corpus facts (verified, not assumed) force this:

  1. Terminal dispositions genuinely appear under Not-Final events — e.g.
     "Quashed" / "Nolle Prossed" under a "Pretrial Bring Back ... Not Final"
     event. Most such charges ALSO carry a Final Disposition event that supplies
     the same disposition, so the always-routing Final path already reproduces
     them and the Not-Final token need NOT route.
  2. A charge held at "Held for Court" (Not Final) and later found guilty at a
     Final event is DISPOSED in its final baseline state, so a naive final-state
     split double-counts the commonest non-terminal.

So each occurrence is scored in two steps. First, is the disposition ATTRIBUTABLE
to this Not-Final event —

    baseline.disposition_raw == token (token survived as the final raw), OR
    baseline.disposition_date in this event block's judge-line dates.

Then, is the same seq ALSO disposed under a Final event on this docket? If yes,
``final_also_disposed`` (Final path covers it). If no, ``not_final_only`` — only
routing this Not-Final event reproduces the disposition. ``not_final_only`` is
the must-route signal.

Partition CANDIDATE (mechanical; the planning chat finalizes membership):

    not_final_only == 0            -> NON_TERMINAL  (all disposed occ. Final-covered)
    not_final_only == corpus_count -> ARD_CLASS     (every occurrence must route)
    otherwise                      -> MIXED  (STOP — adjudicate)

``raw_equals_token`` is reported for the wrapped revoked token specifically: if
any docket ENDS on a revoked event the baseline disposed that charge with the
wrap token as raw. One caveat the must-route signal cannot see: an ARD event
whose disposition_raw is overwritten by a later Final event but whose
judge/sentence-date/sentences are NOT (the progression case) reads as
``final_also_disposed`` yet still needs routing for those fields — a plan-level
adjudication, not a mechanical verdict.

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
from pipeline.envelope import _artifact_docket_number
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


def _final_disposed_seqs(lines: list[str], charges_by_seq: dict) -> set[int]:
    """Sequences disposed under a FINAL Disposition event on this docket.

    A seq is final-covered when it appears on a charge line under a Final
    Disposition event with a NON-EMPTY disposition token — the Final path routes
    it regardless of the 18.5 vocabulary. Used to split each disposed Not-Final
    occurrence into ``final_also_disposed`` (the Final path already reproduces the
    disposition) vs ``not_final_only`` (only routing the Not-Final event does).
    """
    seqs: set[int] = set()
    in_final = False
    for line in lines:
        if EVENT_RE.search(line):
            in_final = line.endswith("Final Disposition")
            continue
        if not in_final:
            continue
        charge_match = CHARGE_RE.match(line)
        if charge_match:
            seq = int(charge_match.group(1))
            token = charge_line_token(
                charge_match.group(2).strip(), charges_by_seq.get(seq)
            )
            if token:
                seqs.add(seq)
    return seqs


def _new_token_row() -> dict:
    return {
        "corpus_count": 0,
        "disposed_under_event": 0,  # = not_final_only + final_also_disposed
        "not_final_only": 0,  # disposed here AND no Final event covers the seq
        "final_also_disposed": 0,  # disposed here BUT a Final event also covers it
        "held_under_event": 0,
        "raw_equals_token": 0,
        "baseline_missing": 0,
        # Out-of-repo detail only (hash-prefix ids, CPCMS raws) — never printed.
        "must_route_dockets": set(),
        "baseline_raws": set(),
        "not_final_only_examples": [],
    }


def _partition(row: dict) -> str:
    """Mechanical partition CANDIDATE — the planning chat finalizes membership.

    Keyed on ``not_final_only``: occurrences whose baseline disposition the
    Final-event path cannot reproduce (no Final event covers the seq), i.e. the
    must-route set. ANY must-route occurrence => ARD_CLASS candidate; none =>
    NON_TERMINAL-safe even when some charges are disposed (all Final-covered);
    a partial split => MIXED (STOP, adjudicate — e.g. the wrap-token and the
    terminal-under-Not-Final cases). NOTE the one caveat this signal cannot see:
    an ARD event whose disposition_raw IS overwritten by a later Final event but
    whose judge/sentence-date/sentences are NOT (the progression case) is
    ``final_also_disposed`` yet still needs routing to reproduce those fields —
    adjudicated at plan level, not by this metric.
    """
    corpus = row["corpus_count"]
    must_route = row["not_final_only"]
    if must_route == 0:
        return "NON_TERMINAL"
    if must_route == corpus:
        return "ARD_CLASS"
    return "MIXED"


def scan(artifacts_dir: Path, baseline_dir: Path, salt: str) -> dict:
    """Walk the extracted artifacts, classify every Not-Final charge-line token.

    Discovery + loading mirror the 18.1 parse CLI (envelope.run_parse): every
    ``*.json`` under artifacts_dir is loaded, the docket number comes from the
    shared ``_artifact_docket_number``, and NO extraction-status filter is
    applied — run_parse parses every artifact's ``pages`` regardless of status
    (statuses are success/partial/needs_ocr_or_review/failed, never "extracted").
    An artifact whose ``pages`` is empty (a ``failed`` extraction) carries no
    disposition text and contributes no tokens.
    """
    baseline = load_baseline(baseline_dir)

    tokens: dict[str, dict] = defaultdict(_new_token_row)
    artifacts_found = 0
    artifacts_scanned = 0
    empty_artifacts = 0
    parse_failures = 0

    for artifact_path in sorted(artifacts_dir.glob("*.json")):
        artifacts_found += 1
        artifact = json.loads(artifact_path.read_text())
        pages_text = list(artifact.get("pages", []))
        docket_number = _artifact_docket_number(artifact)
        source_sha256 = str(artifact.get("source_sha256", ""))
        hash_prefix = (source_sha256 or "unknown")[:HASH_PREFIX_LEN]
        if not pages_text:
            empty_artifacts += 1  # failed/empty extraction: no tokens to find
            continue
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

        dispo = disposition_lines(pages_text)
        final_seqs = _final_disposed_seqs(dispo, charges_by_seq)
        for block in _not_final_blocks(dispo):
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

                # Attributed to THIS Not-Final event: the token survived as the
                # final raw, or the baseline disposition_date lands on a judge
                # line inside this event's block.
                disposed = raw is not None and (
                    raw_equals or (disp_date is not None and disp_date in judge_dates)
                )
                if not disposed:
                    row["held_under_event"] += 1
                    continue

                row["disposed_under_event"] += 1
                row["baseline_raws"].add(raw)
                if seq in final_seqs:
                    # A Final event also disposes this seq — the Final path (which
                    # always routes) reproduces it, so routing here is not required
                    # to keep the charge disposed.
                    row["final_also_disposed"] += 1
                else:
                    # Only routing this Not-Final event keeps the charge disposed.
                    row["not_final_only"] += 1
                    row["must_route_dockets"].add(hash_prefix)
                    if len(row["not_final_only_examples"]) < 20:
                        row["not_final_only_examples"].append(
                            {"docket": hash_prefix, "sequence": seq}
                        )

    return {
        "artifacts_found": artifacts_found,
        "artifacts_scanned": artifacts_scanned,
        "empty_artifacts": empty_artifacts,
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
        f"artifacts_found={result['artifacts_found']} "
        f"artifacts_scanned={result['artifacts_scanned']} "
        f"empty_artifacts={result['empty_artifacts']} "
        f"parse_failures={result['parse_failures']} "
        f"baseline_records={result['baseline_records_loaded']} "
        f"baseline_dockets={result['baseline_unique_dockets']}"
    )
    lines.append("")
    # Full token column (no truncation — distinct tokens must display distinctly;
    # 40-char slicing previously hid e.g. two "DUI: ... 1st Off*" tokens as one).
    # "must" = not_final_only (the Final path cannot reproduce these); "fcov" =
    # final_also_disposed; "raw=" = baseline raw literally equals the token.
    width = max((len(t) for t in tokens), default=len("TOKEN"))
    cols = f"{'corpus':>7} {'must':>5} {'fcov':>5} {'held':>6} {'raw=':>5}"
    header = f"{'TOKEN':<{width}} {cols}  PARTITION"
    lines.append(header)
    lines.append("-" * len(header))
    for part_name, bucket in (
        ("ARD_CLASS", ard_class),
        ("NON_TERMINAL", non_terminal),
        ("MIXED", mixed),
    ):
        for token in bucket:
            row = tokens[token]
            counts = (
                f"{row['corpus_count']:>7} {row['not_final_only']:>5} "
                f"{row['final_also_disposed']:>5} {row['held_under_event']:>6} "
                f"{row['raw_equals_token']:>5}"
            )
            lines.append(f"{token:<{width}} {counts}  {part_name}")

    # Must-route aggregate: charges/dockets the Final path CANNOT reproduce, so
    # only Not-Final routing recovers them. These are the ARD_CLASS ∪ MIXED
    # candidates whose partition the planning chat finalizes.
    must_tokens = ard_class + mixed
    must_charges = sum(tokens[t]["not_final_only"] for t in must_tokens)
    must_dockets: set[str] = set()
    for t in must_tokens:
        must_dockets |= tokens[t]["must_route_dockets"]
    lines.append("")
    lines.append(
        f"must-route (not_final_only) total: {must_charges} charges across "
        f"{len(must_dockets)} dockets"
    )
    lines.append(f"ARD_CLASS candidate tokens={len(ard_class)}")
    lines.append(f"NON_TERMINAL tokens={len(non_terminal)}")
    lines.append(f"MIXED tokens={len(mixed)}  (STOP — plan-level adjudication)")
    if mixed:
        lines.append("MIXED tokens (some must-route, some Final-covered/held):")
        for token in mixed:
            row = tokens[token]
            lines.append(
                f"  {token!r}: corpus={row['corpus_count']} "
                f"must_route={row['not_final_only']} "
                f"final_covered={row['final_also_disposed']} "
                f"held={row['held_under_event']} "
                f"raw_equals_token={row['raw_equals_token']}"
            )

    artifact = {
        "summary": {
            "artifacts_found": result["artifacts_found"],
            "artifacts_scanned": result["artifacts_scanned"],
            "empty_artifacts": result["empty_artifacts"],
            "parse_failures": result["parse_failures"],
            "baseline_records_loaded": result["baseline_records_loaded"],
            "baseline_unique_dockets": result["baseline_unique_dockets"],
            "ard_class_tokens": ard_class,
            "non_terminal_tokens": non_terminal,
            "mixed_tokens": mixed,
            "must_route_charges": must_charges,
            "must_route_dockets": len(must_dockets),
        },
        "tokens": {
            token: {
                "corpus_count": row["corpus_count"],
                "disposed_under_event": row["disposed_under_event"],
                "not_final_only": row["not_final_only"],
                "final_also_disposed": row["final_also_disposed"],
                "held_under_event": row["held_under_event"],
                "raw_equals_token": row["raw_equals_token"],
                "baseline_missing": row["baseline_missing"],
                "partition": _partition(row),
                "must_route_dockets": sorted(row["must_route_dockets"]),
                "baseline_raws": sorted(row["baseline_raws"]),
                "not_final_only_examples": row["not_final_only_examples"],
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

    # Fail-loud: an empty table must never exit 0 (Task 18.5 continuation item 3).
    # These are the two silent-defect signatures — no artifacts processed, or
    # artifacts processed but the disposition walk matched nothing.
    if result["artifacts_scanned"] == 0:
        if result["artifacts_found"] == 0:
            print(
                f"no *.json extraction artifacts found in {args.artifacts_dir}",
                file=sys.stderr,
            )
        else:
            print(
                f"found {result['artifacts_found']} artifacts but none carried "
                f"pages (empty={result['empty_artifacts']}); nothing to scan — "
                "check the artifact shape",
                file=sys.stderr,
            )
        return 2
    if not result["tokens"]:
        print(
            f"scanned {result['artifacts_scanned']} artifacts but found ZERO "
            "Not-Final charge-line tokens — the disposition-section walk is not "
            "matching real layout; refusing to emit an empty table",
            file=sys.stderr,
        )
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
