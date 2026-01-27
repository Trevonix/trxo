# TRXO Installation Guide

This guide describes how to install the **TRXO** CLI tool.

## Prerequisites

- **Python 3.8** or higher
- **pip** (Python package installer)
- Access to a **PingOne Advanced Identity Cloud** tenant or **PingAM** instance.

## Installation Methods

### Method 1: Install from Source (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/techcanopysl/ping-aic-config-tool.git
   cd ping-aic-config-tool
   ```

2. Install the package:
   ```bash
   pip install -e .
   ```

### Method 2: Development Setup

For contributors:

1. Clone and enter directory:
   ```bash
   git clone https://github.com/techcanopysl/ping-aic-config-tool.git
   cd ping-aic-config-tool
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Install with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Verify Installation

Check that the CLI is accessible:

```bash
trxo --help
```
