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

- **Contract Address**: [`0x70dD62d9A2491B8fb66d9616C24A64c707C4B422`](https://explorer-studio.genlayer.com/address/0x70dD62d9A2491B8fb66d9616C24A64c707C4B422)
- **Deployed Commit**: [`2bf583a5e289e5f725711f21b06aa6f1cd8267b0`](https://github.com/khezzed/aegis-sla-escrow/commit/2bf583a5e289e5f725711f21b06aa6f1cd8267b0)
- **Git Blob SHA-1 (`contracts/nexus_dag.py`)**: `e62d2a1dcc36105d050d9d8940e45f48c766c4e6`
- **Release Manifest**: [`release_manifest.json`](release_manifest.json)

### Complete On-Chain Demonstration Transactions (`studionet`)

| Action | Transaction Hash | Status | Leader Result | Mechanism Verification / Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **Deploy Contract** | [`0x767e...2875`](https://explorer-studio.genlayer.com/transactions/0x767e0d22bf3766a1996b442546207f333201f2d8e13f94d21d957740dba12875) | `FINALIZED` | `SUCCESS` | Contract deployed with pinned runner |
| **Deposit Treasury** | [`0xdb03...400e`](https://explorer-studio.genlayer.com/transactions/0xdb034b10eb340b8ed709e4dd5bf86b96c20a381fef2011727f6c57506261400e) | `FINALIZED` | `SUCCESS` | Admin deposits 500 wei into unallocated treasury |
| **Register Node A** | [`0xa00f...87e4`](https://explorer-studio.genlayer.com/transactions/0xa00fd9c6f4d5afb6fd267f6f0f6ae3016c2e23c3bafc3f25b83b03c6ea2c87e4) | `FINALIZED` | `SUCCESS` | Leaf Node A (Audit Assertion) registered |
| **Register Node B** | [`0xdd8e...a47a`](https://explorer-studio.genlayer.com/transactions/0xdd8e27dfed43cd85367d9bcc800dab0de8f185cc7e6bacade69a262bd7a9a47a) | `FINALIZED` | `SUCCESS` | Derived Node B registered (depends on A) |
| **Register Node C** | [`0x3dd4...9825`](https://explorer-studio.genlayer.com/transactions/0x3dd4d310944f772d63d352cf9f4c71e62534c7c582beab754500e5d303f69825) | `FINALIZED` | `SUCCESS` | Derived Node C registered (depends on B, reserves 100 wei) |
| **Register Node D** | [`0x9223...44e0`](https://explorer-studio.genlayer.com/transactions/0x92231850853a2cf912f91812864779db733cbffdcc44e7e6b15e2172ad0544e0) | `FINALIZED` | `SUCCESS` | Independent Leaf Node D (Reserve Attestation) registered |
| **Register Node E** | [`0x8aad...4fb2`](https://explorer-studio.genlayer.com/transactions/0x8aadf4e5cc30d437c48e63fddfa348368ae51b8444c9ec62b2fd5e49fdfc4fb2) | `FINALIZED` | `SUCCESS` | Independent Derived Node E registered (depends on D, reserves 50 wei) |
| **Evaluate Node A** | [`0x9897...8b29`](https://explorer-studio.genlayer.com/transactions/0x9897b1a96008ecf7844d3f212fb0c0f0f77ddb3a7ccd0fb137001e29fdf18b29) | `FINALIZED` | `SUCCESS` | GenVM validators fetch audit payload $\to$ `HOLDS` $\to$ Node A `ACTIVE` |
| **Evaluate Node B** | [`0x3e39...7979`](https://explorer-studio.genlayer.com/transactions/0x3e39d3e2fcea538b8755c0d371950249c50746130aae7594a9f5fcc0984b7979) | `FINALIZED` | `SUCCESS` | Dependency A active $\to$ Node B becomes `ACTIVE` |
| **Evaluate Node C** | [`0x0985...8bde`](https://explorer-studio.genlayer.com/transactions/0x098514611fb6a0d6f32ace7cb55b05713a77bee25db26d7a379f04f8f2918bde) | `FINALIZED` | `SUCCESS` | Dependency B active $\to$ Node C becomes `ACTIVE` (Executable) |
| **Evaluate Node D** | [`0x42f7...e608`](https://explorer-studio.genlayer.com/transactions/0x42f718c050a933d97745594afe84cef4aeaaf657e8e98e1f3b0f787f036ee608) | `FINALIZED` | `SUCCESS` | GenVM validators fetch reserve payload $\to$ `HOLDS` $\to$ Node D `ACTIVE` |
| **Evaluate Node E** | [`0x2391...7c0a`](https://explorer-studio.genlayer.com/transactions/0x2391dbb85552cac366018db6a2ebf6500cd0ec7ce061027b44ecfba3d8087c0a) | `FINALIZED` | `SUCCESS` | Dependency D active $\to$ Node E becomes `ACTIVE` (Executable) |
| **Retract Node A** | [`0x5c8a...6d69`](https://explorer-studio.genlayer.com/transactions/0x5c8ab7c524603838b43d8ceecf18603cbc803d1a4871b4105ef058b387846d69) | `FINALIZED` | `SUCCESS` | **150-Point Mechanism**: Verified CVE advisory invalidates Node A $\to$ Node A `RETRACTED`; Descendants B & C `CASCADE_BLOCKED`; 100 wei quarantined |
| **Execute Node E** | [`0xdb07...fbe2`](https://explorer-studio.genlayer.com/transactions/0xdb07a50d05f9926d854b608cdf76c90fd8eb97b524e4e65c79700f34053ffbe2) | `FINALIZED` | `SUCCESS` | **Graph Isolation Invariant**: Independent branch E is unaffected $\to$ 50 wei disbursed to recipient $\to$ `STATUS_EXECUTED` |
| **Guard 1: Blocked Node**| [`0x800b...e733`](https://explorer-studio.genlayer.com/transactions/0x800b53d55093b8f73e1289c152aa900467c9847c41015a43749410b0ff78e733) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: `EXPECTED:NODE_CASCADE_BLOCKED` prevents execution on compromised path |
| **Guard 2: URL Replay** | [`0x708f...37b4`](https://explorer-studio.genlayer.com/transactions/0x708fdb82937733240b9f5cafcca2242097467d77c14daebed68e2eff1aae37b4) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: `EXPECTED:DUPLICATE_EVIDENCE_URL` blocks duplicate evidence injection |
| **Guard 3: Rogue Domain**| [`0xd1bc...86a0`](https://explorer-studio.genlayer.com/transactions/0xd1bc274810ca44ce33f9090e1df7a0f842415b67e726eb39e7ec4412538c86a0) | `FINALIZED` | `ERROR` | `EXPECTED FAILURE`: `EXPECTED:DOMAIN_NOT_ALLOWED` blocks unverified external origins |
| **Recover Quarantined** | [`0xf2b8...606d`](https://explorer-studio.genlayer.com/transactions/0xf2b801df23f993a48aabb5cde94eacd4971951a11b4dfdaef63d4aec114d606d) | `FINALIZED` | `SUCCESS` | Admin refunds 100 quarantined wei back to unallocated treasury |

---

## 7. Portal Submission Note (< 1,000 Characters)

```text
NexusDAG implements autonomous multi-validator qualitative evidence adjudication over a Directed Acyclic Graph with selective upstream retraction propagation and subtree invalidation.

Unlike flat classification templates, operations and settlements depend on a topological graph of judged atoms. When an upstream certificate (Node A) is retracted via verified CVE advisory, GenVM validators verify the retraction proof and deterministic code cascade-blocks all reachable descendants (B and C) and quarantines allocated funds. Critically, the Graph Isolation Invariant guarantees that disjoint independent branches (D -> E) remain 100% active and executable, proving that upstream failure does not poison unrelated operations.

Demonstrated live on StudioNet (0x70dD62d9A2491B8fb66d9616C24A64c707C4B422): Node E successfully settled while compromised Node C was blocked (EXPECTED:NODE_CASCADE_BLOCKED), with guards blocking duplicate evidence replay and unauthorized domains.
```
