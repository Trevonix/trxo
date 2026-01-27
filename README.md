# TRXO: Ping Identity Configuration Management

**Manage, compare, and deploy Ping configurations—safely and consistently.**

---

### Why TRXO?

*   **Manual console changes are risky** — one wrong redirect URL, script version, or policy can break production.
*   **Ping environments are complex** — managing PingOne Advanced Identity Cloud, PingAM, and PingIDM separately leads to drift and inconsistency.
*   **No visibility before change** — TRXO shows exactly what will change *before* you import, with clear diffs and reports.
*   **Consistency across environments** — Export once, validate in Git, and deploy the same configuration everywhere.
*   **Built for safe automation** — Git-backed storage, batch operations, and rollback reduce errors and deployment anxiety.
*   **Save time, prevent outages** — Fewer manual steps, faster changes, safer releases.

---

### Features

*   **Hybrid Migration**: Seamlessly move configurations between PingOne Advanced Identity Cloud, PingAM, and PingIDM.
*   **Intelligent Diff Summary**: Granular change analysis highlighting specific modifications in OAuth2 clients (Grant Types, Claims, Scopes) and Managed Object properties.
*   **Deep Managed Object Support**: Reliable migration of Managed Objects including schema properties and complex relationships, ensuring `repo.ds` configurations are correctly updated.
*   **Git-Backed Storage**: Native integration for version control, audit trails, and automated rollback capabilities.
*   **Selective Deployment**: Use **Cherry-Pick** to deploy specific items or **Sync Mode** to mirror source to target.
*   **Dependency Awareness**: Automatically identifies and exports dependent items.
*   **Comprehensive Logging**: Integrated logging with daily rotation and sensitive data masking. Use `trxo logs show` to monitor detailed workflows and API calls.

---

### Key Capabilities

#### 1. One Tool, Multiple Environments
Unified management for **PingOne Advanced Identity Cloud** (Service Account) and **PingAM / PingIDM** (On-Premise).
*   [Project Setup & Auth Guide](docs/setup_and_auth.md)

#### 2. Flexible Storage Modes
Manage configuration storage in **Local Filesystem** for ad-hoc tasks or **Git Repository** for collaboration and version control.
*   [Storage Setup Guide](docs/storage_setup.md)

#### 3. Deployment Safety
Deploy with confidence using powerful control features:
*   **Diff Preview**: See changes before applying.
*   **Rollback**: Optional auto-revert on failure (Git mode).
*   **Cherry-Pick**: Import single or multiple specific items.
*   **Sync**: Mirror source to target (removing orphans).
*   [Advanced Features Guide](docs/advanced_features.md)

#### 4. Batch & Automation
Migrate entire realms or specific configuration sets in a single operation. Designed for CI/CD pipelines.
*   [Batch Operations Guide](docs/batch_operations.md)

#### 5. Audit & Troubleshooting
Detailed tracking of every operation with privacy-focused data sanitization.
*   **Real-time Logs**: Monitor internal transitions and API calls as they happen.
*   **Log Management**: Easily view and filter logs using the `trxo logs` command group.

---

### 🚀 Installation

Quick start:

```bash
git clone https://github.com/techcanopysl/ping-aic-config-tool.git
cd ping-aic-config-tool
pip install -e .
```

For detailed requirements and development setup, see [Installation Guide](docs/installation.md).

### 📖 Usage

For command references, examples, and detailed workflows, refer to the [Usage Guide](docs/usage.md).

---

### 🛡️ Community & Legal

*   [**Code of Conduct**](CODE_OF_CONDUCT.md): Our standards for a welcoming community.
*   [**Contributing**](CONTRIBUTING.md): Guidelines for submitting improvements and bug fixes.
*   [**Security**](SECURITY.md): How to report security vulnerabilities.
*   [**License**](LICENSE): This project is licensed under the MIT License.
