# Changelog

All notable changes to this repository are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Offline `make check` runs 26 pytest cases with mocked GitHub and a scripted
  chat model, including the reflector retry cap and notifier dry-run. Reflector
  output is labeled a model self-score. See `FAILURE_MODES.md`.
- README, PREREG, and the technical note no longer say the test directory is
  empty or that few-shot, LangSmith, tenacity retries, or pagination are
  implemented. There is no PyPI package.
- Governance baseline: LICENSE, security policy, code of conduct, contributor and
  support guides, issue and pull-request templates, CODEOWNERS, dependabot, and
  `.editorconfig` added. No research content changed.
