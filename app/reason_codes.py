"""Reason-code registry: card-network dispute reason codes and the
evidence checklist a merchant needs to represent (fight) each one.

Used by:
- data/generate_data.py: to know which evidence fields to synthesize per
  reason code.
- app/scoring.py: all_evidence_fields() defines the ML feature-vector
  columns.
- app/decision.py: coverage() feeds the evidence_coverage_floor rule.
- app/letters.py: each (field, sentence) pair in a rebuttal template is
  keyed off these same field names.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReasonCode:
    code: str
    description: str
    evidence_fields: tuple  # ordered tuple[str, ...] of boolean field names


REASON_CODES: dict[str, ReasonCode] = {
    "10.4": ReasonCode(
        code="10.4",
        description="Fraud - Card Absent Environment",
        evidence_fields=(
            "avs_match",
            "cvv_match",
            "three_ds_authenticated",
            "device_fingerprint_match_prior_orders",
            "ip_billing_geo_match",
            "prior_undisputed_orders_gte_3",
            "delivered_to_avs_matched_address",
        ),
    ),
    "13.1": ReasonCode(
        code="13.1",
        description="Merchandise / Services Not Received",
        evidence_fields=(
            "delivery_confirmed",
            "tracking_number_present",
            "signature_captured",
            "shipping_address_matches_billing",
            "digital_access_logs_present",
        ),
    ),
    "13.3": ReasonCode(
        code="13.3",
        description="Not as Described / Defective",
        evidence_fields=(
            "item_description_shown_at_purchase",
            "product_photos_available",
            "tnc_accepted_at_checkout",
            "return_policy_shown_at_checkout",
            "support_communication_exists",
            "no_return_attempted_by_customer",
        ),
    ),
    "13.6": ReasonCode(
        code="13.6",
        description="Credit Not Processed",
        evidence_fields=(
            "refund_issued",
            "refund_issued_before_dispute_date",
            "return_received_confirmed",
            "refund_policy_stated_at_checkout",
        ),
    ),
    "13.2": ReasonCode(
        code="13.2",
        description="Cancelled Recurring Transaction",
        evidence_fields=(
            "subscription_terms_accepted",
            "cancellation_policy_shown",
            "cancellation_record_exists",
            "usage_after_alleged_cancellation_date",
            "advance_notice_given",
        ),
    ),
    "UPI_UNAUTHORIZED": ReasonCode(
        code="UPI_UNAUTHORIZED",
        description="India Domestic - Unauthorized UPI Transaction",
        evidence_fields=(
            "upi_pin_authenticated",
            "device_binding_match",
            "mobile_number_match_registered",
            "prior_successful_upi_txns_with_payee",
        ),
    ),
}


def all_evidence_fields() -> list:
    """Deduplicated union of every evidence field across all reason codes,
    in a stable (first-seen, dict-iteration) order. This defines the
    fixed column order used to build the ML feature vector so every
    record -- regardless of its own reason code -- produces a vector of
    the same length/order (fields not relevant to a record's reason code
    are simply 0).
    """
    seen: dict = {}
    for rc in REASON_CODES.values():
        for f in rc.evidence_fields:
            seen[f] = True
    return list(seen.keys())


def coverage(reason_code: str, observed: dict) -> float:
    """Fraction of `reason_code`'s own checklist fields that are True in
    `observed`. Fields absent from `observed` count as False (missing
    evidence is not evidence).
    """
    rc = REASON_CODES[reason_code]
    if not rc.evidence_fields:
        return 0.0
    true_count = sum(1 for f in rc.evidence_fields if observed.get(f) is True)
    return true_count / len(rc.evidence_fields)
