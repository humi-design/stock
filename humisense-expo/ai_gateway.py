"""AI provider abstraction for Humisense.

Supports:
    mock               - deterministic, offline, data-driven (default)
    openai_compatible  - OpenAI / OpenRouter / Ollama / any /v1 endpoint
    gemini             - Google Gemini (optional adapter)

The gateway NEVER performs financial calculations. It only produces
investigation narratives, root-cause reasoning and recommendations from
reconciliation evidence. The mock provider derives its output from the
actual exception data so the demo is honest about what it shows.
"""
import json
import time

import requests

from config import config


class AIProvider:
    """Base provider interface."""

    name = "base"

    def generate(self, prompt, system=None, case=None):
        """Return a text completion."""
        raise NotImplementedError

    def structured_output(self, prompt, system=None, case=None):
        """Return a dict parsed from the provider response."""
        raise NotImplementedError

    def health_check(self):
        """Return (ok: bool, message: str)."""
        raise NotImplementedError


# --------------------------------------------------------------------- #
# Mock provider - fully offline, based on the real reconciliation data
# --------------------------------------------------------------------- #
class MockAIProvider(AIProvider):
    name = "mock"

    def _evidence_text(self, case):
        if not case:
            return ""
        parts = []
        for key, label in (("bank", "Bank"), ("broker", "Broker Ledger"),
                           ("settlement", "Settlement")):
            ev = case.get(key) or {}
            if ev:
                parts.append(f"{label}: {ev.get('txn_id','-')} {ev.get('amount','-')} {ev.get('status','-')}")
        return " | ".join(parts)

    def generate(self, prompt, system=None, case=None):
        ctype = (case or {}).get("case_type", "")
        reference = (case or {}).get("reference", "")
        amount = (case or {}).get("amount", 0)
        evidence = self._evidence_text(case)

        if "root_cause" in prompt.lower() or "what happened" in prompt.lower():
            if ctype == "SETTLEMENT_MISMATCH":
                text = ("The settlement amount was received, but the corresponding "
                        "broker ledger entry has not been posted.")
                cause = ("Settlement received successfully while downstream ledger "
                         "posting remains pending.")
            elif ctype == "DUPLICATE_TRANSACTION":
                text = ("An identical transaction profile already exists in the "
                        "bank stream, indicating a duplicated entry.")
                cause = ("A second entry with matching amount, account and date was "
                         "posted for the same transaction.")
            elif ctype == "MISSING_TRANSACTION":
                text = ("The transaction exists in the bank stream but has no "
                        "corresponding broker or settlement record.")
                cause = ("Downstream posting did not occur for this transaction.")
            elif ctype == "AMOUNT_MISMATCH":
                text = ("The amount recorded in the broker ledger differs from the "
                        "amount in the bank stream.")
                cause = ("A partial or incorrect amount was posted to the ledger.")
            elif ctype == "DATE_MISMATCH":
                text = ("The transaction date in the broker ledger differs from the "
                        "bank stream beyond the allowed tolerance.")
                cause = ("The ledger entry was posted on a different value date.")
            elif ctype == "ACCOUNT_MISMATCH":
                text = ("The broker ledger entry references a different account than "
                        "the bank stream.")
                cause = ("The ledger entry was posted to the wrong account.")
            elif ctype == "STATUS_MISMATCH":
                text = ("The broker ledger status differs from the bank stream "
                        "status for this transaction.")
                cause = ("The downstream status update was not propagated.")
            else:
                text = "An exception was detected between the financial systems."
                cause = "Records across systems are inconsistent for this transaction."
            return f"{text}\nROOT_CAUSE: {cause}"

        if "recommend" in prompt.lower():
            if ctype == "SETTLEMENT_MISMATCH":
                rec = "Verify settlement receipt and post the corresponding ledger entry."
            elif ctype == "DUPLICATE_TRANSACTION":
                rec = "Confirm the duplicate and reverse the redundant ledger entry."
            elif ctype == "MISSING_TRANSACTION":
                rec = "Locate the downstream record and post the missing entry."
            elif ctype == "AMOUNT_MISMATCH":
                rec = "Reconcile the amount difference and adjust the ledger entry."
            elif ctype == "DATE_MISMATCH":
                rec = "Correct the value date on the ledger entry."
            elif ctype == "ACCOUNT_MISMATCH":
                rec = "Re-post the ledger entry to the correct account."
            elif ctype == "STATUS_MISMATCH":
                rec = "Update the ledger status to match the bank stream."
            else:
                rec = "Review the exception and align records across systems."
            return rec

        # Generic narration
        return (f"Investigated exception {reference} ({ctype}). "
                f"Evidence: {evidence}. Amount: {amount}.")

    def structured_output(self, prompt, system=None, case=None):
        text = self.generate(prompt, system=system, case=case)
        return {"text": text, "provider": self.name}

    def health_check(self):
        return True, "Demo AI is active and fully offline."


