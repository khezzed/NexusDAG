import json
import pytest
from conftest import (
    gl_mock,
    u256,
    Address,
    DynArray,
    ADMIN_ADDR,
    RECIPIENT_A,
    STRANGER_ADDR,
    MockWebResponse,
    mock_web_responses,
    mock_llm_responses,
    UserError,
    _ReturnWrapper,
)
from contracts.nexus_dag import (
    NexusDag,
    NODE_TYPE_EVIDENCE,
    STATUS_REGISTERED,
    STATUS_ACTIVE,
    STATUS_REJECTED,
    PREDICATE_HOLDS,
    PREDICATE_UNCLEAR,
    STATUS_EXTERNAL_NOT_FOUND,
    STATUS_EXTERNAL_ACCESS_DENIED,
    STATUS_EXTERNAL_REDIRECT,
    STATUS_EXTERNAL_OVERSIZED,
    STATUS_TRANSIENT_HTTP,
    STATUS_LLM_MALFORMED,
    STATUS_LLM_UNVERIFIED_CITATION,
)


def setup_test_contract():
    gl_mock.message.sender_address = ADMIN_ADDR
    allowed = DynArray(["raw.githubusercontent.com"])
    return NexusDag(allowed)


def test_adversarial_leader_forged_citation_rejected_by_validator():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/evidence.json"
    body = b'{"verdict": "Real evidence payload text is verified completely."}'
    mock_web_responses[url] = MockWebResponse(status=200, body=body)

    contract.register_node(
        node_id="NODE-ADV",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    # Legitimate validator expectation
    mock_llm_responses.append(lambda p: json.dumps({
        "predicate": "HOLDS",
        "citation": "Real evidence payload text is verified completely.",
    }))

    # Adversarial test: override run_nondet_unsafe to simulate an adversarial leader
    # returning a forged envelope with same headline predicate ("HOLDS") but altered citation
    def adversarial_run_nondet(leader_fn, validator_fn):
        honest_env = leader_fn()
        forged_env = dict(honest_env)
        forged_env["citation"] = "Forged citation that leader claims"
        # Submit forged calldata to validator
        wrapped = _ReturnWrapper(forged_env)
        accepted = validator_fn(wrapped)
        if not accepted:
            raise UserError("CONSENSUS_VALIDATION_FAILED: Validator rejected leader envelope.")
        return forged_env

    orig_run = gl_mock.vm.run_nondet_unsafe
    gl_mock.vm.run_nondet_unsafe = adversarial_run_nondet

    try:
        with pytest.raises(UserError, match="CONSENSUS_VALIDATION_FAILED"):
            contract.evaluate_node("NODE-ADV")
    finally:
        gl_mock.vm.run_nondet_unsafe = orig_run


def test_http_404_maps_to_rejected_unclear():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/missing.json"
    mock_web_responses[url] = MockWebResponse(status=404, body=b"404 Not Found")

    contract.register_node(
        node_id="NODE-404",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    contract.evaluate_node("NODE-404")
    node = contract.get_node("NODE-404")
    assert node["status"] == int(STATUS_REJECTED)
    assert node["envelope_status_code"] == STATUS_EXTERNAL_NOT_FOUND
    assert node["envelope_predicate"] == PREDICATE_UNCLEAR


def test_http_403_access_denied_maps_to_rejected():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/forbidden.json"
    mock_web_responses[url] = MockWebResponse(status=403, body=b"403 Forbidden")

    contract.register_node(
        node_id="NODE-403",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    contract.evaluate_node("NODE-403")
    node = contract.get_node("NODE-403")
    assert node["status"] == int(STATUS_REJECTED)
    assert node["envelope_status_code"] == STATUS_EXTERNAL_ACCESS_DENIED


def test_http_302_redirect_disallowed():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/redirect.json"
    mock_web_responses[url] = MockWebResponse(status=302, body=b"Moved Temporarily")

    contract.register_node(
        node_id="NODE-302",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    contract.evaluate_node("NODE-302")
    node = contract.get_node("NODE-302")
    assert node["status"] == int(STATUS_REJECTED)
    assert node["envelope_status_code"] == STATUS_EXTERNAL_REDIRECT


def test_oversized_payload_rejected():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/oversized.json"
    # Max payload bytes is 32768; provide 40000 bytes
    mock_web_responses[url] = MockWebResponse(status=200, body=b"x" * 40000)

    contract.register_node(
        node_id="NODE-OVERSIZED",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    contract.evaluate_node("NODE-OVERSIZED")
    node = contract.get_node("NODE-OVERSIZED")
    assert node["status"] == int(STATUS_REJECTED)
    assert node["envelope_status_code"] == STATUS_EXTERNAL_OVERSIZED


def test_invalid_utf8_payload_rejected():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/bad_utf8.bin"
    # Invalid UTF-8 sequence
    mock_web_responses[url] = MockWebResponse(status=200, body=b"\x80\x81\x82" * 20)

    contract.register_node(
        node_id="NODE-UTF8",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    contract.evaluate_node("NODE-UTF8")
    node = contract.get_node("NODE-UTF8")
    assert node["status"] == int(STATUS_REJECTED)
    assert node["envelope_status_code"] == STATUS_LLM_MALFORMED


def test_unverified_citation_rejected():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/grounding.json"
    body = b'{"verdict": "This text contains actual verified claims."}'
    mock_web_responses[url] = MockWebResponse(status=200, body=body)

    contract.register_node(
        node_id="NODE-GROUND",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    # LLM hallucinates a citation not present in the payload
    mock_llm_responses.append(lambda p: json.dumps({
        "predicate": "HOLDS",
        "citation": "Completely hallucinated citation not in text",
    }))

    contract.evaluate_node("NODE-GROUND")
    node = contract.get_node("NODE-GROUND")
    assert node["status"] == int(STATUS_REJECTED)
    assert node["envelope_status_code"] == STATUS_LLM_UNVERIFIED_CITATION


def test_duplicate_url_replay_prevented():
    contract = setup_test_contract()
    url = "https://raw.githubusercontent.com/org/repo/v1.0.0/single_use.json"
    mock_web_responses[url] = MockWebResponse(status=200, body=b'{"verdict": "valid content"}')

    contract.register_node(
        node_id="NODE-FIRST",
        node_type=NODE_TYPE_EVIDENCE,
        dependencies=DynArray([]),
        evidence_url=url,
        required_subject="Audit",
        allocated_wei=u256(0),
        recipient=RECIPIENT_A,
    )

    with pytest.raises(UserError, match="EXPECTED:DUPLICATE_EVIDENCE_URL"):
        contract.register_node(
            node_id="NODE-SECOND",
            node_type=NODE_TYPE_EVIDENCE,
            dependencies=DynArray([]),
            evidence_url=url,
            required_subject="Audit",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )


def test_unauthorized_domain_prevented():
    contract = setup_test_contract()
    with pytest.raises(UserError, match="EXPECTED:DOMAIN_NOT_ALLOWED"):
        contract.register_node(
            node_id="NODE-ROGUE-DOMAIN",
            node_type=NODE_TYPE_EVIDENCE,
            dependencies=DynArray([]),
            evidence_url="https://malicious-site.com/fake.json",
            required_subject="Audit",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )


def test_non_payable_methods_revert_on_attached_value():
    contract = setup_test_contract()
    gl_mock.message.value = u256(100)
    with pytest.raises(UserError, match="EXPECTED:NON_PAYABLE_METHOD"):
        contract.register_node(
            node_id="NODE-REVERT-VAL",
            node_type=NODE_TYPE_EVIDENCE,
            dependencies=DynArray([]),
            evidence_url="https://raw.githubusercontent.com/org/repo/v1.0.0/valid.json",
            required_subject="Audit",
            allocated_wei=u256(0),
            recipient=RECIPIENT_A,
        )
