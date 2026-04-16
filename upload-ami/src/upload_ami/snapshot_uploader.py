"""Upload raw disk images to EBS snapshots via EBS Direct APIs.

Uses PutSnapshotBlock to write 512 KiB blocks in parallel.  Retries
are handled by boto3's adaptive retry mode.
"""

import base64
import hashlib
import logging
import math
import os
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import botocore.config
from mypy_boto3_ebs.client import EBSClient

log = logging.getLogger(__name__)

BLOCK_SIZE = 512 * 1024  # Fixed by EBS Direct API.
GIB = 1024**3


def upload_snapshot(
    path: str | Path,
    *,
    region: str,
    volume_size_gib: int | None = None,
    description: str | None = None,
    tags: dict[str, str] | None = None,
    client_token: str | None = None,
    workers: int = 64,
    timeout_minutes: int = 60,
) -> str:
    """Upload a raw disk image to a new EBS snapshot.

    Returns the snapshot ID on success.  On failure the incomplete
    snapshot is deleted and the exception is re-raised.

    If *client_token* is provided and a snapshot with that token already
    exists in completed state, returns immediately (idempotent retry).
    If *tags* are provided they are set atomically at snapshot creation.
    """
    file_path = Path(path)
    file_size = file_path.stat().st_size
    block_count = math.ceil(file_size / BLOCK_SIZE)
    if volume_size_gib is None:
        volume_size_gib = max(math.ceil(file_size / GIB), 1)

    client = _create_client(region, workers)
    t0 = time.monotonic()

    snapshot_id, status = _start_snapshot(
        client, volume_size_gib, description, timeout_minutes, tags, client_token
    )

    if status == "completed":
        log.info("Snapshot %s already completed (idempotent)", snapshot_id)
        return snapshot_id

    if status != "pending":
        raise RuntimeError(
            f"StartSnapshot returned unexpected status {status!r} for {snapshot_id}"
        )

    log.info(
        "Started %s: %d blocks, %d GiB, %d workers",
        snapshot_id,
        block_count,
        volume_size_gib,
        workers,
    )

    try:
        _upload_blocks(
            file_path,
            snapshot_id,
            block_count,
            file_size,
            client,
            workers,
        )
        status = _complete_snapshot(client, snapshot_id, block_count)
        if status == "error":
            raise RuntimeError(f"CompleteSnapshot returned error for {snapshot_id}")
        if status != "completed":
            _wait_for_snapshot(region, snapshot_id)
    except Exception:
        elapsed = time.monotonic() - t0
        log.error("Upload failed after %.1fs for %s", elapsed, snapshot_id)
        _cleanup_snapshot(region, snapshot_id)
        raise

    elapsed = time.monotonic() - t0
    throughput = (file_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0.0
    log.info("Completed %s: %.1fs, %.1f MiB/s", snapshot_id, elapsed, throughput)
    return snapshot_id


def _create_client(region: str, max_connections: int) -> EBSClient:
    """Create a boto3 EBS client with adaptive retry and a sized connection pool."""
    cfg = botocore.config.Config(
        retries={"mode": "adaptive"},
        connect_timeout=5,
        read_timeout=12,
        max_pool_connections=max_connections,
        tcp_keepalive=True,
    )
    return boto3.client("ebs", region_name=region, config=cfg)


def _start_snapshot(
    client: EBSClient,
    volume_size_gib: int,
    description: str | None,
    timeout_minutes: int,
    tags: dict[str, str] | None,
    client_token: str | None,
) -> tuple[str, str]:
    """Start a snapshot, returning (snapshot_id, status).

    Status is 'pending' for new snapshots, 'completed' for idempotent
    retries where the snapshot already finished.
    """
    token = client_token or str(uuid.uuid4())
    kwargs: dict[str, object] = {
        "VolumeSize": volume_size_gib,
        "Timeout": timeout_minutes,
        "ClientToken": token,
    }
    if description is not None:
        kwargs["Description"] = description
    if tags:
        kwargs["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]
    resp = client.start_snapshot(**kwargs)  # type: ignore[arg-type]
    return resp["SnapshotId"], resp["Status"]


def _complete_snapshot(client: EBSClient, snapshot_id: str, block_count: int) -> str:
    """Complete the snapshot.

    Returns the snapshot status from the CompleteSnapshot response.
    Retries are handled by boto3's adaptive retry mode.
    """
    resp = client.complete_snapshot(
        SnapshotId=snapshot_id, ChangedBlocksCount=block_count
    )
    return resp["Status"]


def _put_block(
    client: EBSClient, snapshot_id: str, block_index: int, data: bytes
) -> None:
    checksum = base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
    client.put_snapshot_block(
        SnapshotId=snapshot_id,
        BlockIndex=block_index,
        BlockData=data,
        DataLength=len(data),
        Checksum=checksum,
        ChecksumAlgorithm="SHA256",
    )


def _cleanup_snapshot(region: str, snapshot_id: str) -> None:
    """Check snapshot state and clean up if appropriate.

    If the snapshot reached 'completed' despite the error (e.g. waiter
    timeout on a slow finalization), log a warning but do not delete it.
    If it is in 'error' or still 'pending', delete it.
    """
    try:
        ec2 = boto3.client("ec2", region_name=region)
        resp = ec2.describe_snapshots(SnapshotIds=[snapshot_id])
        if resp["Snapshots"]:
            state = resp["Snapshots"][0].get("State", "")
            if state == "completed":
                log.warning(
                    "Snapshot %s is completed despite error; not deleting",
                    snapshot_id,
                )
                return
            log.info("Snapshot %s in state %r, deleting", snapshot_id, state)
        ec2.delete_snapshot(SnapshotId=snapshot_id)
    except Exception as exc:
        log.warning("Failed to clean up %s: %s", snapshot_id, exc)


def _wait_for_snapshot(region: str, snapshot_id: str) -> None:
    """Wait for the snapshot to reach 'completed' state in EC2.

    CompleteSnapshot starts an async workflow; the EC2 snapshot may still
    be 'pending' briefly.  Poll every 2 seconds for up to 60 seconds.
    """
    ec2 = boto3.client("ec2", region_name=region)
    ec2.get_waiter("snapshot_completed").wait(
        SnapshotIds=[snapshot_id],
        WaiterConfig={"Delay": 2, "MaxAttempts": 30},
    )


def _read_block(fd: int, block_index: int, file_size: int) -> bytes:
    """Read one 512 KiB block via pread, zero-padding the last block."""
    offset = block_index * BLOCK_SIZE
    to_read = min(BLOCK_SIZE, file_size - offset)
    data = os.pread(fd, to_read, offset)
    if len(data) < to_read:
        raise OSError(
            f"Short read at block {block_index}: expected {to_read}, got {len(data)}"
        )
    if len(data) < BLOCK_SIZE:
        data += b"\x00" * (BLOCK_SIZE - len(data))
    return data


def _upload_blocks(
    path: Path,
    snapshot_id: str,
    block_count: int,
    file_size: int,
    client: EBSClient,
    workers: int,
) -> None:
    """Upload all blocks in parallel. Retries are handled by boto3."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        failed: dict[int, BaseException] = {}
        failed_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures: dict[Future[None], int] = {}
            for idx in range(block_count):
                with failed_lock:
                    if failed:
                        break
                f = pool.submit(
                    _upload_one_block,
                    fd,
                    snapshot_id,
                    idx,
                    file_size,
                    client,
                )
                futures[f] = idx

            for f in as_completed(futures):
                exc = f.exception()
                if exc is not None:
                    with failed_lock:
                        failed[futures[f]] = exc
    finally:
        os.close(fd)

    if failed:
        first_idx = min(failed)
        raise RuntimeError(
            f"{len(failed)} block(s) failed; "
            f"first failure at block {first_idx}: {failed[first_idx]}"
        )


def _upload_one_block(
    fd: int,
    snapshot_id: str,
    block_index: int,
    file_size: int,
    client: EBSClient,
) -> None:
    """Upload a single block. Retries are handled by boto3."""
    data = _read_block(fd, block_index, file_size)
    _put_block(client, snapshot_id, block_index, data)
