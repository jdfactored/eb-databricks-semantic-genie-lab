"""
Checks for 04-genie-ontology-and-genie-one.

Genie Ontology is in Public Preview and Genie One depends on account and workspace settings, so
each Genie One check accepts either evidence that the step worked or a recorded, explained
`availability='unavailable'` observation. Curation is always checkable, because it is applied to
Unity Catalog objects you own.
"""

from helpers import genie_agents, ground_truth, observations, ontology, utils

EX = "04"


def _unavailable_ok(row, step: str) -> bool:
    if row is not None and row.availability == "unavailable":
        assert len((row.notes or "").strip()) >= 20, (
            f"{step}: you recorded 'unavailable'. Say what you saw (error, missing menu, banner) in notes, so "
            f"your instructor can tell a disabled feature from a missed step.")
        return True
    return False


def test_ontology_inspection_recorded(**kwargs):
    row = observations.get(EX, "inspect_ontology", question_key="revenue_definition")
    assert row is not None, "Record what Genie cited in Step 2 (observations.record('04', 'inspect_ontology', ...))."
    if not _unavailable_ok(row, "inspect_ontology"):
        assert len((row.sources_cited or "").strip()) >= 5, (
            "List the sources Genie cited (click the citation icons in the answer) in sources_cited.")


def test_curation_applied(**kwargs):
    status = ontology.curation_status()
    assert any(status.values()), (
        f"No curation signal found: {status}. Do at least one of Step 3: certify the metric view, deprecate "
        f"the legacy summary with the governed tag, or (no grant needed) run ontology.annotate_legacy_summary().")


def test_genie_one_answer_is_governed(**kwargs):
    row = observations.get(EX, "genie_one_answer", question_key="revenue_90d")
    assert row is not None, "Record Genie One's answer to the revenue question in Step 4."
    if _unavailable_ok(row, "genie_one_answer"):
        return
    expected = ground_truth.net_revenue(90)
    if not ground_truth.close(row.answer_value, expected):
        what = next((label for label, v in ground_truth.revenue_candidates(90).items()
                     if ground_truth.close(row.answer_value, v)), "an unknown definition")
        raise AssertionError(
            f"Genie One answered {row.answer_value:,.2f}, which is {what}; governed net revenue is "
            f"{expected:,.2f}. The ontology preferred another source. Strengthen the curation (Step 3), wait a "
            f"few minutes for re-indexing, open a NEW chat and ask again.")


def test_genie_one_action_landed(**kwargs):
    row = observations.get(EX, "genie_one_action")
    if _unavailable_ok(row, "genie_one_action"):
        return
    sid = genie_agents.registered_id("metric_view_agent")
    assert sid, "Your metric-view agent from Exercise 2 is not registered."
    text = genie_agents.text_instructions(genie_agents.config(sid))
    assert ontology.GENIE_ONE_MARKER.lower() in text.lower(), (
        f"Your agent's instructions do not contain '{ontology.GENIE_ONE_MARKER}'. Ask Genie One to add the "
        f"instruction from Step 4 and approve the change when it asks for confirmation.")
