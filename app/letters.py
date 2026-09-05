"""Rebuttal-letter / concede-memo generation.

Called by: app/main.py (POST /disputes/{id}/respond).

Defense-only by construction: a sentence for a given evidence field is
appended to the letter body if and only if
`record["evidence"].get(field_name) is True`. There is no LLM in this
path and no way for a sentence to render off a field that isn't
literally True on the record -- see tests/test_smoke.py's
anti-fabrication test. The LLM-drafting path (an LLM paraphrasing these
grounded bullet points into more natural prose) is designed-for-not-built
tonight; see README.md.
"""

from abc import ABC, abstractmethod

from app.reason_codes import REASON_CODES

# Per reason code: ordered list of (field_name, sentence_template) pairs.
# sentence_template may reference {dispute_id}/{order_id}/{dispute_amount_inr}
# via str.format, since those fields always exist on every record.
LETTER_SENTENCES = {
    "10.4": [
        ("avs_match", "The billing address provided at checkout matched the address on file with the card issuer (AVS match)."),
        ("cvv_match", "The card verification value (CVV) was correctly provided and matched at the time of purchase."),
        ("three_ds_authenticated", "The transaction was authenticated via 3-D Secure, confirming cardholder participation."),
        ("device_fingerprint_match_prior_orders", "The device used for this transaction matches the device fingerprint of prior undisputed orders on this account."),
        ("ip_billing_geo_match", "The purchasing IP address geolocation is consistent with the cardholder's billing region."),
        ("prior_undisputed_orders_gte_3", "This account has at least 3 prior undisputed orders, indicating an established, legitimate purchase history."),
        ("delivered_to_avs_matched_address", "Order {order_id} was delivered to the address verified by AVS at checkout."),
    ],
    "13.1": [
        ("delivery_confirmed", "Delivery of order {order_id} is confirmed by the carrier."),
        ("tracking_number_present", "A valid carrier tracking number exists for this shipment and is on file."),
        ("signature_captured", "A delivery signature was captured, confirming receipt by the customer or an authorized recipient."),
        ("shipping_address_matches_billing", "The shipping address matches the billing address on the cardholder's account."),
        ("digital_access_logs_present", "Server-side access logs confirm the customer accessed the purchased digital product/service after the transaction."),
    ],
    "13.3": [
        ("item_description_shown_at_purchase", "The item description shown to the customer at the time of purchase accurately represented the product."),
        ("product_photos_available", "Product photographs shown at checkout accurately depicted the item as delivered."),
        ("tnc_accepted_at_checkout", "The customer explicitly accepted the terms and conditions at checkout."),
        ("return_policy_shown_at_checkout", "The return policy was clearly displayed to the customer at checkout, prior to purchase."),
        ("support_communication_exists", "Customer support communication records exist for this order and are available on request."),
        ("no_return_attempted_by_customer", "No return of the merchandise for order {order_id} was ever attempted or received from the customer."),
    ],
    "13.6": [
        ("refund_issued", "A refund of INR {dispute_amount_inr} for order {order_id} has been issued to the original payment method."),
        ("refund_issued_before_dispute_date", "The refund for this order was issued prior to the date this dispute was filed."),
        ("return_received_confirmed", "The returned merchandise for this order was received and confirmed by our warehouse."),
        ("refund_policy_stated_at_checkout", "Our refund policy was clearly stated to the customer at checkout, prior to purchase."),
    ],
    "13.2": [
        ("subscription_terms_accepted", "The customer explicitly accepted the subscription terms, including billing cadence, prior to the first charge."),
        ("cancellation_policy_shown", "The cancellation policy was clearly displayed to the customer prior to subscribing."),
        ("cancellation_record_exists", "No cancellation request was recorded on this account prior to the disputed charge."),
        ("usage_after_alleged_cancellation_date", "Account usage logs show active use of the subscription after the customer's alleged cancellation date."),
        ("advance_notice_given", "Advance notice of the renewal charge was provided to the customer as required."),
    ],
    "UPI_UNAUTHORIZED": [
        ("upi_pin_authenticated", "The UPI transaction was authenticated with the customer's UPI PIN at the time of payment."),
        ("device_binding_match", "The transaction originated from the device bound to the customer's registered UPI handle."),
        ("mobile_number_match_registered", "The mobile number used for this UPI transaction matches the number registered on the customer's account."),
        ("prior_successful_upi_txns_with_payee", "This customer has completed prior successful UPI transactions with this same payee, indicating an established payment relationship."),
    ],
}


