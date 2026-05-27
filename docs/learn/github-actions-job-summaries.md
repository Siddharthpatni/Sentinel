# GitHub Actions job summaries

The Sentinel eval CI job posts a markdown table of pass/fail per case to
the PR's checks tab. The mechanism is the `$GITHUB_STEP_SUMMARY` env var.

## How it works

`$GITHUB_STEP_SUMMARY` points to a file. Anything appended to that file
during the step becomes the step's summary, rendered as GitHub-flavored
markdown above the raw logs:

```python
summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_path:
    with open(summary_path, "a") as fh:
        fh.write(markdown_table)
```

Multiple steps in the same job can each append — summaries are
concatenated in step order.

## What renders

Standard CommonMark plus tables and `<details>`/`<summary>`. No HTML
forms, no JavaScript, no images from arbitrary URLs (only those served by
the actions cache or `${{ github.server_url }}`).

## Limits

50 KiB per step. Truncate before writing if your suite has hundreds of
cases — collapse passes under `<details>` and surface only failures.

## Anti-pattern

Don't try to drive PR comments from inside the run script. Use a
dedicated action (`peter-evans/create-or-update-comment`) so the comment
has a clear owner and can be updated on rerun rather than spamming new
comments.
