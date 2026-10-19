# NexusDAG — Evidence-Grounded Dependency Propagation & Retraction Graph

**NexusDAG** (`contracts/nexus_dag.py`) is a GenLayer Intelligent Contract primitive that introduces **autonomous multi-validator qualitative evidence adjudication over a Directed Acyclic Graph (DAG)** with **selective upstream retraction propagation and subtree invalidation**.

---

## 1. Overview & Problem Statement

In decentralized finance, protocol governance, and cross-organization operations, critical actions (such as treasury disbursements, collateral unlocks, or contract migrations) frequently depend on a chain of qualitative preconditions:
- Third-party smart contract security audits.
- Off-chain custodial reserve attestations.
- Regulatory and compliance filings.
- Operational sign-offs from independent assessors.

Traditional smart contracts cannot evaluate qualitative natural language evidence, forcing protocols to rely on centralized multisigs or trusted intermediaries. Furthermore, existing oracle systems evaluate claims in isolation; they lack the ability to model **causal dependency graphs** or automatically propagate the invalidation of an upstream root down dependent subtrees.

**NexusDAG solves this challenge by combining topological graph validation with GenVM multi-validator consensus:**
1. **Hierarchical DAG of Claims & Actions**: Dependencies are structured as a Directed Acyclic Graph. Leaf nodes ground qualitative claims fetched from verified HTTPS endpoints, while derived nodes represent downstream operational actions and treasury allocations.
2. **Autonomous Multi-Validator Evidence Adjudication**: GenVM validators independently fetch external evidence, evaluate qualitative claims using LLM-driven discrete token classification, verify verbatim citations, and agree on an exact multi-field consensus envelope.
3. **Selective Upstream Retraction Propagation**: If an upstream certification is revoked (e.g. an audit firm publishes an emergency CVE advisory), validators verify the retraction proof. The contract deterministically cascades invalidations down all reachable descendants, transitions them to a blocked state, and quarantines all associated treasury allocations.
4. **The Graph Isolation Invariant**: Upstream retraction strictly isolates the affected causal path. **Disjoint independent subgraphs remain active, operational, and executable**, guaranteeing that a vulnerability in one dependency does not stall unrelated protocol operations.

---

## 2. Core Architecture & Mechanisms

```
        Subtree 1 (Compromised Path)                     Subtree 2 (Independent Path)
  
   [ Node A: Security Audit ] (Leaf)                [ Node D: Reserve Attestation ] (Leaf)
               │                                                      │
               ▼                                                      ▼
   [ Node B: Protocol Approval ] (Derived)          [ Node E: Operational Settlement ] (Derived)
               │                                                      │
               ▼                                                      ▼
   [ Node C: Treasury Payout ] (Allocated)                 (Executed & Disbursed)
               │
   ─── Upstream Retraction ───
   Node A -> RETRACTED
   Node B -> CASCADE_BLOCKED
   Node C -> CASCADE_BLOCKED (Funds Quarantined)
```

### A. Directed Acyclic Graph Structure
- **Node Types**:
  - `NODE_TYPE_EVIDENCE` (1): Leaf nodes representing qualitative assertions grounded in external HTTPS evidence (e.g., audit reports, solvency attestations).
  - `NODE_TYPE_DERIVED` (2): Internal and terminal nodes representing operations that depend on one or more parent nodes.
- **Topological Integrity**: When registering nodes, the contract performs cycle detection (DFS/BFS traversal). Self-dependencies and multi-hop cycles are rejected at registration time.
- **Execution Guard**: A derived node can only transition to `STATUS_ACTIVE` when all of its declared upstream dependencies have already achieved `STATUS_ACTIVE`.

