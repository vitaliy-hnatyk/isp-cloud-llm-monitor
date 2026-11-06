# GitHub repository details

Use these values when creating the GitHub repository.

**Repository name:** `isp-cloud-llm-monitor`

**Project title:** ISP Cloud & LLM Monitor

**Short description (paste into the GitHub Description field):**

> Python network and cloud diagnostics for ISP connectivity, DNS, ICMP, SSH, AWS, Azure, and OpenAI/Claude/Kimi/Mistral APIs, with visual HTML dashboards and CSV reports.

**Topics (paste into GitHub Topics, one by one):**

`python`, `network-monitoring`, `isp-monitoring`, `network-diagnostics`, `uptime-monitoring`, `latency`, `dns`, `icmp`, `ssh`, `aws`, `azure`, `llm`, `api-monitoring`, `openai`, `anthropic`, `mistral`

**Primary language:** Python

**Suggested website:** leave blank until you host a project page. Do not use the local HTML file path as a website URL.

**Social preview:** use `assets/dashboard-screenshot.png`, or crop it to fit the GitHub social preview uploader.

**Readme screenshot:** the README already embeds `assets/dashboard-screenshot.png` and `assets/llm-providers-screenshot.png`; these are actual screenshots of the generated **simulated** HTML report.

## Publish to a new GitHub repository

1. Extract the ZIP, then open a terminal in its `isp-cloud-llm-monitor` folder.
2. Confirm `api_keys.env` is **not** present in the files you plan to upload. Only `api_keys.env.example` should be public.
3. Create a new **empty** repository named `isp-cloud-llm-monitor` on GitHub. Use the description and topics above. Do not ask GitHub to initialize a second README or license: both are included in this project.
4. Run:

```bash
git init
git add .
git commit -m "Initial release: ISP, cloud, and LLM diagnostics"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/isp-cloud-llm-monitor.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub account or organization. You will need to authenticate when pushing.

**Without Git:** open the new GitHub repository, choose **Add file → Upload files**, and upload the extracted project files and folders. GitHub cannot use a ZIP as the repository source until you extract it.

## Create a release

After publishing, select **Releases → Draft a new release** and create the tag `v1.0.0`. Suggested release title: `v1.0.0 — ISP Cloud & LLM Monitor`. Describe the built-in network/cloud checks, four LLM integrations, and the English offline HTML report. Use GitHub's automatically generated source archives.

## Tagline options

- Network visibility from your ISP to the cloud and LLM APIs.
- One Python CLI for network reachability, cloud checks, and LLM availability.
