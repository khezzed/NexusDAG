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
  - `NODE_TYPE_DERIVED` (2): Internal and terminal nodes representing operations that depend on one or more parent nodes. Derived nodes **must** declare at least one upstream dependency (`EXPECTED:DERIVED_NODE_REQUIRES_DEPENDENCIES`).
- **Topological Integrity**: When registering nodes, the contract performs cycle detection (DFS/BFS traversal). Self-dependencies and multi-hop cycles are rejected at registration time.
- **Execution Guard**: A derived node can only transition to `STATUS_ACTIVE` when all of its declared upstream dependencies have already achieved `STATUS_ACTIVE`. Terminal settlement execution (`execute_node_action`) is restricted to the contract admin, the node creator, or the designated recipient (`EXPECTED:UNAUTHORIZED_EXECUTION`).

### B. GenVM Multi-Validator Qualitative Evidence Adjudication
- **Discrete Allowlist Tokens**: LLMs are never permitted to directly decide financial balances, contract state, or graph routes. The LLM only classifies evidence into strictly bounded discrete tokens: `HOLDS`, `CONTRADICTED`, or `UNCLEAR`.
- **Verbatim Citation Grounding**: The validator verifies that any citation extracted by the LLM exists verbatim within the raw payload retrieved from the evidence URL.
- **Exact Multi-Field Consensus Envelope**: All validators independently execute the fetch and evaluation, producing an 8-field consensus envelope (`node_id`, `is_retraction`, `http_status`, `evidence_sha256`, `predicate`, `citation`, `status_code`, `adjudicated_at`). Full validator agreement requires 100% exact equality across every field.
- **Fail-Closed Principle**: If evidence is unreachable (HTTP non-200), redirected (HTTP 3xx), empty (< 32 bytes), oversized (> 32,768 bytes), or contains invalid UTF-8 bytes, the evaluation deterministically defaults to `UNCLEAR`, rejecting activation.

### C. Selective Upstream Retraction & Subtree Invalidation
When new evidence refutes a previously validated leaf (e.g. an emergency CVE advisory published by an auditor):
1. Any participant can submit the retraction advisory URL via `retract_node(node_id, retraction_url)`.
2. GenVM validators independently fetch and evaluate the revocation advisory (`HOLDS` = evidence affirmatively proves the certification is revoked/retracted; `CONTRADICTED` = evidence shows the certification remains valid/not retracted).
3. **Strict Affirmative Retraction Rule**:
   - Retraction occurs **only** when the agreed consensus envelope returns `predicate == "HOLDS"`.
   - If the consensus predicate is `"CONTRADICTED"` or `"UNCLEAR"`, the node remains `STATUS_ACTIVE` and all allocated and treasury funds remain completely unchanged.
   - Upon affirmative `HOLDS` consensus confirming revocation:
     - The root node transitions to `STATUS_RETRACTED`.
     - The contract deterministically traverses the transitive closure of all reachable downstream descendants, transitioning each to `STATUS_CASCADE_BLOCKED`.
     - Any funds allocated to affected nodes are automatically moved into a protected quarantined pool (`total_quarantined_wei`), preventing unauthorized disbursement.

### D. The Graph Isolation Invariant
Upstream invalidations are strictly bounded by reachability in the DAG. Formally:
$$\text{For any node } U \text{ retracted, only nodes } V \text{ where } U \rightsquigarrow V \text{ are blocked.}$$
$$\text{For any node } W \text{ such that } U \not\rightsquigarrow W, \text{ the operational status of } W \text{ is completely preserved.}$$

This invariant ensures that separate operational branches (e.g. treasury payouts backed by independent reserve attestations) continue functioning normally without cross-contamination.

### E. Deterministic Treasury Accounting & Caller-Bound Fund Safety
The contract enforces strict balance conservation and caller-owned deposit authorization across all operations:
$$\text{total\_inbound\_wei} - \text{total\_outbound\_wei} = \text{total\_treasury\_wei} + \text{total\_allocated\_wei} + \text{total\_quarantined\_wei}$$