### B. GenVM Multi-Validator Qualitative Evidence Adjudication
- **Discrete Allowlist Tokens**: LLMs are never permitted to directly decide financial balances, contract state, or graph routes. The LLM only classifies evidence into strictly bounded discrete tokens: `HOLDS`, `CONTRADICTED`, or `UNCLEAR`.
- **Verbatim Citation Grounding**: The validator verifies that any citation extracted by the LLM exists verbatim within the raw payload retrieved from the evidence URL.
- **Exact Multi-Field Consensus Envelope**: All validators independently execute the fetch and evaluation, producing an 8-field consensus envelope (`node_id`, `is_retraction`, `http_status`, `evidence_sha256`, `predicate`, `citation`, `status_code`, `adjudicated_at`). Full validator agreement requires 100% exact equality across every field.
- **Fail-Closed Principle**: If evidence is unreachable (HTTP non-200), redirected (HTTP 3xx), empty (< 32 bytes), oversized (> 32,768 bytes), or contains invalid UTF-8 bytes, the evaluation deterministically defaults to `UNCLEAR`, rejecting activation.

### C. Selective Upstream Retraction & Subtree Invalidation
When new evidence refutes a previously validated leaf (e.g. an emergency CVE advisory published by an auditor):
1. Any participant can submit the retraction advisory URL via `retract_node(node_id, retraction_url)`.
2. GenVM validators independently fetch and evaluate the revocation advisory.
3. Upon consensus confirming revocation:
   - The root node transitions to `STATUS_RETRACTED`.
   - The contract deterministically traverses the transitive closure of all reachable downstream descendants, transitioning each to `STATUS_CASCADE_BLOCKED`.
   - Any funds allocated to affected nodes are automatically moved into a protected quarantined pool (`total_quarantined_wei`), preventing unauthorized disbursement.

### D. The Graph Isolation Invariant
Upstream invalidations are strictly bounded by reachability in the DAG. Formally:
$$\text{For any node } U \text{ retracted, only nodes } V \text{ where } U \rightsquigarrow V \text{ are blocked.}$$
$$\text{For any node } W \text{ such that } U \not\rightsquigarrow W, \text{ the operational status of } W \text{ is completely preserved.}$$

This invariant ensures that separate operational branches (e.g. treasury payouts backed by independent reserve attestations) continue functioning normally without cross-contamination.

### E. Deterministic Treasury Accounting & Fund Safety
The contract enforces strict balance conservation across all operations:
$$\text{total\_inbound\_wei} - \text{total\_outbound\_wei} = \text{total\_treasury\_wei} + \text{total\_allocated\_wei} + \text{total\_quarantined\_wei}$$

- **Unallocated Treasury (`total_treasury_wei`)**: Liquid funds available for node reservation.
- **Allocated Pool (`total_allocated_wei`)**: Funds reserved for active or pending settlement nodes.
- **Quarantined Pool (`total_quarantined_wei`)**: Funds that were reserved on paths subsequently blocked by upstream retractions. The admin can refund quarantined funds back to the treasury via `refund_quarantined_to_treasury(node_id)`.

---

## 3. Node Lifecycle & State Machine

```
              ┌───────────────┐
              │ STATUS_PENDING│ (0)
              └───────┬───────┘
                      │ evaluate_node()
                      ▼
              ┌───────────────┐
              │ STATUS_ACTIVE │ (1)
              └───┬───────┬───┘
                  │       │
    retract_node()│       │ execute_node_action()
                  ▼       ▼
    ┌──────────────────┐ ┌─────────────────┐
    │ STATUS_RETRACTED │ │ STATUS_EXECUTED │ (5)
    └─────────┬────────┘ └─────────────────┘
              │ (cascades to descendants)
              ▼
    ┌────────────────────────┐
    │ STATUS_CASCADE_BLOCKED │ (3)
    └────────────────────────┘
```

| Status ID | Status Name | Description |
| :---: | :--- | :--- |
| `0` | `STATUS_PENDING` | Node registered; awaiting evidence evaluation or upstream dependency activation. |
| `1` | `STATUS_ACTIVE` | Preconditions verified; derived actions are eligible for execution. |
| `2` | `STATUS_RETRACTED` | Leaf node explicitly revoked via verified retraction advisory. |
| `3` | `STATUS_CASCADE_BLOCKED` | Derived node blocked because one or more upstream ancestors were retracted. |
| `4` | `STATUS_REJECTED` | Initial evidence evaluation failed to prove the predicate claim. |
| `5` | `STATUS_EXECUTED` | Terminal node action executed; allocated funds disbursed to recipient. |

---

## 4. Contract Interface

