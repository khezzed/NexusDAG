import pytest
from conftest import gl_mock, u256, Address, DynArray, ADMIN_ADDR, RECIPIENT_A, STRANGER_ADDR, UserError
from contracts.nexus_dag import (
    NexusDag,
    NODE_TYPE_EVIDENCE,
    NODE_TYPE_DERIVED,
    STATUS_REGISTERED,
    STATUS_ACTIVE,
)


def create_sample_dag():
    gl_mock.message.sender_address = ADMIN_ADDR
    allowed = DynArray(["raw.githubusercontent.com"])
    contract = NexusDag(allowed)
    return contract


def test_contract_initialization():
    contract = create_sample_dag()
    assert contract.admin == ADMIN_ADDR
    state = contract.get_accounting_state()
    assert state["total_treasury_wei"] == 0
    assert state["total_allocated_wei"] == 0
    assert state["total_quarantined_wei"] == 0
    assert state["total_paid_wei"] == 0
    assert state["node_count"] == 0


def test_register_leaf_node_success():
    contract = create_sample_dag()
    contract.register_node(
        node_id="NODE-ROOT-01",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/audit.json",
        required_subject="Security Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )
    node_data = contract.get_node("NODE-ROOT-01")
    assert node_data["node_id"] == "NODE-ROOT-01"
    assert node_data["status"] == int(STATUS_REGISTERED)
    assert len(node_data["dependencies"]) == 0


def test_register_duplicate_node_id_fails():
    contract = create_sample_dag()
    contract.register_node(
        node_id="NODE-01",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/audit1.json",
        required_subject="Audit 1",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )
    with pytest.raises(UserError, match="EXPECTED:DUPLICATE_NODE_ID"):
        contract.register_node(
            node_id="NODE-01",
            node_type=NODE_TYPE_EVIDENCE,
            dependencies=DynArray([]),
            evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/audit2.json",
            required_subject="Audit 2",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )


def test_register_unknown_dependency_fails():
    contract = create_sample_dag()
    with pytest.raises(UserError, match="EXPECTED:UNKNOWN_DEPENDENCY"):
        contract.register_node(
            node_id="NODE-CHILD",
            node_type=NODE_TYPE_DERIVED,
            dependencies=DynArray(["NODE-NONEXISTENT"]),
            evidence_url="",
            required_subject="",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )


def test_cycle_detection_self_dependency():
    contract = create_sample_dag()
    with pytest.raises(UserError, match="EXPECTED:UNKNOWN_DEPENDENCY"):
        contract.register_node(
            node_id="NODE-SELF",
            node_type=NODE_TYPE_DERIVED,
            dependencies=DynArray(["NODE-SELF"]),
            evidence_url="",
            required_subject="",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )


def test_cycle_detection_multi_hop():
    contract = create_sample_dag()
    # 1. Register A
    contract.register_node(
        node_id="NODE-A",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/a.json",
        required_subject="Sub A",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )
    # 2. Register B depending on A
    contract.register_node(
        node_id="NODE-B",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["NODE-A"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )
    # 3. Register C depending on B
    contract.register_node(
        node_id="NODE-C",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["NODE-B"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    # Now if another node tries to form a cycle or if an edge creates a loop
    # In DAG registration, adding a new node cannot point from an old node to a new node,
    # but the cycle check verifies reachability: if target_dep can reach start_node.
    # Here, start_node is NEW-NODE, target_dep is NODE-C. Can C reach NEW-NODE? No, because NEW-NODE didn't exist.
    # To test cycle detection on edge addition: if we ever had a cycle check:
    # Let's test the helper method directly as well:
    assert contract._check_cycle_exists("NODE-A", "NODE-C") is True  # C depends on B which depends on A
    assert contract._check_cycle_exists("NODE-C", "NODE-A") is False


def test_excessive_dependencies_rejection():
    contract = create_sample_dag()
    # Create 9 nodes
    for i in range(9):
        contract.register_node(
            node_id=f"ROOT-{i}",
            node_type=NODE_TYPE_EVIDENCE,
            dependencies=DynArray([]),
            evidence_url=f"https://raw.githubusercontent.com/org/repo/v1.0.0/{i}.json",
            required_subject=f"Sub {i}",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )

    # 9 dependencies exceeds MAX_DEPENDENCIES_PER_NODE = 8
    deps = DynArray([f"ROOT-{i}" for i in range(9)])
    with pytest.raises(UserError, match="EXPECTED:EXCEEDS_MAX_DEPENDENCIES"):
        contract.register_node(
            node_id="CHILD-OVERFLOW",
            node_type=NODE_TYPE_DERIVED,
            dependencies=deps,
            evidence_url="",
            required_subject="",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )


def test_evaluate_unready_dependency_blocked():
    contract = create_sample_dag()
    contract.register_node(
        node_id="PARENT",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/parent.json",
        required_subject="Parent Subject",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )
    contract.register_node(
        node_id="CHILD",
        node_type=NODE_TYPE_DERIVED,
        dependencies=DynArray(["PARENT"]),
        evidence_url="",
        required_subject="",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    # PARENT is only STATUS_REGISTERED, not STATUS_ACTIVE
    with pytest.raises(UserError, match="EXPECTED:DEPENDENCIES_NOT_ACTIVE"):
        contract.evaluate_node("CHILD")


def test_unauthorized_empty_dependency_derived_node_payout_attempt_blocked():
    """Steward Review Requirement (1):
    Untrusted callers cannot register an empty-dependency derived node or allocate/pay funds
    from the shared treasury without caller-owned deposits.
    """
    contract = create_sample_dag()
    # Admin deposits 500 wei into shared treasury
    gl_mock.message.sender_address = ADMIN_ADDR
    gl_mock.message.value = u256(500)
    contract.deposit_treasury()
    gl_mock.message.value = u256(0)

    # 1. Even Admin cannot register a derived node with empty dependencies
    with pytest.raises(UserError, match="EXPECTED:DERIVED_NODE_REQUIRES_DEPENDENCIES"):
        contract.register_node(
            node_id="EMPTY-DERIVED-ADMIN",
            node_type=NODE_TYPE_DERIVED,
            dependencies=DynArray([]),
            evidence_url="",
            required_subject="",
            allocated_wei=u256(100),
            recipient=RECIPIENT_A,
        )

    # 2. Untrusted stranger attempting an empty-dependency derived-node payout is rejected
    gl_mock.message.sender_address = STRANGER_ADDR
    with pytest.raises(UserError, match="EXPECTED:DERIVED_NODE_REQUIRES_DEPENDENCIES"):
        contract.register_node(
            node_id="EMPTY-DERIVED-ATTACK",
            node_type=NODE_TYPE_DERIVED,
            dependencies=DynArray([]),
            evidence_url="",
            required_subject="",
            allocated_wei=u256(500),
            recipient=STRANGER_ADDR,
        )

    # 3. Untrusted stranger attempting to allocate funds from shared treasury on a valid parent dependency
    gl_mock.message.sender_address = ADMIN_ADDR
    contract.register_node(
        node_id="VALID-ROOT",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/root.json",
        required_subject="Root",
        allocated_wei=u256(0),
        recipient=ADMIN_ADDR,
    )

    gl_mock.message.sender_address = STRANGER_ADDR
    with pytest.raises(UserError, match="EXPECTED:UNAUTHORIZED_TREASURY_ALLOCATION"):
        contract.register_node(
            node_id="STRANGER-DRAIN-ATTEMPT",
            node_type=NODE_TYPE_DERIVED,
            dependencies=DynArray(["VALID-ROOT"]),
            evidence_url="",
            required_subject="",
            allocated_wei=u256(500),
            recipient=STRANGER_ADDR,
        )

    # Verify treasury remains 100% intact (500 wei unallocated, 0 allocated, 0 paid)
    state = contract.get_accounting_state()
    assert state["total_treasury_wei"] == 500
    assert state["total_allocated_wei"] == 0
    assert state["total_paid_wei"] == 0