- **Caller-Bound Deposit Tracking (`depositor_balances`)**: Every `deposit_treasury()` call credits `self.depositor_balances[sender]` alongside `total_treasury_wei`. A caller registering a node with `allocated_wei > 0` may only reserve up to their own unallocated deposit balance (`EXPECTED:UNAUTHORIZED_TREASURY_ALLOCATION`). Zero-allocation structural nodes may only be registered by `self.admin` (`EXPECTED:UNAUTHORIZED_NODE_REGISTRATION`).
- **Unallocated Treasury (`total_treasury_wei`)**: Liquid funds available for node reservation by their respective depositors.
- **Allocated Pool (`total_allocated_wei`)**: Funds reserved for active or pending settlement nodes. If a leaf node is rejected during evaluation, its allocation is refunded back to `total_treasury_wei` and restored to `depositor_balances[node.creator]`.
- **Quarantined Pool (`total_quarantined_wei`)**: Funds that were reserved on paths subsequently blocked by upstream retractions. The admin can refund quarantined funds back to the treasury (restoring `depositor_balances[node.creator]`) via `refund_quarantined_to_treasury(node_id)`.

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
*Output: `21 passed in 0.46s`*

The test suite covers:
- Adversarial leader proposing identical headline status with forged citation.
- HTTP 404, 403, 302 redirect rejection, oversized payloads, and invalid UTF-8 bytes.
- Duplicate URL replay prevention.
- Unauthorized external domain registration.
- Cycle detection across self-dependencies and multi-hop paths.
- Selective retraction propagation and independent branch execution.
- **Unauthorized empty-dependency derived-node payout prevention** (`test_unauthorized_empty_dependency_derived_node_payout_attempt_blocked`): proves derived nodes require upstream dependencies and untrusted callers cannot allocate or drain shared treasury funds (`depositor_balances` binding).
- **`CONTRADICTED` retraction evidence immunity** (`test_contradicted_retraction_evidence_leaves_node_and_funds_unchanged`): proves retraction occurs only on affirmative `HOLDS` consensus and that `CONTRADICTED` retraction evidence leaves the node `STATUS_ACTIVE` and all allocated/treasury funds unchanged.

---

## 7. Live Testnet Deployment (GenLayer StudioNet)