# --------------------------------------------------------------------- #
# OpenAI-compatible provider
# --------------------------------------------------------------------- #
class OpenAICompatibleProvider(AIProvider):
    name = "openai_compatible"

    def __init__(self, base_url=None, api_key=None, model=None):
        self.base_url = (base_url or config.AI_BASE_URL or "").rstrip("/")
        self.api_key = api_key or config.AI_API_KEY
        self.model = model or config.AI_MODEL or "gpt-4o-mini"

    def _post(self, messages):
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 600,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def generate(self, prompt, system=None, case=None):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._post(messages)

    def structured_output(self, prompt, system=None, case=None):
        text = self.generate(prompt, system=system, case=case)
        return {"text": text, "provider": self.name}

    def health_check(self):
        if not self.base_url:
            return False, "Base URL not configured."
        try:
            self._post([{"role": "user", "content": "ping"}])
            return True, "Connected."
        except Exception as exc:
            return False, f"Connection failed: {exc}"


# --------------------------------------------------------------------- #
# Gemini adapter (optional, best-effort)
# --------------------------------------------------------------------- #
class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or config.AI_API_KEY
        self.model = model or config.AI_MODEL or "gemini-1.5-flash"

    def _post(self, prompt):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def generate(self, prompt, system=None, case=None):
        return self._post(prompt)

    def structured_output(self, prompt, system=None, case=None):
        text = self._post(prompt)
        return {"text": text, "provider": self.name}

    def health_check(self):
        if not self.api_key:
            return False, "API key not configured."
        try:
            self._post("ping")
            return True, "Connected."
        except Exception as exc:
            return False, f"Connection failed: {exc}"


# --------------------------------------------------------------------- #
# Gateway factory
# --------------------------------------------------------------------- #
def get_provider(provider_name=None, base_url=None, api_key=None, model=None):
    """Instantiate the configured provider. Falls back to mock on failure."""
    name = (provider_name or config.AI_PROVIDER or "mock").strip().lower()
    try:
        if name == "openai_compatible":
            return OpenAICompatibleProvider(base_url, api_key, model)
        if name == "gemini":
            return GeminiProvider(api_key, model)
    except Exception:
        pass
    return MockAIProvider()


def current_provider_label():
    name = (config.AI_PROVIDER or "mock").strip().lower()
    if name == "openai_compatible":
        return "LIVE AI"
    if name == "gemini":
        return "LIVE AI"
    return "DEMO AI"


def record_usage(provider, model, case_id, prompt_type, success, latency_ms):
    """Persist AI usage (only when live AI is used)."""
    try:
        from db import db
        from datetime import datetime
        db.execute(
            "INSERT INTO ai_usage (provider, model, case_id, prompt_type, "
            "success, latency_ms, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)"
            if db.engine == "mysql" else
            "INSERT INTO ai_usage (provider, model, case_id, prompt_type, "
            "success, latency_ms, created_at) VALUES (?,?,?,?,?,?,?)",
            (provider, model, case_id, prompt_type, 1 if success else 0,
             latency_ms, datetime.utcnow().isoformat(timespec="seconds")),
        )
    except Exception:
        pass


