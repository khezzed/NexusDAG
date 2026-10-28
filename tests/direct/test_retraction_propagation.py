import json
import pytest
from conftest import (
    gl_mock,
    u256,
    Address,
    DynArray,
    ADMIN_ADDR,
    RECIPIENT_A,
    RECIPIENT_B,
    STRANGER_ADDR,
    MockWebResponse,
    mock_web_responses,
    mock_llm_responses,
    mock_llm_dict,
    emitted_transfers,
    UserError,
)
from contracts.nexus_dag import (
    NexusDag,
    NODE_TYPE_EVIDENCE,
    NODE_TYPE_DERIVED,
    STATUS_REGISTERED,
    STATUS_ACTIVE,
    STATUS_RETRACTED,
    STATUS_CASCADE_BLOCKED,
    STATUS_EXECUTED,
    PREDICATE_HOLDS,
    PREDICATE_CONTRADICTED,
    STATUS_EVIDENCE_CONTRADICTED,
)


def setup_multi_branch_dag():
    gl_mock.message.sender_address = ADMIN_ADDR
    allowed = DynArray(["raw.githubusercontent.com"])
    contract = NexusDag(allowed)

    # Fund treasury with 500 wei
    gl_mock.message.value = u256(500)
    contract.deposit_treasury()
    gl_mock.message.value = u256(0)
    return contract


