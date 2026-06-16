"""
Persist named, versioned calculations ("estimates") to Azure Blob Storage using the
Container App's managed identity (no secrets). Shared team repository.

Blob layout:  <container>/<project_slug>/<UTC-timestamp>__v<version>.json
Each blob also carries lightweight blob-metadata (project, version, author, label,
saved_at, price, currency) so listing is cheap (no per-blob download).

Configured via env vars:
    ESTIMATES_ACCOUNT_URL   https://<acct>.blob.core.windows.net
    ESTIMATES_CONTAINER     estimates
When unset (e.g. local dev), store_configured() is False and the UI falls back to
JSON download/upload.
"""
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote

import streamlit as st


# ── Config ─────────────────────────────────────────────────────────────────────

def _config():
    return (
        os.environ.get("ESTIMATES_ACCOUNT_URL", "").strip(),
        os.environ.get("ESTIMATES_CONTAINER", "").strip(),
    )


def store_configured() -> bool:
    return all(_config())


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Filesystem/URL-safe slug for a customer/RFP name."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "untitled"


def next_version_from_names(names, slug: str) -> int:
    """Next version number given existing blob names under a project slug."""
    prefix = f"{slug}/"
    count = sum(1 for n in names if n.startswith(prefix) and n.endswith(".json"))
    return count + 1


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def build_payload(project, label, author, inputs, summary, version, saved_at, app_version="1.1") -> dict:
    """Assemble the JSON document stored per saved version. Pure."""
    return {
        "meta": {
            "project": project,
            "project_slug": slugify(project),
            "version": int(version),
            "label": label or "",
            "author": author or "",
            "saved_at": saved_at,
            "app_version": app_version,
            "schema": "1",
        },
        "inputs": inputs,
        "summary": summary or {},
    }


def _blob_metadata(meta: dict, summary: dict) -> dict:
    """Small ASCII-safe metadata for cheap listing (values URL-quoted)."""
    return {
        "project": quote(str(meta.get("project", "")))[:1024],
        "version": str(meta.get("version", "")),
        "author": quote(str(meta.get("author", "")))[:512],
        "label": quote(str(meta.get("label", "")))[:1024],
        "savedat": str(meta.get("saved_at", "")),
        "price": str(round(float(summary.get("selling_price", 0) or 0))),
        "currency": str(summary.get("reporting_currency", "INR")),
        "totalfte": str(summary.get("total_fte", "")),
    }


def _decode_metadata(md: dict) -> dict:
    md = md or {}
    return {
        "project": unquote(md.get("project", "")),
        "version": int(md.get("version", 0) or 0),
        "author": unquote(md.get("author", "")),
        "label": unquote(md.get("label", "")),
        "saved_at": md.get("savedat", ""),
        "price": float(md.get("price", 0) or 0),
        "currency": md.get("currency", "INR"),
        "total_fte": md.get("totalfte", ""),
    }


# ── Azure Blob operations (lazy imports; managed identity) ────────────────────────

def _container_client():
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import ContainerClient
    url, container = _config()
    cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return ContainerClient(account_url=url, container_name=container, credential=cred)


def save_estimate(project, label, author, inputs, summary) -> dict:
    """Save a new version of an estimate. Returns the stored meta (incl. _blob)."""
    cc = _container_client()
    slug = slugify(project)
    names = [b.name for b in cc.list_blobs(name_starts_with=f"{slug}/")]
    version = next_version_from_names(names, slug)
    saved_at = utc_stamp()
    payload = build_payload(project, label, author, inputs, summary, version, saved_at)
    blob_name = f"{slug}/{saved_at}__v{version}.json"
    data = json.dumps(payload, indent=2, default=str).encode("utf-8")
    cc.upload_blob(name=blob_name, data=data, overwrite=True,
                   metadata=_blob_metadata(payload["meta"], summary))
    payload["meta"]["_blob"] = blob_name
    return payload["meta"]


@st.cache_data(show_spinner=False, ttl=60)
def list_estimates() -> list:
    """All saved versions across all projects. Resilient: prefers blob metadata but
    falls back to parsing the blob name (<slug>/<ts>__v<n>.json) so it never crashes
    on a missing/None field."""
    cc = _container_client()
    # Some SDK/storage combos choke on include=["metadata"]; fall back to a plain list.
    try:
        blobs = list(cc.list_blobs(include=["metadata"]))
    except Exception:
        blobs = list(cc.list_blobs())

    out = []
    for b in blobs:
        try:
            name = getattr(b, "name", None) or ""
            if not name.endswith(".json"):
                continue
            info = _decode_metadata(getattr(b, "metadata", None))
            info["blob"] = name
            info["slug"] = name.split("/", 1)[0]
            # Derive version / timestamp from the name when metadata is absent.
            leaf = name.rsplit("/", 1)[-1]
            if "__v" in leaf:
                ts_part, v_part = leaf.rsplit("__v", 1)
                info["version"] = info["version"] or int((v_part.replace(".json", "") or "0"))
                info["saved_at"] = info["saved_at"] or ts_part
            if not info["saved_at"]:
                lm = getattr(b, "last_modified", None)
                info["saved_at"] = lm.strftime("%Y-%m-%dT%H-%M-%SZ") if lm else ""
            if not info["project"]:
                info["project"] = info["slug"]
            out.append(info)
        except Exception:
            continue
    out.sort(key=lambda x: x.get("saved_at") or "", reverse=True)
    return out


def debug_list_raw() -> dict:
    """Diagnostics: what the app actually sees in the configured container."""
    url, container = _config()
    info = {"account_url": url, "container": container}
    try:
        cc = _container_client()
        names = [getattr(b, "name", None) for b in cc.list_blobs()]
        info["raw_blob_count"] = len(names)
        info["raw_blob_names"] = names[:25]
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def load_estimate(blob_name: str) -> dict:
    """Download and parse a stored estimate JSON."""
    cc = _container_client()
    raw = cc.download_blob(blob_name).readall()
    return json.loads(raw)
