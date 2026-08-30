"""The assistant must be grounded in the same rules the engine applied.

This is the project's own bug class pointed at a new feature: a prompt that *says* it contains the
merchant's findings while containing none of them would produce confident answers about nothing,
and no existing test would notice. So these check what actually reaches the model, not what the
docstring claims reaches it.
"""
from __future__ import annotations

import pytest

from backend import knowledge
from backend.models.schemas import (
    ComplianceCheck,
    ComplianceResult,
    GapItem,
    ReadinessReport,
    ScoreComponent,
    Severity,
)
from backend.tools import assistant


def _report() -> ReadinessReport:
    return ReadinessReport(
        overall_score=41,
        grade="D",
        score_breakdown=[
            ScoreComponent(label="RBI Compliance", score=30, weight=0.40),
            ScoreComponent(label="PCI DSS", score=52, weight=0.20),
        ],
        critical_gaps=[GapItem(
            title="Missing: Refund Policy",
            description="Refund Policy not found or too thin",
            severity=Severity.CRITICAL,
            category="compliance",
            fix_suggestion="Add a Refund & Returns Policy page",
            source_url="https://shop.example.com/",
        )],
        warnings=[GapItem(
            title="PCI: CSP header missing (PCI 11.6.1)",
            description="CSP header missing (PCI 11.6.1)",
            severity=Severity.WARNING,
            category="pci",
            fix_suggestion="See PCI DSS v4.0.1 Requirement 11.6.1",
            source_url="https://shop.example.com/checkout",
        )],
        compliance_details=ComplianceResult(
            refund_policy=ComplianceCheck(name="Refund Policy", check_id="RBI-001", found=False),
        ),
        estimated_fix_time="1-2 days",
    )


class TestTheRuleDigestCoversTheKnowledgeBase:
    """A check the digest omits is a check the assistant cannot explain."""

    def test_every_declared_check_appears(self):
        digest = assistant.rule_digest()
        missing = sorted(cid for cid in assistant.known_check_ids() if cid not in digest)
        assert not missing, (
            f"the assistant is handed a rule digest that omits {missing}, so it cannot explain "
            "findings those checks produce"
        )

    def test_the_digest_carries_what_a_check_requires(self):
        digest = assistant.rule_digest()
        for check in knowledge.rbi_checks():
            assert check["name"] in digest, f"{check['id']} has no name in the digest"
        for check in knowledge.pci_checks():
            assert check["name"] in digest, f"{check['id']} has no name in the digest"

    def test_header_requirements_reach_the_digest(self):
        """PCI-005's four headers each declare a requirement, and a merchant will ask about them."""
        digest = assistant.rule_digest()
        for header in knowledge.pci_check("PCI-005")["scoring"]["headers"]:
            assert header["name"] in digest, f"{header['name']} missing from the digest"
            assert header["requirement"] in digest, (
                f"{header['name']} is in the digest without the requirement it declares"
            )


class TestThePromptActuallyContainsTheReport:
    """Grounding that is described but not included is the defect this project exists to avoid."""

    def test_the_merchants_findings_are_in_the_prompt(self):
        prompt = assistant.build_prompt("why did I fail?", _report())

        for expected in (
            "Missing: Refund Policy",
            "PCI: CSP header missing",
            "Add a Refund & Returns Policy page",
            "https://shop.example.com/checkout",
        ):
            assert expected in prompt, f"the prompt never contains {expected!r}"

    def test_the_score_and_grade_are_in_the_prompt(self):
        prompt = assistant.build_prompt("what is my score?", _report())
        assert "41" in prompt and "grade D" in prompt

    def test_the_rules_are_in_the_prompt(self):
        prompt = assistant.build_prompt("what is RBI-001?", _report())
        assert "RBI-001" in prompt and "PCI-004" in prompt

    def test_the_question_is_in_the_prompt(self):
        prompt = assistant.build_prompt("why is my CSP missing?", _report())
        assert "why is my CSP missing?" in prompt

    def test_history_is_replayed(self):
        prompt = assistant.build_prompt(
            "and how do I fix it?",
            _report(),
            history=[
                {"role": "user", "content": "what is my worst problem?"},
                {"role": "assistant", "content": "Your refund policy is missing."},
            ],
        )
        assert "what is my worst problem?" in prompt
        assert "Your refund policy is missing." in prompt

    def test_history_is_bounded(self):
        """An unbounded transcript would push the report out of the context window."""
        history = [{"role": "user", "content": f"question {i}"} for i in range(40)]
        prompt = assistant.build_prompt("latest", _report(), history=history)

        assert "question 39" in prompt, "the most recent turns were dropped"
        assert "question 0" not in prompt, "history is unbounded"

    def test_a_scan_less_session_says_so(self):
        prompt = assistant.build_prompt("what is PCI DSS?", None)
        assert "no scan open" in prompt


class TestCitationsAreReal:
    """The UI renders these as proof an answer is grounded, so an invented id must not survive."""

    def test_a_real_check_is_cited(self):
        assert assistant.cited_checks("This is your RBI-001 finding.") == ["RBI-001"]

    def test_an_invented_check_is_dropped(self):
        assert assistant.cited_checks("This is PCI-009, a rule I made up.") == []

    def test_mixed_real_and_invented(self):
        cited = assistant.cited_checks("See RBI-002 and PCI-999 for details.")
        assert cited == ["RBI-002"]

    def test_each_check_is_cited_once(self):
        cited = assistant.cited_checks("RBI-001 matters. As RBI-001 says, RBI-001 is critical.")
        assert cited == ["RBI-001"]

    def test_every_citation_is_a_check_the_engine_applies(self):
        answer = " ".join(sorted(assistant.known_check_ids()))
        assert set(assistant.cited_checks(answer)) == assistant.known_check_ids()


