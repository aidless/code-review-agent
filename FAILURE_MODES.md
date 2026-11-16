# FAILURE_MODES

Failure modes of the code in this repository. A number below is an observation
from an offline test in this tree. It is not a review-quality score, a user
count, or evidence that this tool has reviewed real pull requests.

## self-grading loop rubber-stamps

The reflector asks a chat model to score the report this same pipeline just
wrote (`agents/reflector_agent.py`). When that response parses, the state field
`reflection_score_kind` is `model_self_score`. Nothing in this repository
compares that number with a human review or a frozen benchmark.

Measured fallback, same file: if the model call raises and `report_markdown` is
longer than 500 characters, the heuristic returns **7.0** with kind
`heuristic_fallback`. The retry gate is `score < 7.0`, so **7.0 does not
retry**. At 500 characters the same failure returns **4.0** and does retry.
Test: `tests/test_negative_cases.py::test_llm_failure_heuristic_boundary`.

## retry cap exhaustion

`graph/workflow.py` `_should_retry` returns `retry` only when `needs_replan` is
true and `reflection_count < max_reflection_iterations` (default 3). The
reflector increments `reflection_count` on every pass. After the third pass the
count is 3, the comparison fails, and the graph goes to the notifier while
`needs_replan` is still true.

Measured with a scripted model that returns 4.0 three times (a test input, not
a quality measurement): `reflection_count == 3`, `needs_replan is True`,
`notification_status == "dry_run"`, and no POST.
Test: `tests/test_offline_pipeline.py::test_pipeline_retries_while_self_score_below_7_then_dry_run`.

A scripted rise from 4.0 to 8.0 stops on the second pass
(`test_pipeline_stops_retrying_once_self_score_reaches_7`). The unused third
scripted 4.0 is left unconsumed. That shows the cap is an upper bound, not a
quota that always runs three times.

## large diffs/truncation

1. `AnalyzerAgent` sends `file_diff.split("\n")[:200]` to the model.
   `test_analyzer_llm_prompt_drops_lines_after_200` puts
   `LLM_SHOULD_NOT_SEE_THIS_TOKEN_` on line 201 and asserts it is absent from
   the prompt. The static analyzer still flags that line for length. The
   static pass does not recover logic bugs; see the seeded miss below.
2. `ReflectorAgent` inserts `report_markdown[:3000]` into the prompt.
   `test_reflector_prompt_truncates_report_at_3000_chars` asserts a marker
   after character 3000 is absent and that the first 3000 characters are present.
3. `GitHubTool.get_pr_diff` performs one GET and does not follow another page.
   `test_github_diff_fetch_is_a_single_request` records that single URL against
   a fake response. This test does not call GitHub, so it does not measure how
   many files one GitHub response contains.

## token missing

`NotifierAgent` with `dry_run=False` and an empty token returns
`notification_status=failed` and `notification_error` equal to
`GITHUB_TOKEN missing; refusing to post`. It does not call `requests`.
Test: `test_notifier_refuses_to_post_when_token_missing`.

The fetcher still needs a token to read a pull request. This suite does not
perform that call. `POST /review` with no token and no `GITHUB_TOKEN` stores
an empty string (`test_api_defaults_to_dry_run`).

## accidental real comment posting

`dry_run` defaults to true when the state omits it. `POST /review` sets
`dry_run` to false only when the body has `post_comment: true`.
`test_notifier_dry_run_does_not_post_even_with_token` passes a token string
with `dry_run=True` and asserts `requests.get` and `requests.post` are not called.

`test_notifier_posts_only_when_dry_run_is_false` is the live code path under a
patched `requests.post`. The patch records one POST to
`/repos/example/repo/pulls/1/reviews` with `event` `COMMENT`. It does not
create a GitHub comment. A process that runs with `post_comment: true` and a
real `GITHUB_TOKEN` will post.

`tests/conftest.py` rejects any test that reaches `api.github.com`,
`api.deepseek.com`, or `api.openai.com` through `requests` or `httpx`.

## seeded bug the AST analyzer misses

`tests/fixtures/seeded_empty_mean.py` defines `mean(values)` as
`sum(values) / len(values)`. `mean([])` raises `ZeroDivisionError`.
`CodeAnalyzer().analyze_file` on that source returns **no findings**.
Test: `test_ast_misses_seeded_empty_mean`.

Implemented static checks are line length over 120, TODO/FIXME/HACK/XXX, bare
`except`, functions longer than 50 lines, and `console.log` / `console.debug`
in JavaScript or TypeScript. Unused imports, hardcoded strings, and missing
type annotations are not implemented.