### Write Methods
- `deposit_treasury()`: Deposits native wei into the unallocated treasury balance.
- `register_node(node_id: str, node_type: int, dependencies: list[str], evidence_url: str, predicate_claim: str, allocated_amount: int, recipient: str)`: Registers a new node, verifies domain allowlist, detects cycles, and reserves treasury funds if an allocation is requested.
- `evaluate_node(node_id: str)`: Dispatches multi-validator consensus to evaluate external evidence for leaf nodes, or verifies upstream readiness for derived nodes.
- `retract_node(node_id: str, retraction_url: str)`: Dispatches multi-validator consensus to verify retraction evidence against an active leaf node, and propagates cascade invalidation down all reachable descendants.
- `execute_node_action(node_id: str)`: Executes the terminal action on an active node and disburses allocated funds to the designated recipient. Reverts if the node is pending, retracted, or cascade-blocked.
- `refund_quarantined_to_treasury(node_id: str)`: Recovers funds from a cascade-blocked node back to the unallocated treasury (admin only).

### View Methods
- `get_node(node_id: str)`: Returns full metadata, status, dependencies, and evidence for a specific node.
- `get_accounting_state()`: Returns the current 5-bucket balance distribution across treasury, allocated, quarantined, inbound, and outbound wei.
- `is_node_executable(node_id: str)`: Returns boolean indicating whether a node is in `STATUS_ACTIVE` and ready for execution.

---

## 5. Repository Structure

```text
NexusDAG/
├── contracts/
│   └── nexus_dag.py                         # NexusDAG Intelligent Contract (Pinned GenVM runner)
├── tests/
│   ├── direct/
│   │   ├── conftest.py                      # Deterministic in-memory GenVM execution harness
│   │   ├── test_dag_structure.py            # Cycle detection (DFS/BFS), multi-hop loops, bounds
│   │   ├── test_consensus_adversarial.py    # Adversarial leader, forged citations, replay, HTTP errors
│   │   └── test_retraction_propagation.py   # Selective cascade invalidation & independent branch isolation
│   └── integration/
├── fixtures/
│   └── evidence/
│       ├── audit_clean_leaf_a.json          # Pinned leaf audit report fixture
│       ├── audit_cve_retraction_a.json      # Pinned CVE retraction advisory fixture
│       └── reserves_clean_leaf_d.json       # Pinned independent reserve attestation fixture
├── scripts/
│   └── deploy_and_demo_studionet.py         # End-to-end StudioNet deployment & demonstration runner
├── gltest.config.yaml                       # GenLayer test configuration
├── pyproject.toml                           # Python project configuration
├── requirements.txt                         # Pinned dependencies
├── release_manifest.json                    # Full machine-readable release verification
└── README.md                                # Project documentation
```

---

## 6. Local Testing & Verification

All validation tools run inside Python 3.11+:

### 1. GenVM Static Linter & AST Validator
```bash
genvm-lint check contracts/nexus_dag.py --json
```
*Output: `{"ok": true, "lint": {"ok": true, "passed": 3}, "validate": {"ok": true, "contract": "NexusDag", "methods": 9, "view_methods": 3, "write_methods": 6, "ctor_params": 1}}`*

### 2. GenVM Type Checker (Pyright)
```bash
genvm-lint typecheck contracts/nexus_dag.py
```
*Output: `✓ No type errors found`*

### 3. Direct-Mode Unit & Adversarial Test Suite
```bash
pytest tests/direct/ -v
```
*Output: `19 passed in 0.08s`*

The test suite covers:
- Adversarial leader proposing identical headline status with forged citation.
- HTTP 404, 403, 302 redirect rejection, oversized payloads, and invalid UTF-8 bytes.
- Duplicate URL replay prevention.
- Unauthorized external domain registration.
- Cycle detection across self-dependencies and multi-hop paths.
- Selective retraction propagation and independent branch execution.

---

## 7. Live Testnet Deployment (GenLayer StudioNet)

