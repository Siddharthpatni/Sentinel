# Conventional Commits and SemVer

Sentinel uses Conventional Commits — a structured commit message
convention that lets us derive semantic version bumps and changelog
entries from git history.

## The format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types we use:

- `feat` — a new user-visible feature (minor bump in SemVer)
- `fix` — a bug fix (patch bump)
- `chore` — tooling, deps, build (no bump)
- `refactor` — code change without behavior change (no bump)
- `docs` — documentation only (no bump)
- `test` — adding or correcting tests (no bump)

`BREAKING CHANGE:` in the footer triggers a major bump regardless of type.

## Why it matters

When Sentinel ships a published package, `semantic-release` reads commits
since the last tag, computes the next version, generates a changelog, and
tags the release. The author writes commits; the bot writes the
changelog.

## The scope tax

Forced structure feels heavy at first. The discipline pays off when
something breaks in production and you can read `git log
--oneline -- gateway/app/routing/` and immediately spot the relevant
commits without reading bodies.
