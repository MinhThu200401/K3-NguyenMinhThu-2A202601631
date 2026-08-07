"""
Lab 11 — Part 4: Human-in-the-Loop Design
  TODO 11: Confidence Router
  TODO 12: Design 3 HITL decision points
"""
from dataclasses import dataclass


# ============================================================
# TODO 11: Implement ConfidenceRouter
#
# Route agent responses based on confidence scores:
#   - HIGH (>= 0.9): Auto-send to user
#   - MEDIUM (0.7 - 0.9): Queue for human review
#   - LOW (< 0.7): Escalate to human immediately
#
# Special case: if the action is HIGH_RISK (e.g., money transfer,
# account deletion), ALWAYS escalate regardless of confidence.
#
# Implement the route() method.
# ============================================================

HIGH_RISK_ACTIONS = [
    "transfer_money",
    "close_account",
    "change_password",
    "delete_data",
    "update_personal_info",
]


@dataclass
class RoutingDecision:
    """Result of the confidence router."""
    action: str          # "auto_send", "queue_review", "escalate"
    confidence: float
    reason: str
    priority: str        # "low", "normal", "high"
    requires_human: bool


class ConfidenceRouter:
    """Route agent responses based on confidence and risk level.

    Thresholds:
        HIGH:   confidence >= 0.9 -> auto-send
        MEDIUM: 0.7 <= confidence < 0.9 -> queue for review
        LOW:    confidence < 0.7 -> escalate to human

    High-risk actions always escalate regardless of confidence.
    """

    HIGH_THRESHOLD = 0.9
    MEDIUM_THRESHOLD = 0.7

    def route(self, response: str, confidence: float,
              action_type: str = "general") -> RoutingDecision:
        """Route a response based on confidence score and action type.

        Args:
            response: The agent's response text
            confidence: Confidence score between 0.0 and 1.0
            action_type: Type of action (e.g., "general", "transfer_money")

        Returns:
            RoutingDecision with routing action and metadata
        """
        # TODO 11: Implement routing logic
        #
        # 1. Check if action_type is in HIGH_RISK_ACTIONS
        #    -> If yes: always escalate (action="escalate", priority="high",
        #       requires_human=True, reason="High-risk action: {action_type}")
        #
        # 2. Check confidence thresholds:
        #    - confidence >= 0.9:
        #      action="auto_send", priority="low",
        #      requires_human=False, reason="High confidence"
        #
        #    - 0.7 <= confidence < 0.9:
        #      action="queue_review", priority="normal",
        #      requires_human=True, reason="Medium confidence — needs review"
        #
        #    - confidence < 0.7:
        #      action="escalate", priority="high",
        #      requires_human=True, reason="Low confidence — escalating"

        if action_type in HIGH_RISK_ACTIONS:
            return RoutingDecision(
                action="escalate",
                confidence=confidence,
                reason=f"High-risk action: {action_type}",
                priority="high",
                requires_human=True,
            )

        if confidence >= self.HIGH_THRESHOLD:
            return RoutingDecision(
                action="auto_send",
                confidence=confidence,
                reason="High confidence",
                priority="low",
                requires_human=False,
            )

        if confidence >= self.MEDIUM_THRESHOLD:
            return RoutingDecision(
                action="queue_review",
                confidence=confidence,
                reason="Medium confidence — needs review",
                priority="normal",
                requires_human=True,
            )

        return RoutingDecision(
            action="escalate",
            confidence=confidence,
            reason="Low confidence — escalating",
            priority="high",
            requires_human=True,
        )


# ============================================================
# TODO 12: Design 3 HITL decision points + a review lifecycle
#
# For each decision point, define:
# - trigger: What condition activates this HITL check?
# - hitl_model: Which model? (human-in-the-loop, human-on-the-loop,
#   human-as-tiebreaker)
# - context_needed: What info does the human reviewer need?
# - example: A concrete scenario
# - approval_path: What approve/reject/timeout decision is recorded?
# - audit_fields: Which correlation ID, intent and proposed action/diff are logged?
#
# Think about real banking scenarios where human judgment is critical.
# ============================================================

