# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project follows Semantic Versioning.

---

## [Unreleased]

---

## [1.0.0] - 2026-03-30

### Added
- Extended sync functionality to support all configurations.
- Added support for **Application Import/Export** with full dependency resolution.
- Enabled dependency handling for **Policies** and related features.

### Changed
- Refactored codebase by moving API headers into a dedicated configuration module.
- Improved CLI options for better usability and flexibility.
- Enhanced rollback capability with improved handling of configuration dependencies.

### Improved
- Improved Git storage mode handling with better realm scope support.
- Optimized pipeline execution arguments for improved stability and performance.

### Fixed
- Updated batch operations documentation with missing methods for batch import.
- Corrected `CONTRIBUTING.md` with updated Python version requirements.

---

## [0.1.0] - 2026-03-11

### Added
- Integration support for Ping IDM configurations.
- Journey dependencies handling during export and import.
- Extended diff functionality for configuration comparison.
- Extended cherry-pick support across configurations.
- Unit tests for core modules and configuration operations.
- GitHub Pages website with Brevo form as a soft gateway.
- Extended rollback functionality for configuration management.

### Fixed
- CI/CD pipeline issues related to configuration migration.
- Theme import logic

---

## [0.0.1] - 2026-01-26
### Added
- Initial public release of TRXO.
- CLI for config, project, login, export, import, and batch commands.
- Documentation under docs/ (installation, usage, batch operations).