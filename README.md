# NexusDAG — Evidence-Grounded Dependency Propagation & Retraction Graph

**NexusDAG** (`contracts/nexus_dag.py`) is an original **GenLayer Intelligent Contract** primitive that introduces autonomous, multi-validator qualitative evidence adjudication over a Directed Acyclic Graph (DAG) with **selective upstream retraction propagation and subtree invalidation**.

---

## 1. Executive Summary & The 150-Point Reusable Mechanism

In decentralized governance, supply chain financing, and multi-auditor protocol security, operations depend on hierarchical chains of qualitative assertions (e.g. security audits, reserve attestations, regulatory compliance certifications). Traditional smart contracts cannot inspect or interpret qualitative external evidence, while existing GenLayer submissions typically rely on flat classification templates (freeze items $\to$ LLM score $\to$ deadline).

**NexusDAG introduces a fundamentally distinct, reusable mechanism**:
1. **Dynamic Dependency Graph**: Actions and treasury releases depend on a topological graph of judged atoms. Leaf nodes represent external qualitative claims evaluated by GenVM validators; derived nodes represent operational allocations that require upstream dependencies to be active.
2. **Selective Upstream Retraction Propagation**: When an upstream certification or assertion is retracted (e.g., an audit firm issues an emergency CVE advisory), GenVM validators verify the retraction proof. Deterministic code immediately propagates invalidation down the reachable subgraph:
   - Target ancestor transitions to `STATUS_RETRACTED`.
   - All descendant nodes transition to `STATUS_CASCADE_BLOCKED`.
   - All allocated funds on affected paths are quarantined.
3. **The Graph Isolation Invariant**: Upstream invalidation strictly quarantines the affected causal path. **Disjoint independent branches remain 100% operational, active, and executable**. A failure in one domain does not poison unrelated operations.

---

## 2. Close-Match Comparison (Cohort Isolation)

| Dimension | Previous: `aegis-sla-escrow` | Previous: `genlayer-vulnerability-bounty` | **NexusDAG (This Primitive)** |
| :--- | :--- | :--- | :--- |
| **Architectural Shape** | SLA escrow with numerical P99/TTR telemetry threshold & carve-outs | Two-round contested challenge with counter-exploit collateral | **Topological DAG with selective upstream retraction propagation** |
| **Primary Judgment Made** | Did incident telemetry breach P99/TTR SLOs, and does maintenance excuse it? | Does patch resolve vulnerability, and does counter-exploit bypass it? | **Is an atomic claim valid, and does published retraction evidence refute it?** |
| **State Machine Across Interactions** | Collateral moves across 5 accounting buckets based on incident metrics | Created $\to$ Funded $\to$ Submitted $\to$ Challenged $\to$ Defended/Refuted | **Leaf evaluations unlock dependent subtrees; ancestor retraction cascade-blocks reachable paths while preserving disjoint branches** |
| **New Invariant Added** | 5-bucket conservation: $\Delta\text{In} - \Delta\text{Out} = \sum \text{Buckets}$ | Contested challenge stake penalty & 48h dispute timer | **Graph Isolation Invariant**: Revocation at node $U$ invalidates all paths $U \rightsquigarrow V$, while completely preserving disjoint branches $W \not\rightsquigarrow V$ |

---

## 3. Consensus Correctness & GenVM Equivalence

- **Strict Allowlist & Discrete Tokens**: The LLM never chooses outcomes, balances, or graph routes. It classifies bounded inputs into discrete tokens (`HOLDS`, `CONTRADICTED`, `UNCLEAR`).
- **Exact Multi-Field Envelope Consensus**: Validators independently fetch the HTTPS payload and compare all 8 fields in the consensus envelope (`leader_env[k] == val_env[k]`), requiring 100% exact equality.
- **Verbatim Grounded Citations**: All extracted citations must exist verbatim in the independently fetched payload text.
- **Fail-Closed Bounds**: HTTP non-200, redirects, empty bodies ($<32$ bytes), oversized bodies ($>32,768$ bytes), or non-UTF8 bytes immediately resolve to `UNCLEAR` and reject activation.
- **Storage Snapshotting**: All state is snapshotted into local variables prior to non-deterministic closures; zero references to `self` exist inside leader or validator closures.
- **Conservation of Funds**:
  $$\text{total\_inbound\_wei} - \text{total\_outbound\_wei} = \text{total\_treasury\_wei} + \text{total\_allocated\_wei} + \text{total\_quarantined\_wei}$$

---

## 4. Repository Structure

