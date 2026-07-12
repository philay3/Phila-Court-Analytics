"""Tier-1 tests for the sentencing recon/coverage report (Task 22.5, AC 8).

Exercises the PURE classification functions (no DB): the recon per-type counters,
the coverage distribution that the corpus rerun reports, the money bucketing, the
duration-contamination diagnostic, and the FAC-label fine isolation. All inputs
are synthetic; the DB boundary and console hygiene are covered by the module's
guards, not here.
"""

from __future__ import annotations

from pipeline.normalization.sentencing_mapper import (
    SentencingMapper,
    SentencingTaxonomy,
)
from pipeline.reports import sentencing_coverage as sc

SYNTH_TAXONOMY = SentencingTaxonomy(
    taxonomy_version="9.9.9-test",
    public_by_code={
        "probation": True,
        "incarceration": True,
        "fine": True,
        "restitution": True,
        "community_service": True,
        "no_further_penalty": True,
        "costs_fees": True,
        "other": True,
        "unknown": False,
    },
)


def test_money_bucket_boundaries():
    assert sc.money_bucket(0) == "0"
    assert sc.money_bucket(1) == "1"
    assert sc.money_bucket(2) == "2+"
    assert sc.money_bucket(9) == "2+"


def test_candidate_diagnostic_is_duration_contaminated():
    # The committed diagnostic still shows WHY `$`-optional was rejected: a bare
    # "11.00" duration is a "money" token to the candidate but not to the locked
    # `$`-required extractor.
    assert sc.distinct_candidate_cents("Min of 11.00 Max of 23.00 months") == {
        1100,
        2300,
    }


def test_fine_beyond_label_ignores_the_leading_fac_label():
    assert sc._fine_beyond_label("Fines and Costs", "Fines and Costs $500.00") is False
    assert sc._fine_beyond_label("Fines and Costs", "Fines and Costs, Fine $30") is True
    assert sc._fine_beyond_label("Probation", "Probation Fine imposed") is True


def test_recon_counts_per_type_and_signals():
    rows = [
        ("Fines and Costs", "Fines and Costs"),
        ("Probation", "Probation Restitution $500.00"),
        ("ARD", "ARD Restitution $100.00 plus $250.00"),
        ("Confinement", "Confinement 40 hours"),
    ]
    stats = sc.recon_counts(rows)
    assert stats["total"] == 4
    assert stats["distinct_types"] == 4
    per = stats["per_type"]
    # $-money buckets (locked regex): 1 distinct for Probation, 2+ for ARD.
    assert per["Probation"]["dmoney_1"] == 1
    assert per["ARD"]["dmoney_2+"] == 1
    assert per["Fines and Costs"]["dmoney_0"] == 1
    # signals
    assert per["Probation"]["restitution"] == 1
    assert per["Confinement"]["hours_only"] == 1


def test_coverage_counts_matches_the_mapper_distribution():
    mapper = SentencingMapper(SYNTH_TAXONOMY)
    rows = [
        ("Confinement", "Confinement 6 months"),
        ("Probation", "Probation, Restitution $500.00"),  # +restitution, SET
        ("ARD", "ARD Restitution $1.00 and $2.00"),  # +restitution, unparseable
        ("Fines and Costs", "Fines and Costs"),  # costs_fees, absent
        ("No Further Penalty", "No Further Penalty"),
        ("Probation", "Probation Community Service 20 hours"),  # +community_service
        ("Confinement", "Confinement 40 hours"),  # ambiguous CS
        ("Weird New Type", "Weird New Type"),  # unmapped -> unknown
    ]
    stats = sc.coverage_counts(mapper, rows)
    base = stats["base_by_code"]
    assert base["incarceration"] == 2
    assert base["probation"] == 2
    assert base["other"] == 1
    assert base["costs_fees"] == 1
    assert base["no_further_penalty"] == 1
    assert base["unknown"] == 1
    additive = stats["additive"]
    assert additive["restitution"] == 2
    assert additive["community_service"] == 1
    assert stats["ambiguous_cs"] == 1
    # money: monetary comps = 2 restitution + 1 costs_fees = 3.
    assert stats["monetary"] == 3
    assert stats["money_set"] == 1  # the $500.00 restitution
    assert stats["money_unparseable"] == 1  # the $1/$2 restitution
    assert stats["money_absent"] == 1  # bare Fines and Costs
