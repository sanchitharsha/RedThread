"""
AWS S3 archival integration — persist investigation artifacts to S3.
Sponsor prize qualification: AWS.

Archives a completed investigation run (events, graph, report, evidence,
captures) to an S3 bucket as a single prefixed object set.

Storage layout in S3:
  s3://<bucket>/redthread/<run_id>/meta.json
  s3://<bucket>/redthread/<run_id>/events.jsonl
  s3://<bucket>/redthread/<run_id>/graph.json
  s3://<bucket>/redthread/<run_id>/report.json
  s3://<bucket>/redthread/<run_id>/results.json
  s3://<bucket>/redthread/<run_id>/evidence/<evidence_id>.json
  s3://<bucket>/redthread/<run_id>/manifest.json

Requires env vars:
  AWS_ACCESS_KEY_ID     — IAM key
  AWS_SECRET_ACCESS_KEY — IAM secret
  AWS_REGION            — e.g. us-east-1
  S3_BUCKET             — target bucket name
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from backend import store

logger = logging.getLogger(__name__)


def _get_config() -> dict:
    return {
        "bucket": os.environ.get("S3_BUCKET", ""),
        "region": os.environ.get("AWS_REGION", "us-east-1"),
        "prefix": os.environ.get("S3_PREFIX", "redthread"),
    }


def is_configured() -> bool:
    """Check if AWS S3 credentials and bucket are set."""
    return bool(
        os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
        and os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
        and os.environ.get("S3_BUCKET", "").strip()
    )


def _s3_client():
    """Create an S3 client using env credentials."""
    config = _get_config()
    return boto3.client(
        "s3",
        region_name=config["region"],
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def _upload_json(client, bucket: str, key: str, data: Any) -> None:
    """Upload a JSON-serializable object to S3."""
    body = json.dumps(data, default=str, indent=2)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )


def archive_run(run_id: str) -> dict:
    """
    Archive a completed investigation run to S3.

    Returns a manifest dict with S3 keys and metadata.
    Raises RuntimeError on configuration or upload errors.
    """
    config = _get_config()
    if not config["bucket"]:
        raise RuntimeError(
            "S3_BUCKET not set. Set it in .env to enable AWS archival."
        )

    if not store.run_exists(run_id):
        raise RuntimeError(f"Run '{run_id}' not found locally.")

    try:
        client = _s3_client()
    except NoCredentialsError:
        raise RuntimeError(
            "AWS credentials not configured. "
            "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env."
        )

    prefix = f"{config['prefix']}/{run_id}"
    bucket = config["bucket"]
    uploaded_keys = []

    try:
        # 1. Meta
        meta = store.load_meta(run_id)
        if meta:
            key = f"{prefix}/meta.json"
            _upload_json(client, bucket, key, meta)
            uploaded_keys.append(key)

        # 2. Events
        events = store.load_events(run_id)
        if events:
            key = f"{prefix}/events.jsonl"
            body = "\n".join(e.model_dump_json() for e in events)
            client.put_object(
                Bucket=bucket, Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/x-ndjson",
            )
            uploaded_keys.append(key)

        # 3. Graph
        graph = store.load_graph(run_id)
        if graph:
            key = f"{prefix}/graph.json"
            _upload_json(client, bucket, key, graph.model_dump(mode="json"))
            uploaded_keys.append(key)

        # 4. Report
        report = store.load_report(run_id)
        if report:
            key = f"{prefix}/report.json"
            _upload_json(client, bucket, key, report.model_dump(mode="json"))
            uploaded_keys.append(key)

        # 5. Results
        results = store.load_results(run_id)
        if results:
            key = f"{prefix}/results.json"
            _upload_json(
                client, bucket, key,
                [r.model_dump(mode="json") for r in results],
            )
            uploaded_keys.append(key)

        # 6. Evidence files
        evidence = store.load_all_evidence(run_id)
        for eid, ev in evidence.items():
            key = f"{prefix}/evidence/{eid}.json"
            _upload_json(client, bucket, key, ev.model_dump(mode="json"))
            uploaded_keys.append(key)

        # 7. Manifest
        manifest = {
            "run_id": run_id,
            "bucket": bucket,
            "prefix": prefix,
            "region": config["region"],
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(uploaded_keys),
            "keys": uploaded_keys,
        }
        manifest_key = f"{prefix}/manifest.json"
        _upload_json(client, bucket, manifest_key, manifest)
        uploaded_keys.append(manifest_key)

        logger.info(
            "Archived run %s → s3://%s/%s (%d files)",
            run_id, bucket, prefix, len(uploaded_keys),
        )

        return manifest

    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        raise RuntimeError(f"AWS S3 error ({code}): {msg}")


def archive_run_offline(run_id: str) -> dict:
    """
    Offline fallback: returns what would be archived without actually
    uploading. Used when AWS credentials are not set (demo mode).
    """
    if not store.run_exists(run_id):
        raise RuntimeError(f"Run '{run_id}' not found locally.")

    config = _get_config()
    prefix = f"{config['prefix']}/{run_id}"

    files = []
    if store.load_meta(run_id):
        files.append(f"{prefix}/meta.json")
    events = store.load_events(run_id)
    if events:
        files.append(f"{prefix}/events.jsonl")
    if store.load_graph(run_id):
        files.append(f"{prefix}/graph.json")
    if store.load_report(run_id):
        files.append(f"{prefix}/report.json")
    results = store.load_results(run_id)
    if results:
        files.append(f"{prefix}/results.json")
    evidence = store.load_all_evidence(run_id)
    for eid in evidence:
        files.append(f"{prefix}/evidence/{eid}.json")
    files.append(f"{prefix}/manifest.json")

    return {
        "run_id": run_id,
        "bucket": config["bucket"] or "(not configured)",
        "prefix": prefix,
        "region": config["region"],
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "keys": files,
        "offline": True,
    }


def list_archived_runs() -> list[dict]:
    """
    List all archived runs in S3.
    Returns a list of manifest summaries.
    """
    if not is_configured():
        return []

    config = _get_config()
    client = _s3_client()

    try:
        paginator = client.get_paginator("list_objects_v2")
        prefix = f"{config['prefix']}/"
        runs = set()

        for page in paginator.paginate(
            Bucket=config["bucket"], Prefix=prefix, Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                run_id = cp["Prefix"].rstrip("/").split("/")[-1]
                runs.add(run_id)

        return [{"run_id": r, "bucket": config["bucket"]} for r in sorted(runs)]

    except ClientError as e:
        logger.error("Failed to list S3 archives: %s", e)
        return []
