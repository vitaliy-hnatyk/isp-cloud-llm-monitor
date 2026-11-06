# GitHub Actions: Python 3.9 / Ubuntu 26.04 fix

## The error

```
Version 3.9 was not found in the local cache
The version '3.9' with architecture 'x64' was not found for Ubuntu 26.04.
```

The previous `.github/workflows/ci.yml` used `runs-on: ubuntu-latest` with a Python 3.9/3.11/3.13 matrix. GitHub moved `ubuntu-latest` toward Ubuntu 26.04, which does not have Python 3.9 artifacts for `actions/setup-python`.

## Solution in this repository

- `3.9` runs on `ubuntu-24.04`.
- `3.11` and `3.13` run on `ubuntu-latest`.
- The workflow uses maintained major-version tags (`actions/checkout@v7`, `actions/setup-python@v7`).
- Python syntax checking and the original offline unittest discovery remain enabled.

## Apply to an existing GitHub repository

1. Replace `.github/workflows/ci.yml` with the version in this archive.
2. Commit and push the changed file.
3. Go to **GitHub → Actions → Python smoke tests** to view the new run.

If you do **not** need Python 3.9 support, another option is to remove 3.9 from the matrix and run only Python 3.11 and 3.13 on `ubuntu-latest`.

The Node.js `punycode` deprecation warning is separate and not the cause of the failed Python setup. Action upgrades may reduce such warnings; the actual fix is using an OS supporting the requested interpreter.

## References

- https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/
- https://github.com/actions/setup-python
