# Project Setup & Authentication

This guide covers the initial configuration required to start using TRXO with your Ping Identity environments.

## 1. Project Initialization
TRXO uses "Projects" to organize configurations for different tenant migrations or environments.

```bash
# Create a new project workspace
trxo project create my-ping-migration

# Switch to the project
trxo project switch my-ping-migration
```

## 2. Configuration Setup
Once inside a project, run the setup wizard to configure your Storage Mode and Authentication.

```bash
trxo config setup
```
Follow the prompts to select:
*   **Storage**: Local Filesystem or Git Repository (See [Storage Setup Guide](storage_setup.md)).
*   **Authentication**: Service Account (Cloud) or On-Premise.

---

## 3. Authentication Methods

TRXO supports secure authentication for both **PingOne Advanced Identity Cloud** and **PingAM/PingIDM**.

### PingOne Advanced Identity Cloud
Authenticates using a Service Account.

**Setup in Config (Interactive):**
```bash
trxo config setup
# Default to 'service-account' mode
# Provide path to JWK file and Service Account ID
```

**CLI Argument (CI/CD / One-off):**
```bash
trxo config setup --jwk-path /path/to/private.key \
  --client-id service-account-client-id \
  --sa-id service-account-uuid \
  --base-url https://<tenant>.forgeblocks.com
```

### PingAM / PingIDM (On-Premise)
Authenticates using Username/Password.

**Setup in Config (Interactive):**
```bash
trxo config setup --auth-mode onprem
# Provide Base URL (e.g., https://am.example.com or https://am.example.com/am)
# Provide Username and Password
```

**CLI Argument (CI/CD / One-off):**
```bash
trxo config setup --auth-mode onprem \
  --base-url https://am.example.com/am \
  --onprem-username amAdmin \
  --onprem-password SecurityPhrase1! 
```

---

## Token Management
TRXO handles token lifecycle automatically.
- **Auto-Refresh**: Tokens are refreshed if they expire during long operations.
- **Scopes**: Ensure your Service Account has required scopes (e.g., `fr:am:*`, `fr:idm:*`,`fr:idc:esv:*`).

For more information on required scopes, see [Service Account Token Lifetime and Scopes](service-account-token-lifetime-and-scopes.md).