```text
nexus-dag-contract/
├── contracts/
│   └── nexus_dag.py                         # NexusDAG Intelligent Contract (Pinned GenVM v0.2.16)
├── tests/
│   ├── direct/
│   │   ├── conftest.py                      # In-memory deterministic GenVM mock harness
│   │   ├── test_dag_structure.py            # Cycle detection (DFS/BFS), multi-hop loops, bounds
│   │   ├── test_consensus_adversarial.py    # Adversarial leader, forged citation, replay, HTTP failures
│   │   └── test_retraction_propagation.py   # Selective cascade invalidation & independent branch isolation
│   └── integration/
├── fixtures/
│   └── evidence/
│       ├── audit_clean_leaf_a.json          # Pinned audit assertion fixture
│       ├── audit_cve_retraction_a.json      # Pinned CVE retraction advisory fixture
│       └── reserves_clean_leaf_d.json       # Pinned independent reserve attestation fixture
├── scripts/
│   └── deploy_and_demo_studionet.py         # End-to-end StudioNet deployment & demonstration runner
├── gltest.config.yaml                       # GenLayer test runner configuration
├── pyproject.toml                           # Project metadata & pytest configuration
├── requirements.txt                         # Pinned dependencies
├── release_manifest.json                    # Full machine-readable release verification
└── README.md                                # Architectural documentation
```

---

## 5. Verification & Quality Gates

Run all commands from the repository root with `.venv` active:

### 1. Official GenVM Linter & AST Validator
```bash
genvm-lint check contracts/nexus_dag.py --json
```
*Result: `{"ok": true, "lint": {"ok": true, "passed": 3}, "validate": {"ok": true, "contract": "NexusDag", "methods": 9}}`*

### 2. GenVM SDK Type Checker (Pyright)
```bash
genvm-lint typecheck contracts/nexus_dag.py
```
*Result: `✓ No type errors found`*

### 3. Direct-Mode Unit & Adversarial Test Suite (`pytest`)
```bash
pytest tests/direct/ -v
```
*Result: `19 passed in 0.07s`*

---

## 6. Live Testnet Deployment (GenLayer StudioNet)