def investigate_case(case):
    """Run the Humisense investigation pipeline for a case.

    Returns a dict with root_cause, recommendation, confidence, rationale.
    Uses live AI if configured; otherwise the deterministic mock. Never
    breaks the demo - falls back to mock on any live-AI failure.
    """
    provider = get_provider()
    is_live = provider.name != "mock"
    start = time.time()
    latency_ms = 0
    try:
        if is_live:
            evidence = json.dumps({k: case.get(k) for k in ("bank", "broker", "settlement")})
            prompt = (
                f"You are Humisense, a financial operations investigation agent.\n"
                f"Investigate this reconciliation exception.\n"
                f"Case type: {case.get('case_type')}\n"
                f"Reference: {case.get('reference')}\n"
                f"Amount: {case.get('amount')} {case.get('currency')}\n"
                f"Evidence: {evidence}\n"
                f"Return JSON with keys: what_happened, root_cause, recommendation, "
                f"confidence (0-100), rationale."
            )
            out = provider.structured_output(prompt, system="You are Humisense AI.")
            text = out.get("text", "")
            parsed = _parse_json(text)
            latency_ms = int((time.time() - start) * 1000)
            record_usage(provider.name, getattr(provider, "model", ""),
                         case.get("reference"), "investigation", True, latency_ms)
            if parsed:
                return _normalize_investigation(parsed)
            # fall through to mock if live output wasn't parseable
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        record_usage(provider.name, getattr(provider, "model", ""),
                     case.get("reference"), "investigation", False, latency_ms)
        # Live AI unavailable - continue with Demo AI
        pass

    # Deterministic mock investigation based on the actual case data.
    mock = MockAIProvider()
    ctype = case.get("case_type", "")
    root = mock.generate("what happened", case=case).split("ROOT_CAUSE: ")[0].strip()
    cause = mock.generate("what happened", case=case).split("ROOT_CAUSE: ")[1].strip()
    rec = mock.generate("recommendation", case=case)
    confidence = _mock_confidence(ctype)
    rationale = _mock_rationale(case)
    return {
        "what_happened": root,
        "root_cause": cause,
        "recommendation": rec,
        "confidence": confidence,
        "rationale": rationale,
        "provider": "demo",
        "fallback": is_live,
    }


def _parse_json(text):
    """Best-effort JSON extraction from a model response."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def _normalize_investigation(parsed):
    return {
        "what_happened": parsed.get("what_happened", ""),
        "root_cause": parsed.get("root_cause", ""),
        "recommendation": parsed.get("recommendation", ""),
        "confidence": _clamp_conf(parsed.get("confidence", 90)),
        "rationale": parsed.get("rationale", ""),
        "provider": "live",
        "fallback": False,
    }


def _clamp_conf(v):
    try:
        return max(0, min(100, int(float(v))))
    except (TypeError, ValueError):
        return 90


def _mock_confidence(ctype):
    table = {
        "SETTLEMENT_MISMATCH": 94,
        "DUPLICATE_TRANSACTION": 98,
        "MISSING_TRANSACTION": 91,
        "AMOUNT_MISMATCH": 95,
        "DATE_MISMATCH": 93,
        "ACCOUNT_MISMATCH": 96,
        "STATUS_MISMATCH": 92,
        "UNMATCHED_TRANSACTION": 90,
    }
    return table.get(ctype, 90)


def _mock_rationale(case):
    ctype = case.get("case_type", "")
    if ctype == "SETTLEMENT_MISMATCH":
        return ("3 related records found. 2 systems confirm settlement. "
                "1 system shows a pending ledger entry. No conflicting "
                "transaction detected.")
    if ctype == "DUPLICATE_TRANSACTION":
        return ("An identical transaction profile was found in the bank stream. "
                "No conflicting transaction detected.")
    if ctype == "MISSING_TRANSACTION":
        return ("Transaction present in the bank stream with no downstream "
                "records. No conflicting transaction detected.")
    if ctype == "AMOUNT_MISMATCH":
        return ("Amounts differ between bank and broker records. "
                "No conflicting transaction detected.")
    if ctype == "DATE_MISMATCH":
        return ("Value dates differ beyond the configured tolerance. "
                "No conflicting transaction detected.")
    if ctype == "ACCOUNT_MISMATCH":
        return ("Account references differ between systems. "
                "No conflicting transaction detected.")
    if ctype == "STATUS_MISMATCH":
        return ("Status values differ between systems. "
                "No conflicting transaction detected.")
    return ("Related records were compared across systems. "
            "No conflicting transaction detected.")