- **Network**: GenLayer StudioNet (`https://studio.genlayer.com/api`)
- **Contract Address**: [`0x5C6D76942Ba7505E15cE3f9a21763137F89e76bF`](https://explorer-studio.genlayer.com/address/0x5C6D76942Ba7505E15cE3f9a21763137F89e76bF)
- **Deployed Commit**: [`2ab459d85bb48a69d84f139945d8f2c0b80218a1`](https://github.com/khezzed/NexusDAG/commit/2ab459d85bb48a69d84f139945d8f2c0b80218a1)
- **Git Blob SHA-1 (`contracts/nexus_dag.py`)**: `e62d2a1dcc36105d050d9d8940e45f48c766c4e6`
- **Release Manifest**: [`release_manifest.json`](release_manifest.json)

### Complete On-Chain Transaction Walkthrough

The contract was demonstrated on StudioNet through an 18-step sequential scenario proving graph registration, multi-validator qualitative consensus, upstream retraction propagation, independent branch isolation, and defensive security guards:

| Step | Action | Transaction Hash | Status | Leader Execution | Verified On-Chain Behavior |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | **Deploy Contract** | [`0xa0c5...08be`](https://explorer-studio.genlayer.com/transactions/0xa0c5b7097cf6128aabc23983b8c9f7ea7b50c1c89171e1a8cd01012198e908be) | `FINALIZED` | `SUCCESS` | Pinned GenVM runner verified; contract instantiated. |
| **2** | **Deposit Treasury** | [`0x0bd1...645a`](https://explorer-studio.genlayer.com/transactions/0x0bd13c19cac91561cec87a0c9e68fd80c66c8556aaaa1beef7b12add09ba645a) | `FINALIZED` | `SUCCESS` | Deposited 500 wei into unallocated treasury balance. |
| **3** | **Register Node A** | [`0xbd32...54d4`](https://explorer-studio.genlayer.com/transactions/0xbd328d098c01cc438cdf6a896fbc67988ffaea238ea4dad7926dd3ff9ee354d4) | `FINALIZED` | `SUCCESS` | Leaf Node A registered with pinned audit report evidence URL. |
| **4** | **Register Node B** | [`0x50f3...198e`](https://explorer-studio.genlayer.com/transactions/0x50f32d5ec86ed94b14a4abd81268876f8de066c6a977a12ed024b169d165198e) | `FINALIZED` | `SUCCESS` | Derived Node B registered with dependency on Node A. |
| **5** | **Register Node C** | [`0xec42...2f93`](https://explorer-studio.genlayer.com/transactions/0xec427e871790d7152fdde2060d5c48ac9a187275bf7de7380694dc3d4e062f93) | `FINALIZED` | `SUCCESS` | Derived Node C registered (depends on B, reserves 100 wei from treasury). |
| **6** | **Register Node D** | [`0x1f70...15d8`](https://explorer-studio.genlayer.com/transactions/0x1f70a16cab11c38ae881343416d769bc6da8f41f3e180ac6fd3eda90e621b5d8) | `FINALIZED` | `SUCCESS` | Independent Leaf Node D registered with reserve attestation evidence URL. |
| **7** | **Register Node E** | [`0x80df...6d47`](https://explorer-studio.genlayer.com/transactions/0x80df044c8e6f52ed555e845a08f28caff67de1169211e6f0553c4a9412066d47) | `FINALIZED` | `SUCCESS` | Independent Derived Node E registered (depends on D, reserves 50 wei). |
| **8** | **Evaluate Node A** | [`0xa44b...37a0`](https://explorer-studio.genlayer.com/transactions/0xa44ba32b7b44c00b18535a3d2cc2f5da2426b39fdc352939e2cee1696dcc37a0) | `FINALIZED` | `SUCCESS` | Validators independently fetch audit evidence $\to$ `HOLDS` $\to$ Node A becomes `ACTIVE`. |
| **9** | **Evaluate Node B** | [`0x5b93...0ff6`](https://explorer-studio.genlayer.com/transactions/0x5b9335602ac3bf8d0014b9139262a22a8cb6a9538606e1649642182085a00ff6) | `FINALIZED` | `SUCCESS` | Upstream Node A is active $\to$ Derived Node B transitions to `ACTIVE`. |
| **10** | **Evaluate Node C** | [`0x8106...615a`](https://explorer-studio.genlayer.com/transactions/0x8106659c1b91cb5d8af0fbe8a232b864bebeeafc7901df702deb4c9c8ca0615a) | `FINALIZED` | `SUCCESS` | Upstream Node B is active $\to$ Node C transitions to `ACTIVE` (executable). |
| **11** | **Evaluate Node D** | [`0x7b39...9cf4`](https://explorer-studio.genlayer.com/transactions/0x7b398c2d4c3b0f9a5f1c479da950f24c23b831bcf1c63f7156ba4a2798299cf4) | `FINALIZED` | `SUCCESS` | Validators fetch reserve evidence $\to$ `HOLDS` $\to$ Node D becomes `ACTIVE`. |
| **12** | **Evaluate Node E** | [`0x1ed6...b9e3`](https://explorer-studio.genlayer.com/transactions/0x1ed636bfd6d3a5280c946698a6d20e09d3e4acd4d9faed09c323466c3029b9e3) | `FINALIZED` | `SUCCESS` | Upstream Node D is active $\to$ Node E transitions to `ACTIVE` (executable). |
| **13** | **Retract Node A** | [`0xd38d...4bf9`](https://explorer-studio.genlayer.com/transactions/0xd38dc37f476d4a8dd83dd38764a3b7180aaf36ea7099cba832e920372aef4bf9) | `FINALIZED` | `SUCCESS` | Verified CVE advisory revokes Node A $\to$ Node A transitions to `RETRACTED`; descendants B and C cascade to `CASCADE_BLOCKED`; 100 wei moved to quarantined pool. |
| **14** | **Execute Node E** | [`0xc953...cc85`](https://explorer-studio.genlayer.com/transactions/0xc9536f20c321ae022578b40e05b453ef96aa1e5c7ac682a53de6e0008416cc85) | `FINALIZED` | `SUCCESS` | **Graph Isolation Invariant**: Independent branch E is unaffected $\to$ 50 wei disbursed to recipient $\to$ Node E transitions to `STATUS_EXECUTED`. |
| **15** | **Guard: Blocked Node** | [`0x0158...01fd`](https://explorer-studio.genlayer.com/transactions/0x015822679db442ab82280bf6101f68ffb88683ed07a34819c34fd8c52ab601fd) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Calling `execute_node_action` on cascade-blocked Node C reverts with `EXPECTED:NODE_CASCADE_BLOCKED`. |
| **16** | **Guard: Replay Evidence** | [`0x0c52...c718`](https://explorer-studio.genlayer.com/transactions/0x0c522e3184014ada03c7dd5c4edf978d3ca6088ed62ce4af883593fcda50c718) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Replaying already-evaluated evidence URL on a new node reverts with `EXPECTED:DUPLICATE_EVIDENCE_URL`. |
| **17** | **Guard: Rogue Domain** | [`0x7e61...196c`](https://explorer-studio.genlayer.com/transactions/0x7e61405891d6afe9a99b228dee96a5d0a28fe3779a366dd53ccd54feffb0196c) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Attempting to register an unapproved external domain reverts with `EXPECTED:DOMAIN_NOT_ALLOWED`. |
| **18** | **Refund Quarantined** | [`0xd516...848b`](https://explorer-studio.genlayer.com/transactions/0xd5163b8d68beef4ed048eedd4d813f23c8c4ecaa5b120cbfbd800b1f36f6848b) | `FINALIZED` | `SUCCESS` | Admin recovers 100 quarantined wei back into unallocated treasury; full conservation invariant verified. |

---

## 8. Security Invariants & Defensive Design

1. **Deterministic Equivalence Principle**: Validators independently query external URLs, extract citations, and agree on all envelope fields. Non-deterministic closure state is completely isolated from contract storage.
2. **Cycle Prevention**: The DAG registration algorithm validates that adding an edge cannot produce a cycle via depth-first and breadth-first search.
3. **Payload Bounds & Timeouts**: Maximum evidence payload size is capped at 32 KB. Payloads smaller than 32 bytes or failing HTTP 200 checks fail closed.
4. **Conservation of Balances**: Total inbound wei equals the sum of unallocated treasury, active allocations, quarantined balances, and outbound disbursements at all times.
5. **Separation of Concerns**: Qualitative evaluation is performed strictly by GenVM validators; all state transitions, dependency checks, funds management, and graph traversals are executed deterministically in ordinary smart contract code.
