# Security policy

## Credentials

Never submit real API keys, access tokens, private SSH keys, or `api_keys.env` with an issue, pull request, or screenshot. If a key is accidentally published, immediately revoke and rotate it through the provider dashboard. Do not rely on deleting a commit to make an exposed secret safe.

The included `api_keys.env.example` contains placeholder strings only. The monitor does not intentionally include API keys or generated LLM response content in HTML/CSV reports, but reports can include target hosts, paths, and error details. Review them before distributing.

## Scope and safe use

Use the utility only against services you own, administer, or have permission to test. Keep probe intervals reasonable. Repeated LLM inference calls may cost money or trigger rate limits.

## Reporting vulnerabilities

If you discover a security issue, avoid publishing credentials, exploit payloads, or private server details in a public issue. Contact the repository maintainer through a private channel or enable GitHub's private vulnerability reporting after creating the repository.