hitl_decision_points = [
    {
        "id": 1,
        "name": "Outbound money transfer above threshold",
        "trigger": "action_type == 'transfer_money' with amount over a configured limit (e.g. > 10,000,000 VND) or destination account not previously used by this customer.",
        "hitl_model": "human-in-the-loop",
        "context_needed": "Correlation/request ID, customer ID, source and destination account, amount, currency, agent's proposed confirmation message, and the raw user request that triggered the transfer.",
        "example": "Customer asks the assistant to 'transfer 50,000,000 VND to account 0123456789'. The agent drafts a transfer confirmation but a human reviewer must approve before the transfer is actually executed.",
        "approval_path": "Reviewer can Approve (transfer proceeds, egress gated by is_egress_allowed), Reject (transfer cancelled, customer notified with reason), or Timeout after N minutes (auto-reject and escalate to a supervisor queue; transfer never auto-sends on timeout).",
        "audit_fields": "correlation_id, request_id, customer_id, action='transfer_money', proposed_diff (before/after balances or payload), reviewer_id, decision (approve/reject/timeout), decision_timestamp, reason.",
    },
    {
        "id": 2,
        "name": "Sensitive account change (password / personal info update)",
        "trigger": "action_type in {'change_password', 'update_personal_info', 'close_account', 'delete_data'} — any request that mutates account credentials or PII.",
        "hitl_model": "human-in-the-loop",
        "context_needed": "Customer ID, field(s) being changed with old vs new value diff, channel/session metadata (IP, device if available), and recent account activity for anomaly context.",
        "example": "Customer requests 'change my registered phone number to 0987654321'. Because this could be an account-takeover attempt, the change is queued for a human to confirm the customer's identity before the update is applied.",
        "approval_path": "Approve applies the change and notifies the customer via the original verified channel; Reject keeps old value and flags the session for fraud review; Timeout (e.g. 30 min) auto-rejects and requires the customer to re-initiate the request.",
        "audit_fields": "correlation_id, request_id, customer_id, action, field_diff (old_value/new_value, redacted if secret), reviewer_id, decision, decision_timestamp, escalation_reason.",
    },
    {
        "id": 3,
        "name": "Low-confidence or guardrail-ambiguous response",
        "trigger": "ConfidenceRouter.route() returns action in {'queue_review', 'escalate'} for a non-high-risk action — i.e. confidence < 0.9, or the output guardrail/LLM judge flags the response as borderline (e.g. content_filter found an issue but the judge marked it SAFE, a disagreement).",
        "hitl_model": "human-on-the-loop",
        "context_needed": "Original user question, agent's drafted response (pre- and post-redaction), guardrail verdicts (content_filter issues, judge verdict), and confidence score.",
        "example": "A customer asks an ambiguous multi-part question mixing a benign banking query with an off-topic remark; the judge is unsure whether the drafted answer leaks internal details, so it is queued for a reviewer to approve, edit, or reject before being sent.",
        "approval_path": "Approve sends the response as-is; Reject discards it and the agent responds with a generic fallback; Timeout (e.g. 5 min, since this is lower risk than money movement) auto-sends a safe fallback message rather than the drafted response, and logs the timeout for later audit.",
        "audit_fields": "correlation_id, request_id, customer_id, confidence, guardrail_issues, judge_verdict, reviewer_id, decision, decision_timestamp.",
    },
]


# ============================================================
# Quick tests
# ============================================================

def test_confidence_router():
    """Test ConfidenceRouter with sample scenarios."""
    router = ConfidenceRouter()

    test_cases = [
        ("Balance inquiry", 0.95, "general"),
        ("Interest rate question", 0.82, "general"),
        ("Ambiguous request", 0.55, "general"),
        ("Transfer $50,000", 0.98, "transfer_money"),
        ("Close my account", 0.91, "close_account"),
    ]

    print("Testing ConfidenceRouter:")
    print("=" * 80)
    print(f"{'Scenario':<25} {'Conf':<6} {'Action Type':<18} {'Decision':<15} {'Priority':<10} {'Human?'}")
    print("-" * 80)

    for scenario, conf, action_type in test_cases:
        decision = router.route(scenario, conf, action_type)
        print(
            f"{scenario:<25} {conf:<6.2f} {action_type:<18} "
            f"{decision.action:<15} {decision.priority:<10} "
            f"{'Yes' if decision.requires_human else 'No'}"
        )

    print("=" * 80)


def test_hitl_points():
    """Display HITL decision points."""
    print("\nHITL Decision Points:")
    print("=" * 60)
    for point in hitl_decision_points:
        print(f"\n  Decision Point #{point['id']}: {point['name']}")
        print(f"    Trigger:  {point['trigger']}")
        print(f"    Model:    {point['hitl_model']}")
        print(f"    Context:  {point['context_needed']}")
        print(f"    Example:  {point['example']}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_confidence_router()
    test_hitl_points()