- **Network**: GenLayer StudioNet (`https://studio.genlayer.com/api`)
- **Contract Address**: [`0x11a877F15211054987932d9EAC55f1e7b9252656`](https://explorer-studio.genlayer.com/address/0x11a877F15211054987932d9EAC55f1e7b9252656)
- **Deployed Commit**: [`887d8eb70d7ccf724b0b32a59dd8cabb1484e61e`](https://github.com/khezzed/NexusDAG/commit/887d8eb70d7ccf724b0b32a59dd8cabb1484e61e)
- **Git Blob SHA-1 (`contracts/nexus_dag.py`)**: `a1d08449faeb3b15375c08e9fce71fd2c70d02bd`
- **Release Manifest**: [`release_manifest.json`](release_manifest.json)

### Complete On-Chain Transaction Walkthrough

The contract was demonstrated on StudioNet through a 20-step sequential scenario proving graph registration, multi-validator qualitative consensus, upstream retraction propagation, independent branch isolation, and defensive security guards:

| Step | Action | Transaction Hash | Status | Leader Execution | Verified On-Chain Behavior |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | **Deploy Contract** | [`0x3aab...a13d`](https://explorer-studio.genlayer.com/transactions/0x3aab1e7d3549b02a3f295e643700076e60e48034ec80dc83a9d8d35eec34a13d) | `FINALIZED` | `SUCCESS` | Pinned GenVM runner verified; contract instantiated at `0x11a877F15211054987932d9EAC55f1e7b9252656`. |
| **2** | **Deposit Treasury** | [`0xff2c...55e4`](https://explorer-studio.genlayer.com/transactions/0xff2c95c6030b1c4bc4c0052d987aaeae636e757cb0127d6fd5080e32da9c55e4) | `FINALIZED` | `SUCCESS` | Admin deposited 500 wei into treasury and credited `depositor_balances[admin]`. |
| **3** | **Register Node A** | [`0xd6a7...c60c`](https://explorer-studio.genlayer.com/transactions/0xd6a735cd2c33c554a0de28a4cd23939bb6d1e6bda09bd3a4699c01a1ca54c60c) | `FINALIZED` | `SUCCESS` | Leaf Node A registered with pinned audit report evidence URL. |
| **4** | **Register Node B** | [`0xb8e7...76be`](https://explorer-studio.genlayer.com/transactions/0xb8e75e9cd331e8568ad296d8850f2d4304204bf9352bf1109eb56d8b518576be) | `FINALIZED` | `SUCCESS` | Derived Node B registered with dependency on Node A. |
| **5** | **Register Node C** | [`0xaaea...3c77`](https://explorer-studio.genlayer.com/transactions/0xaaeace881216edf0932943fb2c6683636777a3430e90441bcf5286d1165f3c77) | `FINALIZED` | `SUCCESS` | Derived Node C registered (depends on B, reserves 100 wei from admin's deposit). |
| **6** | **Register Node D** | [`0x460a...7888`](https://explorer-studio.genlayer.com/transactions/0x460aa0d65eaae3763ede23f9f9fb7ebb75e19cd5c93770c6386b8b2880427888) | `FINALIZED` | `SUCCESS` | Independent Leaf Node D registered with reserve attestation evidence URL. |
| **7** | **Register Node E** | [`0x303b...9eac`](https://explorer-studio.genlayer.com/transactions/0x303b5eb936082debc24a95281e039f454cc8c38dc345df6c8e3a7dd5666a9eac) | `FINALIZED` | `SUCCESS` | Independent Derived Node E registered (depends on D, reserves 50 wei). |
| **8** | **Evaluate Node A** | [`0x6d37...db0d`](https://explorer-studio.genlayer.com/transactions/0x6d37aa3b8c4aeac2f622d02c4e2c6a4cfc7d10789057ad13c5639897a320db0d) | `FINALIZED` | `SUCCESS` | Validators independently fetch audit evidence $\to$ `HOLDS` $\to$ Node A becomes `ACTIVE`. |
| **9** | **Evaluate Node B** | [`0x2f2e...aa7b`](https://explorer-studio.genlayer.com/transactions/0x2f2ed7f33cd70fd41bdc94d861880671510bb7cd0a20b867598377cb298caa7b) | `FINALIZED` | `SUCCESS` | Upstream Node A is active $\to$ Derived Node B transitions to `ACTIVE`. |
| **10** | **Evaluate Node C** | [`0x4911...ae93`](https://explorer-studio.genlayer.com/transactions/0x491108faf177d2eb4d6382c084d8accc43c560989dc4085ef41da2194f04ae93) | `FINALIZED` | `SUCCESS` | Upstream Node B is active $\to$ Node C transitions to `ACTIVE` (executable). |
| **11** | **Evaluate Node D** | [`0xe317...8d81`](https://explorer-studio.genlayer.com/transactions/0xe317d6e5730385fed9328dbecb57f20ea2b59d17285ae58a577bff86d5318d81) | `FINALIZED` | `SUCCESS` | Validators fetch reserve evidence $\to$ `HOLDS` $\to$ Node D becomes `ACTIVE`. |
| **12** | **Evaluate Node E** | [`0x2f4d...6701`](https://explorer-studio.genlayer.com/transactions/0x2f4dec4ce29318a5b6c24dc56ed2029b6c2af86d453fc456aa0bad08bca116701) | `FINALIZED` | `SUCCESS` | Upstream Node D is active $\to$ Node E transitions to `ACTIVE` (executable). |
| **13** | **Retract Node A** | [`0x1e95...867e`](https://explorer-studio.genlayer.com/transactions/0x1e9540dd0a68bc83c477fbf463e344e2daf733d04e369666733fff197d79867e) | `FINALIZED` | `SUCCESS` | Verified CVE advisory (`predicate == HOLDS`) revokes Node A $\to$ Node A transitions to `RETRACTED`; descendants B and C cascade to `CASCADE_BLOCKED`; 100 wei moved to quarantined pool. |
| **14** | **Execute Node E** | [`0xad69...9f30`](https://explorer-studio.genlayer.com/transactions/0xad69b452e93583f1e25d836afd5f70c2b99d2c9f913424292e305a3f9a5e9f30) | `FINALIZED` | `SUCCESS` | **Graph Isolation Invariant**: Independent branch E is unaffected $\to$ 50 wei disbursed to recipient $\to$ Node E transitions to `STATUS_EXECUTED`. |
| **15** | **Guard: Blocked Node** | [`0x8d27...934e`](https://explorer-studio.genlayer.com/transactions/0x8d27a4823ce59aff9685142ed8174843c7d1f54ddb37873497bcce8f1550934e) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Calling `execute_node_action` on cascade-blocked Node C reverts with `EXPECTED:NODE_CASCADE_BLOCKED`. |
| **16** | **Guard: Replay Evidence** | [`0x5d34...20d0`](https://explorer-studio.genlayer.com/transactions/0x5d34c356e9bef6caa57ca7c07ed971a40c978e67059f74ba9810c0e36fb920d0) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Replaying already-evaluated evidence URL on a new node reverts with `EXPECTED:DUPLICATE_EVIDENCE_URL`. |
| **17** | **Guard: Rogue Domain** | [`0x2b04...8385`](https://explorer-studio.genlayer.com/transactions/0x2b04fffcf52d870cc01388ea58d750727f585a19d9a0d891ffa19687c12f8385) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Attempting to register an unapproved external domain reverts with `EXPECTED:DOMAIN_NOT_ALLOWED`. |
| **18** | **Guard: Empty-Dep Derived** | [`0xbce3...f458`](https://explorer-studio.genlayer.com/transactions/0xbce3096a89bcc5d392d9010658207ee55e9f40d057eec0da3aecb3b1c5a3f458) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Registering a derived node with empty dependencies reverts with `EXPECTED:DERIVED_NODE_REQUIRES_DEPENDENCIES`. |
| **19** | **Guard: Unauth Allocation** | [`0x4d9e...9a7d`](https://explorer-studio.genlayer.com/transactions/0x4d9ebea78d11f1696c8da5e70c6bdc73f9fe442128ea8da669b90805056d9a7d) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: Untrusted caller attempting to allocate from shared treasury without deposit balance reverts with `EXPECTED:UNAUTHORIZED_TREASURY_ALLOCATION`. |
| **20** | **Refund Quarantined** | [`0x7ada...baf8`](https://explorer-studio.genlayer.com/transactions/0x7adae03bb39e40c1799c81a1e890a46e47c051f7ebfde3678586ca5c6e58baf8) | `FINALIZED` | `SUCCESS` | Admin recovers 100 quarantined wei back into unallocated treasury; full conservation invariant verified. |

---

## 8. Security Invariants & Defensive Design

1. **Deterministic Equivalence Principle**: Validators independently query external URLs, extract citations, and agree on all envelope fields. Non-deterministic closure state is completely isolated from contract storage.
2. **Cycle & Empty-Dependency Prevention**: The DAG registration algorithm validates that derived nodes declare non-empty dependencies and that adding an edge cannot produce a cycle via depth-first and breadth-first search.
3. **Caller-Owned Deposit Binding**: Positive treasury allocations (`allocated_wei > 0`) are strictly bound to the caller's own unallocated deposit balance (`depositor_balances[sender]`), preventing untrusted callers from draining the shared treasury.
4. **Affirmative `HOLDS`-Only Retraction**: `retract_node` only invalidates a node and quarantines funds when the agreed validator consensus envelope returns `predicate == "HOLDS"`. A `"CONTRADICTED"` or `"UNCLEAR"` result leaves the node and funds unchanged.
5. **Payload Bounds & Timeouts**: Maximum evidence payload size is capped at 32 KB. Payloads smaller than 32 bytes or failing HTTP 200 checks fail closed.
6. **Conservation of Balances**: Total inbound wei equals the sum of unallocated treasury, active allocations, quarantined balances, and outbound disbursements at all times.
7. **Separation of Concerns**: Qualitative evaluation is performed strictly by GenVM validators; all state transitions, dependency checks, funds management, and graph traversals are executed deterministically in ordinary smart contract code.
