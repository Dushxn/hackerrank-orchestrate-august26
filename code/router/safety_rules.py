"""Hard scam / phishing / safety override rules.

These rules run before any trust or personalization scoring. When one fires,
it hard-overrides the routing decision to `mute` regardless of sender
reputation or the user's usual engagement -- matching the spec's requirement
that "clear scam or safety risk should be muted regardless of the user's
usual engagement."

Detection is deliberately pattern-based (not proximity-fragile regex chains)
so it stays auditable and easy to extend: split the message into sentences,
look for a *combination* of signals within a sentence (credential term +
an action verb asking for it), and separately check whole-message
pressure+verify combos and business sending-domain mismatches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# --- vocabulary ---------------------------------------------------------

_CREDENTIAL_TERM = re.compile(
    r"\b(?:otp|pin|cvv|password|passcode|verification code|login code|"
    r"card number|bank details|account number)\b",
    re.I,
)
_ASK_VERB = re.compile(
    r"\b(?:share|enter|reply with|send|confirm|provide|verify with|type|upload|give)\b",
    re.I,
)
_PRESSURE_TERM = re.compile(
    r"\b(?:blocked|suspend(?:ed)?|expire[sd]?|deactivat\w*|frozen|locked|"
    r"will be closed|temporarily blocked)\b",
    re.I,
)
_VERIFY_VERB = re.compile(r"\b(?:verify|confirm|re-?validate|re-?activate)\b", re.I)

_NEGATION_GUARD = re.compile(
    r"\b(?:do not|don't|never|please don't|avoid)\s+(?:share|enter|send|give|provide)\b",
    re.I,
)

_FEE_LURE = re.compile(
    r"\b(?:pay|reattempt|redelivery|release)\b[^.!\n]{0,40}\b(?:fee|charge)\b|"
    r"\bfee\b[^.!\n]{0,40}\b(?:release|redeliver|reattempt)\b",
    re.I,
)

_PRIZE_LURE = re.compile(
    r"\b(?:you'?ve won|winner|lottery|lucky draw|claim your prize|free gift)\b",
    re.I,
)

_PROMPT_INJECTION = re.compile(
    r"\b(?:ignore (?:all|any) (?:previous|prior) (?:instructions|rules)|"
    r"disregard (?:the )?(?:above|previous)|"
    r"mark this (?:message )?as (?:notify|urgent|safe))\b",
    re.I,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class SafetyFinding:
    message_type: str  # 'scam' or 'spam'
    reason: str
    confidence: float


def check_text(text: str | None) -> SafetyFinding | None:
    """Run text-based safety rules. Returns the first/strongest match, or
    None if the text has no safety-critical signal.
    """
    if not text:
        return None

    # 1. Prompt-injection attempts embedded in the message must never change
    #    the routing decision -- and are themselves a strong signal that the
    #    message is malicious/manipulative.
    if _PROMPT_INJECTION.search(text):
        return SafetyFinding(
            message_type="scam",
            reason="The message attempts to manipulate the routing system's instructions rather than being a genuine notification.",
            confidence=0.95,
        )

    # 2. Sentence-scoped credential request: a credential term and an action
    #    verb asking for it in the same sentence, unless that sentence is
    #    actually a warning telling the user NOT to share one.
    for sentence in _SENTENCE_SPLIT.split(text):
        if _NEGATION_GUARD.search(sentence):
            continue
        if _CREDENTIAL_TERM.search(sentence) and _ASK_VERB.search(sentence):
            return SafetyFinding(
                message_type="scam",
                reason="The message asks the user to share an OTP, PIN, password, or other credential, a common phishing pattern.",
                confidence=0.93,
            )

    # 3. Whole-message pressure + verify combo (e.g. "profile blocked ...
    #    verify now"), unless the message is a "don't share" warning.
    if not _NEGATION_GUARD.search(text):
        if _PRESSURE_TERM.search(text) and _VERIFY_VERB.search(text):
            return SafetyFinding(
                message_type="scam",
                reason="The message uses account-blocking or expiry pressure to push urgent verification, a common phishing tactic.",
                confidence=0.88,
            )

    # 4. Small-fee-to-release-package/refund lure.
    if _FEE_LURE.search(text):
        return SafetyFinding(
            message_type="scam",
            reason="The message asks for a small fee to release a package or refund, a common delivery-scam pattern.",
            confidence=0.85,
        )

    # 5. Prize / lottery / too-good-to-be-true lure.
    if _PRIZE_LURE.search(text):
        return SafetyFinding(
            message_type="scam",
            reason="The message offers an unsolicited prize or cashback, a common scam lure.",
            confidence=0.8,
        )

    return None


def check_business_domain(business: dict | None) -> SafetyFinding | None:
    """Flags a business message where the sending domain doesn't match the
    business's official domain -- a strong phishing signal independent of
    message text (e.g. a lookalike domain impersonating a known brand).
    """
    if not business:
        return None
    official = (business.get("official_domain") or "").strip().lower()
    used = (business.get("domain_used_by_sender") or "").strip().lower()
    if not official or not used or official == used:
        return None

    verified = business.get("verified") == "1"
    try:
        domain_age = int(business.get("domain_used_by_sender_age_days") or 0)
    except ValueError:
        domain_age = 0

    if not verified and domain_age < 60:
        return SafetyFinding(
            message_type="scam",
            reason=(
                f"The sending domain ({used}) does not match this business's official domain "
                f"({official}) and was registered recently, consistent with a phishing lookalike."
            ),
            confidence=0.9,
        )
    return None


def evaluate(text: str | None, business: dict | None = None) -> SafetyFinding | None:
    """Combined entry point used by the decision engine: text rules take
    priority (they're specific to this message), domain mismatch is the
    fallback (it's a property of the sender, not the message content).
    """
    finding = check_text(text)
    if finding:
        return finding
    return check_business_domain(business)
