#!/usr/bin/env python3
"""Internet-provider and service reachability monitor with a self-contained HTML report.

Python 3.9+; no required third-party packages. Speed tests require speedtest-cli.

Examples:
    python provider_monitor.py --minutes 10 --interval 5
    python provider_monitor.py --minutes 10 --ssh-host 192.168.1.20 --ssh-port 22
    python provider_monitor.py --no-default-targets \
        --target "SSH gateway=ssh://192.168.1.20:22" \
        --target "Website=https://example.com/" \
        --target "DNS lookup=dns://1.1.1.1/example.com" \
        --target "Google ICMP=icmp://8.8.8.8"
    python provider_monitor.py --aws-region eu-central-1 --azure-region westeurope
    python provider_monitor.py --cloud-only --aws-region us-east-1 --azure-region eastus
    python provider_monitor.py --demo
    python provider_monitor.py --all-tests --minutes 10 --interval 60
    python provider_monitor.py --all-tests --ssh-host 192.168.1.20 --llm-base-url https://api.openai.com/v1
    python provider_monitor.py --llm-base-url https://api.openai.com/v1 --llm-mode models
    python provider_monitor.py --llm-all-providers --llm-mode models --demo

These checks measure service reachability, not proof of ISP responsibility.
SSH checks read the server identification banner; they do not authenticate.
Cloud HTTP endpoints test public website availability, and regional targets test TCP:443.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from html import escape
import math
from pathlib import Path
import platform
import random
import re
import secrets
import shutil
import socket
import ssl
import statistics
import struct
import subprocess
import sys
import time
from urllib.parse import urlsplit
import http.client
import json
import os
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError


COLORS = ("#3a9ed8", "#836ae6", "#ed9e43", "#17a986", "#df658e", "#6d90ad", "#ad7d43", "#bd56be")
DEFAULT_URLS = (
    ("Cloudflare TCP", "tcp://1.1.1.1:443"),
    ("Google TCP", "tcp://8.8.8.8:443"),
    ("Quad9 TCP", "tcp://9.9.9.9:443"),
)

# Public web endpoints: HTTPS availability, not an AWS/Azure region benchmark.
CLOUD_DEFAULT_URLS = (
    ("AWS global website", "https://aws.amazon.com/", "AWS"),
    ("Azure global website", "https://azure.microsoft.com/", "Azure"),
)

# Explicit, documented region codes. Regional probes use TCP:443, so
# authentication/HTTP status codes are not involved in their success criteria.
# AWS: Amazon S3 regional API endpoints documented in AWS General Reference.
AWS_REGIONS = {
    "eu-central-1": "Frankfurt", "eu-west-1": "Ireland", "eu-west-2": "London",
    "eu-west-3": "Paris", "eu-north-1": "Stockholm", "us-east-1": "N. Virginia",
    "us-east-2": "Ohio", "us-west-2": "Oregon", "ap-southeast-1": "Singapore",
    "ap-northeast-1": "Tokyo", "ap-southeast-2": "Sydney",
}
# Azure: regional Azure Monitor Live Metrics endpoints, as documented by Microsoft.
AZURE_REGIONS = {
    "polandcentral": "Warsaw", "westeurope": "West Europe", "northeurope": "North Europe",
    "germanywestcentral": "Germany West Central", "francecentral": "France Central",
    "uksouth": "UK South", "swedencentral": "Sweden Central",
    "eastus": "East US", "eastus2": "East US 2", "westus2": "West US 2",
    "japaneast": "Japan East", "southeastasia": "Southeast Asia",
}


# Verified provider base paths: Anthropic's native Messages API; others are chat-compatible.
LLM_PRESETS = {
    "openai": ("OpenAI API", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": ("Anthropic Claude API", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "kimi": ("Kimi (Moonshot) API", "https://api.moonshot.ai/v1", "KIMI_API_KEY"),
    "mistral": ("Mistral API", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
}

BASE_CSS = """
:root{color-scheme:light;--text:#1d2b43;--muted:#66768c;--border:#dfe8f1;--bg:#f3f7fb;--card:#fff;--good:#138361;--bad:#cb4963}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.5}
main{max-width:1180px;margin:auto;padding:34px 20px 64px}.eyebrow{text-transform:uppercase;letter-spacing:.16em;color:#5b719c;font-weight:700;font-size:12px}
h1{font-size:clamp(27px,4.7vw,41px);letter-spacing:-.035em;margin:4px 0 6px}h2{margin:0 0 14px;font-size:20px;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 20px}.heading{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.badge{font-weight:700;font-size:13px;display:inline-block;border-radius:999px;padding:8px 14px;background:#e2f4ec;color:#117753}.badge.warn{background:#fff1dd;color:#965512}.badge.fail{background:#ffe8eb;color:#a72e47}
.notice{background:#fff4dd;border:1px solid #efd3a0;color:#75521a;border-radius:12px;padding:12px 16px;margin:18px 0}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:18px 0 25px}
.card{border:1px solid var(--border);background:var(--card);border-radius:16px;padding:19px;box-shadow:0 4px 16px rgba(20,41,72,.025);margin-bottom:17px}
.metric .label{font-size:13px;color:var(--muted)}.metric strong{display:block;font-size:29px;letter-spacing:-.035em;margin:7px 0 3px}.metric small{color:var(--muted);font-size:12px}
.chart{width:100%;display:block;height:auto}.legend{display:flex;gap:15px;flex-wrap:wrap;margin:5px 0 13px;font-size:13px;color:var(--muted)}.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px}
table{width:100%;border-collapse:collapse}th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.065em;color:var(--muted);white-space:nowrap}td,th{padding:11px 9px;border-bottom:1px solid var(--border)}tr:last-child td{border-bottom:none}
.table-wrap{overflow-x:auto}.muted{color:var(--muted)}.fine{font-size:13px;color:var(--muted)}.twocol{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.speed-value{font-weight:800;font-size:30px;margin:6px 0}.footer{font-size:12px;color:var(--muted);margin-top:18px}
code{font-size:.92em;background:#edf2f7;padding:1px 5px;border-radius:4px}td{font-size:14px}
.cloudmetrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.cloudbar{display:grid;grid-template-columns:minmax(105px,205px) 1fr 110px;gap:12px;align-items:center;margin:13px 0;font-size:13px}
.bartrack{height:16px;background:#eaf0f5;border-radius:8px;overflow:hidden}
.barfill{height:100%;border-radius:8px}
@media(max-width:860px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.twocol{grid-template-columns:1fr}}
@media(max-width:480px){main{padding:20px 11px 35px}.card{padding:14px}.metric strong{font-size:24px}.metrics{gap:8px}.cloudmetrics{grid-template-columns:1fr}.cloudbar{grid-template-columns:110px 1fr 75px;gap:6px;font-size:11px}}
"""


@dataclass(frozen=True)
class Target:
    name: str
    protocol: str
    endpoint: str
    hostname: str
    port: int | None = None
    dns_name: str | None = None
    provider: str = ""
    region: str = ""
    llm_mode: str = "models"
    llm_model: str = ""
    llm_key_env: str = "OPENAI_API_KEY"
    llm_auth_header: str = "bearer"
    llm_vendor: str = "compatible"
    llm_version: str = "2026-10-21"
    llm_max_tokens: int = 32
    llm_timeout: float = 20.0


def target_from_spec(spec: str, default_name: str | None = None,
                     provider: str = "", region: str = "") -> Target:
    """Accept 'Display name=protocol://host[:port][/path]' target specifications."""
    # A bare URL may contain an equals sign in its query string. Only split
    # NAME=URL when the prefix is not itself part of a URL.
    prefix, sep, value = spec.partition("=")
    named = bool(sep and "://" not in prefix and "://" in value)
    uri = value.strip() if named else spec.strip()
    name = prefix.strip() if named else (default_name or uri)
    if not name or not uri:
        raise ValueError("A target name and URL are required")
    parsed = urlsplit(uri)
    protocol = parsed.scheme.lower()
    if protocol not in {"tcp", "ssh", "http", "https", "dns", "icmp"}:
        raise ValueError(f"Unsupported protocol {protocol!r}; use tcp, ssh, http, https, dns, or icmp")
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be included in target URLs")
    if not parsed.hostname:
        raise ValueError(f"Target {name!r} must have a host")
    try:
        supplied_port = parsed.port
    except ValueError as ex:
        raise ValueError(f"Invalid port for target {name!r}: {ex}") from ex
    if protocol == "tcp" and supplied_port is None:
        raise ValueError("TCP targets require a port, e.g. tcp://host:443")
    if protocol == "ssh":
        port = supplied_port or 22
    elif protocol in {"http", "https"}:
        port = supplied_port or (443 if protocol == "https" else 80)
    elif protocol == "dns":
        port = supplied_port or 53
    elif protocol == "icmp":
        if supplied_port is not None:
            raise ValueError("ICMP does not use ports")
        port = None
    else:
        port = supplied_port
    if protocol in {"tcp", "ssh", "icmp"} and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError(f"{protocol.upper()} targets must not include a path, query, or fragment")
    if protocol == "dns":
        dns_name = parsed.path.lstrip("/") or "example.com"
        if not re.fullmatch(r"[A-Za-z0-9._-]+", dns_name) or len(dns_name) > 253:
            raise ValueError("Invalid DNS lookup name")
        if parsed.query or parsed.fragment:
            raise ValueError("DNS targets must not include query strings or fragments")
    else:
        dns_name = None
    if parsed.fragment:
        raise ValueError("Target URLs must not include fragments")
    return Target(name, protocol, uri, parsed.hostname, port, dns_name, provider, region)


def add_unique(targets: list[Target], target: Target):
    if any(existing.name == target.name for existing in targets):
        raise ValueError(f"Duplicate target name: {target.name!r}; use unique display names")
    targets.append(target)


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_tcp(target: Target, timeout: float) -> tuple[float, str]:
    start = time.perf_counter()
    with socket.create_connection((target.hostname, target.port), timeout=timeout):
        return (time.perf_counter() - start) * 1000, "TCP connection established"


def run_ssh(target: Target, timeout: float) -> tuple[float, str]:
    start = time.perf_counter()
    with socket.create_connection((target.hostname, target.port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        stream = connection.makefile("rb")
        try:
            for _ in range(10):  # RFC 4253 allows pre-identification text lines.
                line = stream.readline(256)
                if line.startswith(b"SSH-"):
                    banner = line.decode("ascii", errors="replace").strip()
                    if not re.match(r"^SSH-2\.0-|^SSH-1\.99-", banner):
                        raise ValueError("Unsupported SSH identification version")
                    return (time.perf_counter() - start) * 1000, banner[:160]
                if not line:
                    raise ValueError("No SSH identification received")
            raise ValueError("No SSH identification received in first 10 lines")
        finally:
            stream.close()


def run_http(target: Target, timeout: float) -> tuple[float, str]:
    parsed = urlsplit(target.endpoint)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    conn_cls = http.client.HTTPSConnection if target.protocol == "https" else http.client.HTTPConnection
    start = time.perf_counter()
    conn = conn_cls(target.hostname, target.port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"User-Agent": "ProviderMonitor/2.0", "Accept": "*/*", "Connection": "close"})
        response = conn.getresponse()
        elapsed_ms = (time.perf_counter() - start) * 1000  # until response headers
        # Read a small amount of data so the protocol response is actually usable.
        response.read(1)
        if 200 <= response.status < 400:
            return elapsed_ms, f"HTTP {response.status} {response.reason}"
        raise ValueError(f"HTTP {response.status} {response.reason}")
    finally:
        conn.close()


def encode_dns_name(name: str) -> bytes:
    parts = name.rstrip(".").split(".")
    if not parts or any(not part or len(part.encode("ascii")) > 63 for part in parts):
        raise ValueError("Invalid DNS domain labels")
    return b"".join(bytes([len(part)]) + part.encode("ascii") for part in parts) + b"\x00"


def run_dns(target: Target, timeout: float) -> tuple[float, str]:
    # A real DNS-over-UDP query sent directly to the configured DNS server.
    txn = secrets.randbelow(65536)
    query = (struct.pack("!HHHHHH", txn, 0x0100, 1, 0, 0, 0)
             + encode_dns_name(target.dns_name or "example.com") + struct.pack("!HH", 1, 1))
    start = time.perf_counter()
    results = socket.getaddrinfo(target.hostname, target.port, type=socket.SOCK_DGRAM)
    # An IP address is recommended to avoid querying the system DNS for the DNS server itself.
    if not results:
        raise OSError("Could not resolve DNS server address")
    family, socktype, proto, _, addr = results[0]
    with socket.socket(family, socktype, proto) as udp:
        udp.settimeout(timeout)
        udp.sendto(query, addr)
        while True:
            packet, source = udp.recvfrom(4096)
            if len(packet) < 12:
                continue
            txid, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", packet[:12])
            if txid != txn or not (flags & 0x8000):
                continue
            if source[0] != addr[0]:
                continue
            ms = (time.perf_counter() - start) * 1000
            rcode = flags & 0x000F
            if rcode != 0:
                raise ValueError(f"DNS response code {rcode}")
            if ancount == 0:
                raise ValueError("DNS response had no answer records")
            return ms, f"DNS NOERROR, {ancount} answer(s)"


def run_icmp(target: Target, timeout: float) -> tuple[float, str]:
    if shutil.which("ping") is None:
        raise RuntimeError("System ping utility not found")
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(max(1, math.ceil(timeout * 1000))), target.hostname]
    elif system == "darwin":
        cmd = ["ping", "-n", "-c", "1", "-W", str(max(1, math.ceil(timeout * 1000))), target.hostname]
    else:
        cmd = ["ping", "-n", "-c", "1", "-W", str(max(1, math.ceil(timeout))), target.hostname]
    start = time.perf_counter()
    completed = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout + 2)
    if completed.returncode != 0:
        raise OSError("ICMP echo not answered (or blocked by the network)")
    match = re.search(r"time\s*[=<]\s*(\d+(?:[.,]\d+)?)\s*ms", completed.stdout, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ".")), "ICMP echo reply (round-trip time)"
    return (time.perf_counter() - start) * 1000, "ICMP echo reply (process time; RTT unavailable)"



class NoLLMRedirect(HTTPRedirectHandler):
    """Never forward API credentials from an LLM endpoint to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


LLM_HTTP_OPENER = build_opener(NoLLMRedirect)


def run_llm(target: Target, timeout: float) -> tuple[float, str]:
    """Measure authenticated LLM API access; never persist tokens or generated content.

    The Anthropic native API uses /messages and anthropic-version. OpenAI,
    Kimi and Mistral use their OpenAI-style chat-completions interfaces.
    """
    mode = target.llm_mode
    vendor = target.llm_vendor
    if vendor == "anthropic" and mode == "responses":
        raise ValueError("Anthropic uses --llm-mode chat (native Messages API), not responses")
    if vendor in {"kimi", "mistral"} and mode == "responses":
        raise ValueError(f"{vendor.title()} requires --llm-mode chat, not responses")
    path = "/models" if mode == "models" else (
        "/messages" if vendor == "anthropic" else
        "/chat/completions" if mode == "chat" else "/responses"
    )
    url = target.endpoint.rstrip("/") + path
    secret = os.environ.get(target.llm_key_env, "").strip()
    if not secret and vendor == "kimi":
        secret = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if vendor in LLM_PRESETS and not secret:
        raise ValueError(f"Missing API key: set {target.llm_key_env} in your environment")
    parsed_endpoint = urlsplit(target.endpoint)
    if (secret and parsed_endpoint.scheme != "https"
            and parsed_endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}):
        raise ValueError("Refusing to send API key over unencrypted remote HTTP")
    headers = {"User-Agent": "ProviderMonitor/4.0", "Accept": "application/json"}
    if secret:
        if target.llm_auth_header == "api-key":
            headers["api-key"] = secret
        else:
            headers["Authorization"] = "Bearer " + secret
    if vendor == "anthropic":
        headers["anthropic-version"] = target.llm_version
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
        if workspace:
            headers["anthropic-workspace-id"] = workspace
    body = None
    if mode in {"chat", "responses"}:
        if not target.llm_model:
            raise ValueError("Model ID is required for LLM inference probes")
        headers["Content-Type"] = "application/json"
        if vendor == "anthropic":
            payload = {"model": target.llm_model, "max_tokens": target.llm_max_tokens,
                       "messages": [{"role": "user", "content": "Reply with OK."}]}
        elif mode == "chat":
            payload = {"model": target.llm_model,
                       "messages": [{"role": "user", "content": "Reply with OK."}],
                       "max_tokens": target.llm_max_tokens}
        else:
            payload = {"model": target.llm_model, "input": "Reply with OK.",
                       "max_output_tokens": target.llm_max_tokens}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    start = time.perf_counter()
    try:
        with LLM_HTTP_OPENER.open(Request(url, data=body, headers=headers,
                                          method=("POST" if body is not None else "GET")),
                                  timeout=target.llm_timeout) as response:
            status = response.status
            raw = response.read(131072)  # Do not persist model output.
    except HTTPError as exc:
        # Do not read/log the provider error body, which may contain confidential data.
        raise ValueError(f"LLM API returned HTTP {exc.code}") from None
    elapsed = (time.perf_counter() - start) * 1000
    if not 200 <= status < 300:
        raise ValueError(f"LLM API returned HTTP {status}")
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("LLM API returned invalid JSON") from None
    if not isinstance(obj, dict) or "error" in obj:
        raise ValueError("Response was not a successful LLM response")
    if mode == "models" and not isinstance(obj.get("data"), list):
        raise ValueError("Invalid models response: missing data list")
    if mode in {"chat", "responses"}:
        if vendor == "anthropic" and obj.get("type") != "message":
            raise ValueError("Invalid Anthropic Messages API response")
        if vendor != "anthropic" and not (obj.get("choices") if mode == "chat" else obj.get("output")):
            raise ValueError("Invalid LLM inference response")
    details = f"HTTP {status}; {vendor} {mode}"
    usage = obj.get("usage")
    if isinstance(usage, dict):
        keys = ("total_tokens", "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens")
        counts = [f"{k}={usage[k]}" for k in keys if isinstance(usage.get(k), int)]
        if counts:
            details += "; " + ", ".join(counts)
    return elapsed, details


def probe(target: Target, timeout: float) -> dict:
    funcs = {"tcp": run_tcp, "ssh": run_ssh, "http": run_http,
             "https": run_http, "dns": run_dns, "icmp": run_icmp}
    try:
        ms, detail = (run_llm(target, timeout) if target.protocol == "llm"
                      else funcs[target.protocol](target, timeout))
        return {"latency_ms": round(ms, 2), "detail": detail, "error": ""}
    except (OSError, RuntimeError, ValueError, ssl.SSLError, http.client.HTTPException,
            subprocess.TimeoutExpired, URLError, TimeoutError, json.JSONDecodeError) as exc:
        detail = str(exc).strip()[:180] or type(exc).__name__
        return {"latency_ms": None, "detail": "", "error": f"{type(exc).__name__}: {detail}"}


def generate_demo(targets: list[Target], interval: float) -> list[dict]:
    rng = random.Random(41)
    output = []
    start = time.time() - (120 - 1) * interval
    for i in range(120):
        results = {}
        for j, target in enumerate(targets):
            failed = i in {20, 21, 22} or (j == 1 and i in {54, 55}) or (j == 2 and i == 83)
            latency = None if failed else max(2, rng.gauss(15 + j * 7, 4) + (rng.uniform(45, 100) if 90 <= i <= 97 else 0))
            results[target.name] = {"latency_ms": round(latency, 2) if latency is not None else None,
                                    "detail": f"DEMO: {target.protocol.upper()} succeeded" if not failed else "",
                                    "error": "DEMO_OUTAGE" if failed else ""}
        stamp = datetime.fromtimestamp(start + i * interval).astimezone().isoformat(timespec="seconds")
        output.append({"time": stamp, "results": results})
    return output


def monitor(targets: list[Target], minutes: float, interval: float, timeout: float) -> list[dict]:
    data = []
    started = time.monotonic()
    deadline = started + minutes * 60
    print(f"Monitoring {len(targets)} targets for {minutes:g} minute(s), every {interval:g} seconds. Press Ctrl+C to stop.", flush=True)
    cycle = 0
    try:
        while True:
            stamp = timestamp()
            results = {target.name: probe(target, timeout) for target in targets}
            data.append({"time": stamp, "results": results})
            values = " | ".join(f"{t.name}: {r['latency_ms']:.1f} ms" if (r := results[t.name])["latency_ms"] is not None
                                else f"{t.name}: FAIL" for t in targets)
            print(f"[{stamp[11:19]}] {values}", flush=True)
            cycle += 1
            if time.monotonic() >= deadline:
                break
            delay = min(deadline - time.monotonic(), started + cycle * interval - time.monotonic())
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        print("\nInterrupted. Preparing reports from collected samples.", flush=True)
    return data


def speed_test() -> dict:
    try:
        import speedtest
    except ImportError:
        return {"error": "speedtest-cli is not installed. Run: python -m pip install speedtest-cli"}
    try:
        print("Running download/upload speed test...", flush=True)
        client = speedtest.Speedtest(secure=True)
        client.get_best_server()
        return {"download": round(client.download() / 1_000_000, 2),
                "upload": round(client.upload(pre_allocate=False) / 1_000_000, 2),
                "ping": round(client.results.ping, 2)}
    except Exception as exc:
        return {"error": f"Speed test failed: {type(exc).__name__}: {str(exc)[:160]}"}


def write_csv(data: list[dict], targets: list[Target], filename: Path):
    with filename.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp_local", "target_name", "provider", "region", "protocol", "endpoint", "latency_ms", "ok", "detail", "error"])
        for sample in data:
            for target in targets:
                result = sample["results"][target.name]
                writer.writerow([sample["time"], target.name, target.provider, target.region, target.protocol.upper(), target.endpoint,
                                 "" if result["latency_ms"] is None else result["latency_ms"],
                                 int(result["latency_ms"] is not None), result["detail"], result["error"]])


def summaries(data: list[dict], targets: list[Target]) -> dict:
    result = {}
    for target in targets:
        sequence = [sample["results"][target.name]["latency_ms"] for sample in data]
        valid = [v for v in sequence if v is not None]
        deltas = [abs(a - b) for a, b in zip(sequence, sequence[1:]) if a is not None and b is not None]
        result[target.name] = {"success_rate": len(valid) * 100 / len(sequence), "failed": len(sequence) - len(valid),
                               "avg": statistics.mean(valid) if valid else None,
                               "min": min(valid) if valid else None,
                               "max": max(valid) if valid else None,
                               "variation": statistics.mean(deltas) if deltas else None}
    return result


def failure_episodes(data: list[dict], targets: list[Target], interval: float):
    spans = []
    start = None
    for idx, sample in enumerate(data):
        failed = all(sample["results"][t.name]["latency_ms"] is None for t in targets)
        if failed and start is None:
            start = idx
        if not failed and start is not None:
            spans.append((start, idx - 1))
            start = None
    if start is not None:
        spans.append((start, len(data) - 1))
    return [(data[a]["time"], data[b]["time"], (b - a + 1) * interval) for a, b in spans]


def format_ms(v):
    return "—" if v is None else f"{v:.1f}"


def latency_chart(data: list[dict], targets: list[Target]) -> str:
    w, h = 1120, 355
    left, right, top, bottom = 72, 22, 28, 50
    plot_w, plot_h = w - left - right, h - top - bottom
    series = [sample["results"][target.name]["latency_ms"] for sample in data for target in targets]
    valid = [v for v in series if v is not None]
    ceiling = max(50, math.ceil(max(valid, default=0) / 20) * 20)
    def x(i): return left + (i / max(1, len(data) - 1)) * plot_w
    def y(v): return top + plot_h * (1 - v / ceiling)
    parts = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Protocol response times by target in milliseconds">']
    for k in range(5):
        value = ceiling * k / 4
        yy = y(value)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{w-right}" y2="{yy:.1f}" stroke="#e6edf4"/>')
        parts.append(f'<text x="{left-12}" y="{yy+4:.1f}" text-anchor="end" font-size="12" fill="#69798f">{value:g}</text>')
    parts.append('<text x="12" y="17" font-size="13" fill="#69798f">ms</text>')
    bucket_size = max(1, math.ceil(len(data) / 600))
    for index, target in enumerate(targets):
        color = COLORS[index % len(COLORS)]
        points = []
        for start in range(0, len(data), bucket_size):
            block = [row["results"][target.name]["latency_ms"] for row in data[start:start + bucket_size]]
            # Break the line at any failed sample; failures remain visible in the timeline.
            if any(value is None for value in block):
                if len(points) > 1:
                    parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" points="{" ".join(points)}"/>')
                points = []
            else:
                val = max(block)
                points.append(f'{x(min(start + bucket_size // 2, len(data)-1)):.1f},{y(val):.1f}')
        if len(points) > 1:
            parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" points="{" ".join(points)}"/>')
        elif len(points) == 1:
            px, py = points[0].split(",")
            parts.append(f'<circle cx="{px}" cy="{py}" r="3.4" fill="{color}"/>')
    if data:
        parts.append(f'<text x="{left}" y="{h-12}" font-size="13" fill="#69798f">{escape(data[0]["time"][11:19])}</text>')
        parts.append(f'<text x="{w-right}" y="{h-12}" text-anchor="end" font-size="13" fill="#69798f">{escape(data[-1]["time"][11:19])}</text>')
    parts.append('</svg>')
    return "".join(parts)


def timeline_chart(data: list[dict], targets: list[Target]) -> str:
    width, left, right = 1120, 190, 20
    row_h, top = 40, 18
    height = top + len(targets) * row_h + 42
    plot_w = width - left - right
    n = max(1, len(data))
    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Per-target success and failure timeline">']
    for j, target in enumerate(targets):
        yy = top + j * row_h
        name = escape(target.name[:23] + "…" if len(target.name) > 24 else target.name)
        parts.append(f'<text x="{left - 10}" y="{yy + 17}" font-size="13" text-anchor="end" fill="#43536a">{name}</text>')
        parts.append(f'<rect x="{left}" y="{yy}" width="{plot_w}" height="22" rx="4" fill="#dee8f0"/>')
        flags = [r["results"][target.name]["latency_ms"] is not None for r in data]
        beginning = 0
        for i in range(1, len(flags)+1):
            if i == len(flags) or flags[i] != flags[beginning]:
                xx = left + beginning * plot_w / n
                ww = (i-beginning) * plot_w / n
                color = "#24a883" if flags[beginning] else "#e75a75"
                text = "SUCCESS" if flags[beginning] else "FAILURE"
                parts.append(f'<rect x="{xx:.2f}" y="{yy}" width="{ww:.2f}" height="22" fill="{color}"><title>{escape(target.name)}: {text} ({i-beginning} checks)</title></rect>')
                beginning = i
    parts.append(f'<text x="{left}" y="{height-9}" font-size="13" fill="#69798f">Start</text>')
    parts.append(f'<text x="{width-right}" y="{height-9}" text-anchor="end" font-size="13" fill="#69798f">End</text>')
    parts.append("</svg>")
    return "".join(parts)


def cloud_section(targets: list[Target], stats: dict) -> str:
    """Display a cloud-provider summary and apples-to-apples regional TCP bars."""
    cloud_targets = [t for t in targets if t.provider in {"AWS", "Azure"}]
    if not cloud_targets:
        return ""
    provider_cards = []
    for provider in ("AWS", "Azure"):
        selected = [t for t in cloud_targets if t.provider == provider]
        if not selected:
            continue
        # Every target has the same number of monitoring samples.
        available = statistics.mean(stats[t.name]["success_rate"] for t in selected)
        fails = sum(stats[t.name]["failed"] for t in selected)
        region_count = sum(bool(t.region) for t in selected)
        provider_cards.append(
            f'<div class="card metric"><div class="label">{provider} reachability</div>'
            f'<strong>{available:.1f}%</strong><small>{len(selected)} targets · '
            f'{region_count} regional · {fails} failed checks</small></div>'
        )
    regional = [t for t in cloud_targets if t.region and t.protocol == "tcp"]
    bars = ""
    if regional:
        available_latencies = [stats[t.name]["avg"] for t in regional if stats[t.name]["avg"] is not None]
        largest = max(1.0, max(available_latencies, default=0))
        bar_items = []
        for t in regional:
            avg = stats[t.name]["avg"]
            color = "#e79a38" if t.provider == "AWS" else "#368bd6"
            desc = f'{t.provider} · {t.region}'
            if avg is None:
                bar_items.append(f'<div class="cloudbar"><span>{escape(desc)}</span>'
                                 f'<div class="bartrack"><div class="barfill" style="width:0"></div></div>'
                                 f'<strong>no successes</strong></div>')
            else:
                percent = avg * 100 / largest
                bar_items.append(f'<div class="cloudbar"><span>{escape(desc)}</span>'
                                 f'<div class="bartrack"><div class="barfill" style="width:{percent:.1f}%;background:{color}"></div></div>'
                                 f'<strong>{avg:.1f} ms</strong></div>')
        bars = '<div class="card"><h2>AWS vs Azure · Regional TCP connection time</h2>' + "".join(bar_items) + (
            '<p class="fine">Mean successful TCP:443 connection time only; lower is faster. '
            'Regions and services may differ, and DNS resolution is part of the measurement. '
            'This is not an end-to-end cloud performance benchmark.</p></div>'
        )
    return ('<div class="card"><h2>Amazon Web Services &amp; Microsoft Azure</h2>'
            '<p class="fine">Public websites are HTTPS probes; regional cloud endpoints are TCP:443 '
            'reachability probes. A successful check does not test your AWS or Azure account, '
            'cloud infrastructure performance, or SSH authentication.</p></div>'
            '<div class="cloudmetrics">' + "".join(provider_cards) + '</div>' + bars)



def llm_section(targets: list[Target], stats: dict) -> str:
    llms = [t for t in targets if t.protocol == "llm"]
    if not llms:
        return ""
    rows = []
    for t in llms:
        stat = stats[t.name]
        rows.append(
            f'<tr><td><strong>{escape(t.name)}</strong></td><td>{escape(t.llm_mode)}</td>'
            f'<td>{stat["success_rate"]:.1f}%</td><td>{stat["failed"]}</td>'
            f'<td>{format_ms(stat["avg"])}</td><td>{escape(t.llm_model or "—")}</td></tr>'
        )
    return ('<div class="card"><h2>LLM API providers</h2>'
            '<p class="fine">These are application-layer API checks, not network ping. '
            'Model listing does not generate tokens; chat and responses requests can be billed. '
            'Different model families and operations are not directly comparable. '
            'No API keys or generated text are saved.</p>'
            '<div class="table-wrap"><table><thead><tr><th>Provider</th><th>Mode</th>'
            '<th>Availability</th><th>Failures</th><th>Average latency</th><th>Model</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></div>')


def html_report(data: list[dict], targets: list[Target], speed: dict | None,
                demo: bool, interval: float, filename: Path):
    if not data:
        raise ValueError("No samples were collected")
    stats = summaries(data, targets)
    episodes = failure_episodes(data, targets, interval)
    cycles = len(data)
    total_checks = cycles * len(targets)
    succeeded = total_checks - sum(stats[t.name]["failed"] for t in targets)
    percent = 100 * succeeded / total_checks
    partial_or_total = sum(v["failed"] for v in stats.values())
    status = "All targets failed during some checks" if episodes else ("Some checks failed" if partial_or_total else "All checks succeeded")
    badge_style = "fail" if episodes else ("warn" if partial_or_total else "")
    notice = '<div class="notice"><strong>DEMONSTRATION DATA:</strong> These values are simulated. They do not represent a measurement of your connection.</div>' if demo else ''
    legend = "".join(f'<span><span class="dot" style="background:{COLORS[index % len(COLORS)]}"></span>{escape(t.name)} ({t.protocol.upper()})</span>'
                     for index, t in enumerate(targets))
    rows = "".join(
        f'<tr><td><strong>{escape(t.name)}</strong><div class="fine">{escape(t.protocol.upper())} · {escape(t.endpoint)}</div></td>'
        f'<td>{stats[t.name]["success_rate"]:.1f}%</td><td>{stats[t.name]["failed"]}</td>'
        f'<td>{format_ms(stats[t.name]["avg"])}</td><td>{format_ms(stats[t.name]["min"])}</td>'
        f'<td>{format_ms(stats[t.name]["max"])}</td><td>{format_ms(stats[t.name]["variation"])}</td></tr>'
        for t in targets)
    cloud_report = cloud_section(targets, stats)
    llm_report = llm_section(targets, stats)
    episode_rows = "".join(f'<tr><td>{escape(first.replace("T", " ")[:19])}</td><td>{escape(last.replace("T", " ")[:19])}</td><td>~{duration:g} s</td></tr>'
                           for first, last, duration in episodes[:30])
    episode_section = (f'<div class="card"><h2>All-target failure episodes</h2><div class="table-wrap"><table><thead><tr><th>First failed check</th><th>Last failed check</th><th>Estimated duration</th></tr></thead><tbody>{episode_rows}</tbody></table></div><p class="fine">Timing is approximate; failures can start and end between checks. Only the first 30 episodes are shown here; CSV retains all checks.</p></div>'
                       if episodes else '<div class="card"><h2>All-target failure episodes</h2><p class="muted">No check failed across every configured target simultaneously.</p></div>')
    if speed and "error" not in speed:
        speed_section = f'<div class="twocol"><div class="card"><h2>Download speed</h2><div class="speed-value">{speed["download"]:.1f} <span class="fine">Mbps</span></div></div><div class="card"><h2>Upload speed</h2><div class="speed-value">{speed["upload"]:.1f} <span class="fine">Mbps</span></div><div class="fine">Speed-test server latency: {speed["ping"]:.1f} ms</div></div></div>'
    elif speed and "error" in speed:
        speed_section = f'<div class="card"><h2>Download / upload speed</h2><p class="muted">{escape(speed["error"])}</p></div>'
    else:
        speed_section = '<div class="card"><h2>Download / upload speed</h2><p class="muted">Not run. Add <code>--speedtest</code> and install <code>speedtest-cli</code> to enable.</p></div>'
    first = escape(data[0]["time"].replace("T", " ")[:19])
    last = escape(data[-1]["time"].replace("T", " ")[:19])
    header = f'<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Internet &amp; Protocol Diagnostics</title><style>{BASE_CSS}</style></head>'
    report = f'''<!doctype html>{header}<body><main>
<div class="eyebrow">Connectivity / protocol diagnostics</div>
<div class="heading"><h1>Internet &amp; Protocol Diagnostics</h1><span class="badge {badge_style}">{escape(status)}</span></div>
<p class="sub">{first} — {last} · {cycles} cycles · {len(targets)} targets · {interval:g}-second configured interval</p>{notice}
<section class="metrics">
<div class="card metric"><div class="label">Successful checks</div><strong>{percent:.1f}%</strong><small>{succeeded} of {total_checks} protocol checks</small></div>
<div class="card metric"><div class="label">All-target failure episodes</div><strong>{len(episodes)}</strong><small>Every configured target failed</small></div>
<div class="card metric"><div class="label">Failed checks</div><strong>{partial_or_total}</strong><small>Across all protocols</small></div>
<div class="card metric"><div class="label">Observation window</div><strong>{(cycles-1)*interval/60:.1f}<span style="font-size:16px"> min</span></strong><small>Approximate, based on configured interval</small></div>
</section>
{cloud_report}
{llm_report}
<div class="card"><h2>Protocol response time</h2><div class="legend">{legend}</div>{latency_chart(data, targets)}<p class="fine">Time to TCP connect (TCP), server identification (SSH), HTTP response headers (HTTP/HTTPS), DNS response (DNS), ICMP round trip (ICMP), or LLM API response (LLM). These quantities are <strong>not directly comparable</strong>. The maximum successful sample in each chart bucket is shown. Gaps may indicate failures.</p></div>
<div class="card"><h2>Success / failure timeline</h2><div class="legend"><span><span class="dot" style="background:#24a883"></span>Success</span><span><span class="dot" style="background:#e75a75"></span>Failure</span></div>{timeline_chart(data, targets)}</div>
<div class="card"><h2>Results by target</h2><div class="table-wrap"><table><thead><tr><th>Target / protocol</th><th>Success</th><th>Failures</th><th>Avg ms</th><th>Min ms</th><th>Max ms</th><th>Variation* ms</th></tr></thead><tbody>{rows}</tbody></table></div></div>
{episode_section}{speed_section}
<div class="card"><h2>Interpretation and limitations</h2>
<p class="fine">A failure is a failed application/protocol check, not necessarily an ISP outage. SSH validates the SSH server banner <strong>without authenticating</strong>. HTTPS validates TLS certificates using Python's default trusted certificates. HTTP/HTTPS success means a 2xx/3xx status (redirects are not followed). DNS sends a UDP A-record query directly to the selected DNS server and requires a nonempty successful answer. ICMP uses the system <code>ping</code> executable, which may be blocked by firewalls. TCP success means the TCP connection was accepted; it does not validate an application service. LLM checks call OpenAI-compatible APIs or the native Anthropic Messages API: the models mode measures listing rather than inference, and generation modes may incur provider charges. API keys and generated response text are not written to CSV or HTML. *Variation is the mean absolute change between consecutive successful samples, not standardized network jitter. Use Ethernet, compare multiple independent public targets, and check your local gateway before attributing failures to an ISP. Amazon/Azure global probes reach public website/CDN services, not a particular cloud region; regional TCP probes use published AWS S3 and Azure Monitor endpoints, which can have access controls or routing behavior independent of your ISP.</p>
</div>
<div class="footer">Generated locally as an offline HTML file. Timings and failure durations are limited by probing intervals, timeouts, and target behavior.</div>
</main></body></html>'''
    filename.write_text(report, encoding="utf-8")
    return percent, len(episodes)


def get_parser():
    parser = argparse.ArgumentParser(description="Internet and protocol monitor: TCP, SSH, HTTP(S), DNS, ICMP, LLM API; English HTML/CSV reports",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--minutes", type=float, default=10, help="Monitoring duration in minutes")
    parser.add_argument("--interval", type=float, default=5, help="Time between monitoring cycles in seconds")
    parser.add_argument("--timeout", type=float, default=2, help="Timeout per probe in seconds")
    parser.add_argument("--target", action="append", default=[], metavar="'NAME=PROTOCOL://ENDPOINT'",
                        help="Add any TCP/SSH/HTTP/HTTPS/DNS/ICMP target; repeat this argument")
    parser.add_argument("--all-tests", action="store_true",
                        help="Enable standard DNS, ICMP, HTTP, HTTPS, two AWS and two Azure regions (plus built-in TCP/global-cloud checks); speed test runs at end")
    parser.add_argument("--no-default-targets", action="store_true", help="Disable all built-in public checks (including global AWS/Azure)")
    parser.add_argument("--cloud-only", action="store_true", help="Skip non-cloud default TCP checks; keep AWS and Azure defaults")
    parser.add_argument("--no-cloud-defaults", action="store_true", help="Skip global AWS/Azure website targets")
    parser.add_argument("--list-cloud-regions", action="store_true", help="Print supported AWS/Azure regional presets and exit")
    parser.add_argument("--aws-region", action="append", default=[], choices=sorted(AWS_REGIONS), metavar="REGION",
                        help="Add AWS regional S3 TCP:443 target; repeat (e.g. eu-central-1, us-east-1)")
    parser.add_argument("--azure-region", action="append", default=[], choices=sorted(AZURE_REGIONS), metavar="REGION",
                        help="Add Azure regional Monitor TCP:443 target; repeat (e.g. westeurope, polandcentral)")
    parser.add_argument("--ssh-host", help="Additional SSH server; checks port and SSH identification, not login")
    parser.add_argument("--ssh-port", type=int, default=22, help="Port used by --ssh-host")
    parser.add_argument("--tcp-host", help="Additional TCP endpoint hostname or IP")
    parser.add_argument("--tcp-port", type=int, default=443, help="Port used by --tcp-host")
    parser.add_argument("--http-url", help="Additional HTTP URL (http://...) to check")
    parser.add_argument("--https-url", help="Additional HTTPS URL (https://...) to check")
    parser.add_argument("--dns-server", help="DNS resolver IP address for UDP query")
    parser.add_argument("--dns-name", default="example.com", help="DNS A record to request from --dns-server")
    parser.add_argument("--icmp-host", help="Host/IP for system ping (ICMP echo)")
    parser.add_argument("--llm-provider", choices=list(LLM_PRESETS), action="append", default=[],
                        help="Add an LLM provider (openai, anthropic, kimi, mistral); repeat for multiple providers")
    parser.add_argument("--llm-all-providers", action="store_true",
                        help="Add all four LLM providers using separate environment API keys")
    parser.add_argument("--env-file", help="Optional local KEY=VALUE file holding API keys (never written to reports)")
    for provider in LLM_PRESETS:
        parser.add_argument(f"--{provider}-model", metavar="MODEL_ID",
                            help=f"Model to use for {provider} inference when --llm-mode chat")
    parser.add_argument("--anthropic-version", default="2026-10-21",
                        help="Required Anthropic API version header")
    parser.add_argument("--llm-base-url", help="OpenAI-compatible base URL ending in /v1 (e.g. https://api.openai.com/v1)")
    parser.add_argument("--llm-name", default="LLM API", help="Display label for the LLM endpoint")
    parser.add_argument("--llm-mode", choices=["models", "chat", "responses"], default="models",
                        help="GET /models (no generation); POST chat (Anthropic uses /messages); OpenAI POST /responses")
    parser.add_argument("--llm-model", help="Model ID, required for chat and responses modes")
    parser.add_argument("--llm-api-key-env", default="OPENAI_API_KEY", help="Environment variable containing the API key")
    parser.add_argument("--llm-auth-header", choices=["bearer", "api-key"], default="bearer",
                        help="Authentication header style (Bearer token or api-key)")
    parser.add_argument("--llm-timeout", type=float, default=20,
                        help="Separate timeout in seconds for LLM requests")
    parser.add_argument("--llm-max-tokens", type=int, default=32,
                        help="Maximum output tokens for LLM generation tests")
    parser.add_argument("--speedtest", action="store_true", help="Run optional download/upload test at the end (requires speedtest-cli)")
    parser.add_argument("--demo", action="store_true", help="Generate English HTML and CSV with simulated values; no network calls")
    parser.add_argument("--output", default=None, help="HTML output path; CSV will have the same stem")
    return parser



def load_env_file(filename: str) -> None:
    """Read local KEY=VALUE secrets without printing or copying them into reports.

    Existing process environment variables take precedence over file entries.
    """
    path = Path(filename)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ValueError(f"Cannot read env file {path}: {type(exc).__name__}") from None
    for lineno, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        name, sep, value = line.partition("=")
        name = name.strip()
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Invalid env-file entry at line {lineno}; expected KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
            value = value[1:-1]
        # Placeholders intentionally do not authenticate. They are demo examples.
        if value and not value.startswith("PASTE_YOUR_"):
            os.environ.setdefault(name, value)


def main(argv=None):
    parser = get_parser()
    args = parser.parse_args(argv)
    if args.env_file and not args.demo:
        try:
            load_env_file(args.env_file)
        except ValueError as exc:
            parser.error(str(exc))
    if args.list_cloud_regions:
        print("AWS S3 TCP:443 presets:")
        for code, label in AWS_REGIONS.items():
            print(f"  {code:<22} {label}")
        print("\nAzure Monitor TCP:443 presets:")
        for code, label in AZURE_REGIONS.items():
            print(f"  {code:<22} {label}")
        return 0
    if args.minutes <= 0 or args.interval <= 0 or args.timeout <= 0 or args.llm_timeout <= 0:
        parser.error("--minutes, --interval, --timeout and --llm-timeout must be positive numbers")
    if args.llm_max_tokens <= 0:
        parser.error("--llm-max-tokens must be positive")
    if args.llm_base_url:
        parsed_llm = urlsplit(args.llm_base_url)
        if (parsed_llm.scheme not in {"http", "https"} or not parsed_llm.hostname
                or parsed_llm.username or parsed_llm.password or parsed_llm.query or parsed_llm.fragment):
            parser.error("--llm-base-url must be an HTTP(S) base URL without credentials, query or fragment")
        if args.llm_mode in {"chat", "responses"} and not args.llm_model:
            parser.error("--llm-model is required when --llm-mode is chat or responses")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.llm_api_key_env):
            parser.error("--llm-api-key-env must be a valid environment variable name")
    providers = list(dict.fromkeys((list(LLM_PRESETS) if args.llm_all_providers else []) + args.llm_provider))
    if not args.demo:
        for provider in providers:
            key_name = LLM_PRESETS[provider][2]
            if not os.environ.get(key_name, "").strip() and not (provider == "kimi" and os.environ.get("MOONSHOT_API_KEY", "").strip()):
                parser.error(f"Missing API key for {provider}: set {key_name}, or use --env-file api_keys.env (Kimi also supports MOONSHOT_API_KEY)")
    if providers and args.llm_mode == "responses" and any(p != "openai" for p in providers):
        parser.error("Only OpenAI supports responses mode in the built-in presets; use --llm-mode chat for all providers")
    if args.llm_mode in {"chat", "responses"}:
        for provider in providers:
            model = getattr(args, f"{provider}_model") or (args.llm_model if len(providers) == 1 and not args.llm_base_url else None)
            if not model:
                parser.error(f"--{provider}-model is required for {provider} inference (models mode needs no model)")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.anthropic_version):
        parser.error("--anthropic-version must be YYYY-MM-DD")
    for flag, val in [("--ssh-port", args.ssh_port), ("--tcp-port", args.tcp_port)]:
        if not (1 <= val <= 65535):
            parser.error(f"{flag} must be between 1 and 65535")
    if args.all_tests and args.cloud_only:
        parser.error("--all-tests and --cloud-only cannot be combined")
    targets: list[Target] = []
    try:
        if not args.no_default_targets:
            if not args.cloud_only:
                for name, uri in DEFAULT_URLS:
                    add_unique(targets, target_from_spec(f"{name}={uri}"))
            if not args.no_cloud_defaults:
                for name, uri, provider in CLOUD_DEFAULT_URLS:
                    add_unique(targets, target_from_spec(f"{name}={uri}", provider=provider))
        aws_regions = list(dict.fromkeys(args.aws_region + (["eu-central-1", "eu-west-1"] if args.all_tests else [])))
        azure_regions = list(dict.fromkeys(args.azure_region + (["westeurope", "polandcentral"] if args.all_tests else [])))
        for region in aws_regions:
            name = f"AWS {region} (S3)"
            endpoint = f"tcp://s3.{region}.amazonaws.com:443"
            add_unique(targets, target_from_spec(f"{name}={endpoint}", provider="AWS", region=region))
        for region in azure_regions:
            name = f"Azure {region} (Monitor)"
            endpoint = f"tcp://{region}.livediagnostics.monitor.azure.com:443"
            add_unique(targets, target_from_spec(f"{name}={endpoint}", provider="Azure", region=region))
        if args.ssh_host:
            add_unique(targets, target_from_spec(f"SSH server=ssh://{args.ssh_host}:{args.ssh_port}"))
        if args.tcp_host:
            add_unique(targets, target_from_spec(f"Custom TCP=tcp://{args.tcp_host}:{args.tcp_port}"))
        http_url = args.http_url or ("http://example.com/" if args.all_tests else None)
        https_url = args.https_url or ("https://example.com/" if args.all_tests else None)
        dns_server = args.dns_server or ("1.1.1.1" if args.all_tests else None)
        icmp_host = args.icmp_host or ("8.8.8.8" if args.all_tests else None)
        if http_url:
            if not http_url.startswith("http://"):
                raise ValueError("--http-url must begin with http://")
            add_unique(targets, target_from_spec(f"HTTP website={http_url}"))
        if https_url:
            if not https_url.startswith("https://"):
                raise ValueError("--https-url must begin with https://")
            add_unique(targets, target_from_spec(f"HTTPS website={https_url}"))
        if dns_server:
            add_unique(targets, target_from_spec(f"DNS server=dns://{dns_server}/{args.dns_name}"))
        if icmp_host:
            add_unique(targets, target_from_spec(f"ICMP host=icmp://{icmp_host}"))
        for string in args.target:
            add_unique(targets, target_from_spec(string))
        for provider_name in providers:
            label, base, env = LLM_PRESETS[provider_name]
            selected_model = getattr(args, f"{provider_name}_model") or (args.llm_model if len(providers) == 1 and not args.llm_base_url else "")
            add_unique(targets, Target(name=label, protocol="llm", endpoint=base,
                                       hostname=urlsplit(base).hostname or "", port=443,
                                       provider=label, llm_mode=args.llm_mode,
                                       llm_model=selected_model,
                                       llm_key_env=env, llm_auth_header="bearer",
                                       llm_vendor=provider_name, llm_version=args.anthropic_version,
                                       llm_max_tokens=args.llm_max_tokens,
                                       llm_timeout=args.llm_timeout))
        if args.llm_base_url:
            parsed_llm = urlsplit(args.llm_base_url)
            port = parsed_llm.port or (443 if parsed_llm.scheme == "https" else 80)
            if not 1 <= port <= 65535:
                raise ValueError("LLM port must be between 1 and 65535")
            if not args.llm_name.strip():
                raise ValueError("--llm-name cannot be empty")
            add_unique(targets, Target(name=args.llm_name.strip(), protocol="llm",
                endpoint=args.llm_base_url.rstrip("/"), hostname=parsed_llm.hostname,
                port=port, provider="LLM API", llm_mode=args.llm_mode,
                llm_model=args.llm_model or "", llm_key_env=args.llm_api_key_env,
                llm_auth_header=args.llm_auth_header,
                llm_max_tokens=args.llm_max_tokens, llm_timeout=args.llm_timeout))
    except ValueError as exc:
        parser.error(str(exc))
    if not targets:
        parser.error("No targets configured; use --target or a protocol-specific option")
    if len(targets) > 30:
        parser.error("Limit is 30 targets per run to keep the report readable")
    if not args.demo and (args.timeout * sum(t.protocol != "llm" for t in targets)
                          + sum(t.llm_timeout for t in targets if t.protocol == "llm")) > args.interval:
        print("Warning: with sequential checks, failures/timeouts may make each cycle longer than --interval.", flush=True)
    html_file = Path(args.output or ("provider_report_demo_en.html" if args.demo else "provider_report.html"))
    html_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file = html_file.with_suffix(".csv")
    data = generate_demo(targets, args.interval) if args.demo else monitor(targets, args.minutes, args.interval, args.timeout)
    if not data:
        parser.error("No samples collected")
    speed = speed_test() if (args.speedtest or args.all_tests) and not args.demo else None
    write_csv(data, targets, csv_file)
    success, episodes = html_report(data, targets, speed, args.demo, args.interval, html_file)
    print(f"\nHTML report: {html_file.resolve()}\nCSV data: {csv_file.resolve()}")
    print(f"Check success rate: {success:.1f}% | All-target failure episodes: {episodes}")
    if args.demo:
        print("DEMO ONLY: Results are simulated, not measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
