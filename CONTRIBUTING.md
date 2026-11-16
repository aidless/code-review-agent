# Contributing

Thanks for your interest in improving this repository.

## Getting set up

```bash
git clone https://github.com/aidless/code-review-agent.git
cd code-review-agent
pip install -r requirements.txt   # if present
```

## Verifying your change

```bash
make check
```

`make check` is the same offline path CI runs: install dependencies, pytest with a
coverage table for `agents`, `graph`, `tools`, and `api`, then `eval/run_cases.py`.
It does not need `GITHUB_TOKEN` or a model key. The coverage percentage is line
coverage of this prototype, not a review-quality score.

## Pull requests

- One logical change per pull request.
- Explain what breaks or is missing without the change.
- State how you verified it, and paste the command output.
- Keep unrelated reformatting out of the diff.

## Security

Do not open a public issue for a security problem. Use the private channel described
in [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
