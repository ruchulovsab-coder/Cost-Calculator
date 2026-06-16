"""
Load the rate card from Azure Blob Storage using the Container App's managed
identity (no connection string / secret). Configured entirely via env vars:

    RATECARD_ACCOUNT_URL   e.g. https://myacct.blob.core.windows.net
    RATECARD_CONTAINER     e.g. ratecards
    RATECARD_BLOB          e.g. genus_rate_card.xlsx

When these aren't set (e.g. local dev) the app falls back to manual upload.
"""
import os
import streamlit as st


def _config():
    return (
        os.environ.get("RATECARD_ACCOUNT_URL", "").strip(),
        os.environ.get("RATECARD_CONTAINER", "").strip(),
        os.environ.get("RATECARD_BLOB", "").strip(),
    )


def blob_configured() -> bool:
    """True when all three RATECARD_* env vars are present."""
    return all(_config())


@st.cache_data(show_spinner="Loading rate card from Azure Blob…", ttl=600)
def load_rate_card_bytes(account_url: str, container: str, blob: str) -> bytes:
    """Download the rate-card blob via DefaultAzureCredential (managed identity in
    Azure; az-CLI/login locally). Cached for 10 min and keyed on the blob location."""
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobClient

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    client = BlobClient(account_url=account_url, container_name=container,
                        blob_name=blob, credential=credential)
    return client.download_blob().readall()


def fetch_rate_card_bytes():
    """Return the rate-card bytes from Blob, or raise. Returns None if not configured."""
    account_url, container, blob = _config()
    if not (account_url and container and blob):
        return None
    return load_rate_card_bytes(account_url, container, blob)