def test_selective_retraction_propagation_and_isolation():
    contract = setup_multi_branch_dag()

    # --- Setup Evidence Fixtures ---
    url_a = "https://raw.githubusercontent.com/org/repo/v1.0.0/audit_clean.json"
    url_d = "https://raw.githubusercontent.com/org/repo/v1.0.0/reserves_clean.json"
    url_retract_a = "https://raw.githubusercontent.com/org/repo/v1.0.0/advisory_cve_retraction.json"

    body_a = json.dumps({
        "report_id": "AUDIT-2026-01",
        "verdict": "Audited smart contracts show zero critical vulnerabilities and pass all invariants.",
    }).encode("utf-8")

    body_d = json.dumps({
        "attestation_id": "RES-2026-99",
        "verdict": "Total verifiable reserves exceed 120% of on-chain obligations.",
    }).encode("utf-8")

    body_retract_a = json.dumps({
        "advisory_id": "CVE-2026-RETRACT-01",
        "revocation": "Notice of immediate revocation: Critical reentrancy flaw discovered; prior audit certification is retracted.",
    }).encode("utf-8")

    mock_web_responses[url_a] = MockWebResponse(status=200, body=body_a)
    mock_web_responses[url_d] = MockWebResponse(status=200, body=body_d)
    mock_web_responses[url_retract_a] = MockWebResponse(status=200, body=body_retract_a)

    # --- Register Subtree 1: A -> B -> C (Allocated 100 wei) ---
    contract.register_node(
        node_id="NODE-A",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url_a,
        required_subject="Smart Contract Security Audit",
        allocated_wei=u256(0),
        recipient=ADMIN_ADDR,
    )
    contract.register_node(
        node_id="NODE-B",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["NODE-A"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(0),
        recipient=ADMIN_ADDR,
    )
    contract.register_node(
        node_id="NODE-C",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["NODE-B"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(100),
        recipient=RECIPIENT_A,
    )

    # --- Register Subtree 2 (Independent Branch): D -> E (Allocated 50 wei) ---
    contract.register_node(
        node_id="NODE-D",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url_d,
        required_subject="Reserve Attestation",
        allocated_wei=u256(0),
        recipient=ADMIN_ADDR,
    )
    contract.register_node(
        node_id="NODE-E",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["NODE-D"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(50),
        recipient=RECIPIENT_B,
    )

    # Verify initial accounting
    state = contract.get_accounting_state()
    assert state["total_treasury_wei"] == 350
    assert state["total_allocated_wei"] == 150
    assert state["total_quarantined_wei"] == 0

    # Configure mock responses keyed by prompt context
    mock_llm_dict["NODE-A"] = lambda prompt: json.dumps({
        "predicate": "HOLDS",
        "citation": "prior audit certification is retracted" if "RETRACTION" in prompt else "Audited smart contracts show zero critical vulnerabilities",
    })
    mock_llm_dict["NODE-D"] = lambda prompt: json.dumps({
        "predicate": "HOLDS",
        "citation": "Total verifiable reserves exceed 120%",
    })

    # --- Evaluate Subtree 1 ---
    res_a = contract.evaluate_node("NODE-A")
    assert res_a["predicate"] == PREDICATE_HOLDS
    assert contract.get_node("NODE-A")["status"] == int(STATUS_ACTIVE)

    # Evaluate Node B & C
    contract.evaluate_node("NODE-B")
    assert contract.get_node("NODE-B")["status"] == int(STATUS_ACTIVE)

    contract.evaluate_node("NODE-C")
    assert contract.get_node("NODE-C")["status"] == int(STATUS_ACTIVE)
    assert contract.is_node_executable("NODE-C") is True

    # --- Evaluate Subtree 2 (Independent Branch) ---
    res_d = contract.evaluate_node("NODE-D")
    assert res_d["predicate"] == PREDICATE_HOLDS
    assert contract.get_node("NODE-D")["status"] == int(STATUS_ACTIVE)

    contract.evaluate_node("NODE-E")
    assert contract.get_node("NODE-E")["status"] == int(STATUS_ACTIVE)
    assert contract.is_node_executable("NODE-E") is True

    # --- Retract Node A (Upstream of B and C) ---
    res_retract = contract.retract_node("NODE-A", url_retract_a)
    assert res_retract["predicate"] == PREDICATE_HOLDS

    # --- Assert Cascade Invalidation on Subtree 1 ---
    node_a = contract.get_node("NODE-A")
    assert node_a["status"] == int(STATUS_RETRACTED)

    node_b = contract.get_node("NODE-B")
    assert node_b["status"] == int(STATUS_CASCADE_BLOCKED)

    node_c = contract.get_node("NODE-C")
    assert node_c["status"] == int(STATUS_CASCADE_BLOCKED)
    assert contract.is_node_executable("NODE-C") is False

    # Attempting to execute blocked Node C must fail
    with pytest.raises(UserError, match="EXPECTED:NODE_CASCADE_BLOCKED"):
        contract.execute_node_action("NODE-C")

    # Accounting check: Node C's 100 wei should have moved from allocated to quarantined
    state_after_retract = contract.get_accounting_state()
    assert state_after_retract["total_allocated_wei"] == 50  # Node E still allocated
    assert state_after_retract["total_quarantined_wei"] == 100
    assert state_after_retract["total_treasury_wei"] == 350

    # --- Assert CRITICAL INVARIANT: Subtree 2 (Independent Branch) Remains Untouched ---
    node_d = contract.get_node("NODE-D")
    assert node_d["status"] == int(STATUS_ACTIVE)

    node_e = contract.get_node("NODE-E")
    assert node_e["status"] == int(STATUS_ACTIVE)
    assert contract.is_node_executable("NODE-E") is True

    # Execute Node E action successfully!
    payout_e = contract.execute_node_action("NODE-E")
    assert payout_e == 50
    assert contract.get_node("NODE-E")["status"] == int(STATUS_EXECUTED)
    assert len(emitted_transfers) == 1
    assert emitted_transfers[0].recipient == RECIPIENT_B
    assert emitted_transfers[0].value == 50

    # Final accounting check
    state_final = contract.get_accounting_state()
    assert state_final["total_paid_wei"] == 50
    assert state_final["total_allocated_wei"] == 0
    assert state_final["total_quarantined_wei"] == 100
    assert state_final["total_treasury_wei"] == 350

    # Admin refunds quarantined funds back to treasury
    contract.refund_quarantined_to_treasury("NODE-C")
    state_refunded = contract.get_accounting_state()
    assert state_refunded["total_quarantined_wei"] == 0
    assert state_refunded["total_treasury_wei"] == 450


def test_contradicted_retraction_evidence_leaves_node_and_funds_unchanged():
    """Steward Review Requirement (2):
    Retract a node ONLY when the agreed evidence affirmatively proves retraction (HOLDS);
    a CONTRADICTED result must leave the node and funds completely unchanged.
    """
    contract = setup_multi_branch_dag()

    url_a = "https://raw.githubusercontent.com/org/repo/v1.0.0/audit_clean_1.json"
    url_false_retract = "https://raw.githubusercontent.com/org/repo/v1.0.0/audit_reaffirmation.json"

    body_a = json.dumps({
        "report_id": "AUDIT-2026-01",
        "verdict": "Audited smart contracts show zero critical vulnerabilities and pass all invariants.",
    }).encode("utf-8")

    body_reaffirm = json.dumps({
        "advisory_id": "AUDIT-REAFFIRM-2026-02",
        "verdict": "Prior audit certification remains completely valid and is NOT retracted or compromised.",
    }).encode("utf-8")

    mock_web_responses[url_a] = MockWebResponse(status=200, body=body_a)
    mock_web_responses[url_false_retract] = MockWebResponse(status=200, body=body_reaffirm)

    contract.register_node(
        node_id="NODE-A",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url_a,
        required_subject="Smart Contract Security Audit",
        allocated_wei=u256(0),
        recipient=ADMIN_ADDR,
    )
    contract.register_node(
        node_id="NODE-B",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["NODE-A"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(100),
        recipient=RECIPIENT_A,
    )

    mock_llm_dict["NODE-A"] = lambda prompt: json.dumps(
        {
            "predicate": "CONTRADICTED",
            "citation": "Prior audit certification remains completely valid and is NOT retracted",
        }
        if "RETRACTION" in prompt
        else {
            "predicate": "HOLDS",
            "citation": "Audited smart contracts show zero critical vulnerabilities",
        }
    )

    # Activate NODE-A and NODE-B
    contract.evaluate_node("NODE-A")
    contract.evaluate_node("NODE-B")
    assert contract.get_node("NODE-A")["status"] == int(STATUS_ACTIVE)
    assert contract.get_node("NODE-B")["status"] == int(STATUS_ACTIVE)

    # Submit retraction evidence that evaluates to CONTRADICTED
    res_retract = contract.retract_node("NODE-A", url_false_retract)
    assert res_retract["predicate"] == PREDICATE_CONTRADICTED
    assert res_retract["status_code"] == STATUS_EVIDENCE_CONTRADICTED

    # Verify NODE-A and descendant NODE-B remain STATUS_ACTIVE (unchanged)
    node_a = contract.get_node("NODE-A")
    assert node_a["status"] == int(STATUS_ACTIVE)
    assert node_a["retraction_predicate"] == PREDICATE_CONTRADICTED

    node_b = contract.get_node("NODE-B")
    assert node_b["status"] == int(STATUS_ACTIVE)
    assert contract.is_node_executable("NODE-B") is True

    # Verify funds remain in allocated pool (not quarantined) and NODE-B can still execute payout
    acct = contract.get_accounting_state()
    assert acct["total_allocated_wei"] == 100
    assert acct["total_quarantined_wei"] == 0
    assert acct["total_treasury_wei"] == 400