- **Contract Address**: [`0x5C6D76942Ba7505E15cE3f9a21763137F89e76bF`](https://explorer-studio.genlayer.com/address/0x5C6D76942Ba7505E15cE3f9a21763137F89e76bF)
- **Deployed Commit**: [`2ab459d85bb48a69d84f139945d8f2c0b80218a1`](https://github.com/khezzed/NexusDAG/commit/2ab459d85bb48a69d84f139945d8f2c0b80218a1)
- **Git Blob SHA-1 (`contracts/nexus_dag.py`)**: `e62d2a1dcc36105d050d9d8940e45f48c766c4e6`
- **Release Manifest**: [`release_manifest.json`](release_manifest.json)

### Complete On-Chain Demonstration Transactions (`studionet`)

| Action | Transaction Hash | Status | Leader Result | Mechanism Verification / Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **Deploy Contract** | [`0xa0c5...08be`](https://explorer-studio.genlayer.com/transactions/0xa0c5b7097cf6128aabc23983b8c9f7ea7b50c1c89171e1a8cd01012198e908be) | `FINALIZED` | `SUCCESS` | Contract deployed with pinned runner |
| **Deposit Treasury** | [`0x0bd1...645a`](https://explorer-studio.genlayer.com/transactions/0x0bd13c19cac91561cec87a0c9e68fd80c66c8556aaaa1beef7b12add09ba645a) | `FINALIZED` | `SUCCESS` | Admin deposits 500 wei into unallocated treasury |
| **Register Node A** | [`0xbd32...54d4`](https://explorer-studio.genlayer.com/transactions/0xbd328d098c01cc438cdf6a896fbc67988ffaea238ea4dad7926dd3ff9ee354d4) | `FINALIZED` | `SUCCESS` | Leaf Node A (Audit Assertion) registered |
| **Register Node B** | [`0x50f3...198e`](https://explorer-studio.genlayer.com/transactions/0x50f32d5ec86ed94b14a4abd81268876f8de066c6a977a12ed024b169d165198e) | `FINALIZED` | `SUCCESS` | Derived Node B registered (depends on A) |
| **Register Node C** | [`0xec42...2f93`](https://explorer-studio.genlayer.com/transactions/0xec427e871790d7152fdde2060d5c48ac9a187275bf7de7380694dc3d4e062f93) | `FINALIZED` | `SUCCESS` | Derived Node C registered (depends on B, reserves 100 wei) |
| **Register Node D** | [`0x1f70...15d8`](https://explorer-studio.genlayer.com/transactions/0x1f70a16cab11c38ae881343416d769bc6da8f41f3e180ac6fd3eda90e621b5d8) | `FINALIZED` | `SUCCESS` | Independent Leaf Node D (Reserve Attestation) registered |
| **Register Node E** | [`0x80df...6d47`](https://explorer-studio.genlayer.com/transactions/0x80df044c8e6f52ed555e845a08f28caff67de1169211e6f0553c4a9412066d47) | `FINALIZED` | `SUCCESS` | Independent Derived Node E registered (depends on D, reserves 50 wei) |
| **Evaluate Node A** | [`0xa44b...37a0`](https://explorer-studio.genlayer.com/transactions/0xa44ba32b7b44c00b18535a3d2cc2f5da2426b39fdc352939e2cee1696dcc37a0) | `FINALIZED` | `SUCCESS` | GenVM validators fetch audit payload $\to$ `HOLDS` $\to$ Node A `ACTIVE` |
| **Evaluate Node B** | [`0x5b93...0ff6`](https://explorer-studio.genlayer.com/transactions/0x5b9335602ac3bf8d0014b9139262a22a8cb6a9538606e1649642182085a00ff6) | `FINALIZED` | `SUCCESS` | Dependency A active $\to$ Node B becomes `ACTIVE` |
| **Evaluate Node C** | [`0x8106...615a`](https://explorer-studio.genlayer.com/transactions/0x8106659c1b91cb5d8af0fbe8a232b864bebeeafc7901df702deb4c9c8ca0615a) | `FINALIZED` | `SUCCESS` | Dependency B active $\to$ Node C becomes `ACTIVE` (Executable) |
| **Evaluate Node D** | [`0x7b39...9cf4`](https://explorer-studio.genlayer.com/transactions/0x7b398c2d4c3b0f9a5f1c479da950f24c23b831bcf1c63f7156ba4a2798299cf4) | `FINALIZED` | `SUCCESS` | GenVM validators fetch reserve payload $\to$ `HOLDS` $\to$ Node D `ACTIVE` |
| **Evaluate Node E** | [`0x1ed6...b9e3`](https://explorer-studio.genlayer.com/transactions/0x1ed636bfd6d3a5280c946698a6d20e09d3e4acd4d9faed09c323466c3029b9e3) | `FINALIZED` | `SUCCESS` | Dependency D active $\to$ Node E becomes `ACTIVE` (Executable) |
| **Retract Node A** | [`0xd38d...4bf9`](https://explorer-studio.genlayer.com/transactions/0xd38dc37f476d4a8dd83dd38764a3b7180aaf36ea7099cba832e920372aef4bf9) | `FINALIZED` | `SUCCESS` | **150-Point Mechanism**: Verified CVE advisory invalidates Node A $\to$ Node A `RETRACTED`; Descendants B & C `CASCADE_BLOCKED`; 100 wei quarantined |
| **Execute Node E** | [`0xc953...cc85`](https://explorer-studio.genlayer.com/transactions/0xc9536f20c321ae022578b40e05b453ef96aa1e5c7ac682a53de6e0008416cc85) | `FINALIZED` | `SUCCESS` | **Graph Isolation Invariant**: Independent branch E is unaffected $\to$ 50 wei disbursed to recipient $\to$ `STATUS_EXECUTED` |
| **Guard 1: Blocked Node**| [`0x0158...01fd`](https://explorer-studio.genlayer.com/transactions/0x015822679db442ab82280bf6101f68ffb88683ed07a34819c34fd8c52ab601fd) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: `EXPECTED:NODE_CASCADE_BLOCKED` prevents execution on compromised path |
| **Guard 2: URL Replay** | [`0x0c52...c718`](https://explorer-studio.genlayer.com/transactions/0x0c522e3184014ada03c7dd5c4edf978d3ca6088ed62ce4af883593fcda50c718) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: `EXPECTED:DUPLICATE_EVIDENCE_URL` blocks duplicate evidence injection |
| **Guard 3: Rogue Domain**| [`0x7e61...196c`](https://explorer-studio.genlayer.com/transactions/0x7e61405891d6afe9a99b228dee96a5d0a28fe3779a366dd53ccd54feffb0196c) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: `EXPECTED:DOMAIN_NOT_ALLOWED` blocks unverified external origins |
| **Recover Quarantined** | [`0xd516...848b`](https://explorer-studio.genlayer.com/transactions/0xd5163b8d68beef4ed048eedd4d813f23c8c4ecaa5b120cbfbd800b1f36f6848b) | `FINALIZED` | `SUCCESS` | Admin refunds 100 quarantined wei back to unallocated treasury |

---

## 7. Portal Submission Note (< 1,000 Characters)

```text
NexusDAG implements autonomous multi-validator qualitative evidence adjudication over a Directed Acyclic Graph with selective upstream retraction propagation and subtree invalidation.

Unlike flat classification templates, operations and settlements depend on a topological graph of judged atoms. When an upstream certificate (Node A) is retracted via verified CVE advisory, GenVM validators verify the retraction proof and deterministic code cascade-blocks all reachable descendants (B and C) and quarantines allocated funds. Critically, the Graph Isolation Invariant guarantees that disjoint independent branches (D -> E) remain 100% active and executable, proving that upstream failure does not poison unrelated operations.

Demonstrated live on StudioNet (0x5C6D76942Ba7505E15cE3f9a21763137F89e76bF): Node E successfully settled while compromised Node C was blocked (EXPECTED:NODE_CASCADE_BLOCKED), with guards blocking duplicate evidence replay and unauthorized domains.
```