def sentence_for(reason_code: str, field_name: str, record: dict) -> str:
    """The exact grounded sentence for one evidence field, formatted with
    this record's own identifiers -- used by the UI's evidence-checklist
    click interaction. Returns the real sentence regardless of whether the
    field is actually True on the record (so an analyst can see what
    WOULD render if it were present); the letter body itself still only
    ever includes sentences for fields that are True (see
    TemplateGenerator._generate_represent_letter below) -- this function
    never fabricates a field value, it just formats known template text.
    """
    fmt_kwargs = {
        "dispute_id": record.get("dispute_id"),
        "order_id": record.get("order_id"),
        "dispute_amount_inr": record.get("dispute_amount_inr"),
    }
    for f, template in LETTER_SENTENCES.get(reason_code, []):
        if f == field_name:
            return template.format(**fmt_kwargs)
    return ""


class LetterGenerator(ABC):
    @abstractmethod
    def generate(self, record: dict, decision: dict, evidence: dict) -> str:
        """Return the letter (represent) or memo (concede) text for a dispute."""
        raise NotImplementedError


class TemplateGenerator(LetterGenerator):
    """Template-only letter generator: no LLM. Every sentence is grounded
    in a real, present-and-True evidence field on the record -- it cannot
    fabricate a claim the merchant doesn't actually have on file.

    LLM-drafting path (paraphrasing these grounded facts into smoother
    prose) is designed-for-not-built; see README.md.
    """

    def generate(self, record: dict, decision: dict, evidence: dict) -> str:
        if decision["decision"] == "concede":
            return self._generate_concede_memo(record, decision)
        return self._generate_represent_letter(record, decision, evidence)

    def _generate_represent_letter(self, record: dict, decision: dict, evidence: dict) -> str:
        reason_code = record["reason_code"]
        rc = REASON_CODES[reason_code]
        sentences = LETTER_SENTENCES.get(reason_code, [])

        fmt_kwargs = {
            "dispute_id": record.get("dispute_id"),
            "order_id": record.get("order_id"),
            "dispute_amount_inr": record.get("dispute_amount_inr"),
        }

        body_lines = []
        for field_name, template in sentences:
            if evidence.get(field_name) is True:
                body_lines.append("- " + template.format(**fmt_kwargs))

        lines = [
            "REBUTTAL LETTER -- REPRESENTMENT",
            "=" * 40,
            f"Dispute ID: {record['dispute_id']}    Order ID: {record['order_id']}",
            f"Reason Code: {reason_code} ({rc.description})",
            f"Disputed Amount: INR {record['dispute_amount_inr']:g}",
            "",
            "We respectfully submit the following evidence in support of representment "
            "of the above transaction:",
            "",
        ]
        lines.extend(body_lines)
        lines.append("")
        lines.append(
            f"Decision basis: {decision['rule_applied']}"
        )
        return "\n".join(lines)

    def _generate_concede_memo(self, record: dict, decision: dict) -> str:
        """Visibly distinct, clearly labeled internal memo -- not a
        customer-facing rebuttal. This is the point: the system also
        knows when NOT to fight, and that's a first-class feature, not
        a fallback.
        """
        reasons = []
        if decision["expected_value_inr"] <= 0:
            reasons.append(
                f"expected value is not positive "
                f"(win_probability {decision['win_probability']:.2f} x amount "
                f"INR {record['dispute_amount_inr']:g} does not clear the "
                f"representment cost)"
            )
        reasons.append(
            f"evidence coverage is {decision['evidence_coverage']:.2f} for reason "
            f"code {record['reason_code']}"
        )

        lines = [
            "INTERNAL MEMO -- CONCEDE (no customer-facing letter generated)",
            "=" * 40,
            f"Dispute ID: {record['dispute_id']}    Order ID: {record['order_id']}",
            f"Reason Code: {record['reason_code']}",
            f"Disputed Amount: INR {record['dispute_amount_inr']:g}",
            "",
            "Recommendation: CONCEDE this dispute. Do not file a representment.",
            "",
            "Rationale: " + "; ".join(reasons) + ".",
            "",
            f"Decision basis: {decision['rule_applied']}",
        ]
        return "\n".join(lines)