class TestNoCredentialIsSaidPlainly:
    """An apology rendered as an answer is worse than an honest refusal."""

    async def test_empty_completion_reports_unavailable(self, monkeypatch):
        async def silent(prompt, max_tokens=512):
            return ""

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", silent)
        result = await assistant.answer_question("why did I fail?", _report())

        assert result["available"] is False
        assert result["cited_checks"] == []
        assert "language model" in result["answer"]

    async def test_an_answer_reports_available(self, monkeypatch):
        async def replying(prompt, max_tokens=512):
            return "Your refund policy is missing, which is RBI-001."

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", replying)
        result = await assistant.answer_question("why did I fail?", _report())

        assert result["available"] is True
        assert result["cited_checks"] == ["RBI-001"]


class TestTheEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app

        with TestClient(create_app()) as c:
            yield c

    def test_a_blank_question_is_rejected(self, client):
        assert client.post("/api/assistant", json={"question": "   "}).status_code == 422

    def test_an_unknown_job_still_answers_generally(self, client, monkeypatch):
        async def replying(prompt, max_tokens=512):
            return "I have no scan for that id."

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", replying)
        response = client.post(
            "/api/assistant",
            json={"question": "what is my score?", "job_id": "does-not-exist"},
        )
        assert response.status_code == 200
        assert response.json()["available"] is True

    def test_the_response_carries_citations(self, client, monkeypatch):
        async def replying(prompt, max_tokens=512):
            return "That is RBI-003, terms and conditions."

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", replying)
        body = client.post("/api/assistant", json={"question": "what is T&C?"}).json()
        assert body["cited_checks"] == ["RBI-003"]


class TestMarkdownDoesNotReachThePanel:
    """The chat panel renders plain text, so markdown prints as literal asterisks.

    The prompt asks for plain prose. This project has been bitten once by treating an instruction
    to the model as enforcement: the policy generator asked for placeholders to be replaced and
    shipped raw {{COMPANY_NAME}} when the model ignored it. So it is asked for and also done.
    """

    def test_bold_is_flattened(self):
        assert assistant.strip_markdown("a **bold** word") == "a bold word"
        assert assistant.strip_markdown("a __bold__ word") == "a bold word"

    def test_headings_are_flattened(self):
        assert assistant.strip_markdown("## Your score\nis 41") == "Your score\nis 41"

    def test_asterisk_bullets_become_hyphens(self):
        assert assistant.strip_markdown("* one\n* two") == "- one\n- two"

    def test_plain_text_is_untouched(self):
        text = "Your refund policy is missing, which is RBI-001. Add one."
        assert assistant.strip_markdown(text) == text

    def test_check_ids_survive_stripping(self):
        """The citation badge depends on the id surviving, and bold wraps them constantly."""
        stripped = assistant.strip_markdown("that is **PCI-004** and **RBI-001**")
        assert assistant.cited_checks(stripped) == ["PCI-004", "RBI-001"]

    async def test_the_answer_returned_is_stripped(self, monkeypatch):
        async def bold(prompt, max_tokens=512):
            return "Your **refund policy** is missing (**RBI-001**)."

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", bold)
        result = await assistant.answer_question("why?", _report())

        assert "**" not in result["answer"], result["answer"]
        assert result["cited_checks"] == ["RBI-001"]

    def test_the_prompt_asks_for_plain_prose(self):
        """Both halves must be present: the ask, and the enforcement above."""
        assert "No markdown" in assistant.build_prompt("q", None)


class TestProviderFailuresAreAnswersNotCrashes:
    """An expired credential is the most likely failure in practice, and it 500'd.

    `available` existed to say what happened, and only covered the provider returning an empty
    string. An exception propagated out of the endpoint, so the merchant saw a generic error and
    nobody could tell an expired key from a network problem without reading server logs.
    """

    async def _fails_with(self, monkeypatch, error: Exception) -> dict:
        async def raising(prompt, max_tokens=512):
            raise error

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", raising)
        return await assistant.answer_question("why did I fail?", _report())

    async def test_an_expired_credential_is_reported_plainly(self, monkeypatch):
        class AuthenticationError(Exception):
            pass

        result = await self._fails_with(monkeypatch, AuthenticationError("401 token expired"))

        assert result["available"] is False
        assert "expired" in result["answer"], result["answer"]
        assert result["cited_checks"] == []

    async def test_an_unreachable_endpoint_says_so(self, monkeypatch):
        class APIConnectionError(Exception):
            pass

        result = await self._fails_with(monkeypatch, APIConnectionError("no route"))
        assert "could not be reached" in result["answer"], result["answer"]

    async def test_an_unknown_failure_still_answers(self, monkeypatch):
        result = await self._fails_with(monkeypatch, ValueError("something odd"))
        assert result["available"] is False
        assert "ValueError" in result["answer"]

    async def test_the_answer_says_the_report_still_works(self, monkeypatch):
        """The merchant must not think their report is affected."""
        class AuthenticationError(Exception):
            pass

        result = await self._fails_with(monkeypatch, AuthenticationError("401"))
        assert "report was produced without one" in result["answer"]

    def test_the_endpoint_returns_200_not_500(self, monkeypatch):
        from fastapi.testclient import TestClient

        from backend.main import create_app

        class AuthenticationError(Exception):
            pass

        async def raising(prompt, max_tokens=512):
            raise AuthenticationError("401 token expired")

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", raising)
        with TestClient(create_app()) as c:
            response = c.post("/api/assistant", json={"question": "what should I fix?"})

        assert response.status_code == 200, (
            "a provider failure reaches the merchant as a server error, so the UI can only "
            "show a generic message"
        )
        assert response.json()["available"] is False
