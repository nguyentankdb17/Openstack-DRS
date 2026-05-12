from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app import config
from app.utils.logger import get_logger

router = APIRouter(tags=["webhook"])
logger = get_logger(__name__)


def _parse_alertmanager_payload(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of firing alerts from an Alertmanager webhook payload."""
    return [a for a in body.get("alerts", []) if a.get("status") == "firing"]


@router.post("/webhook/alertmanager", status_code=status.HTTP_202_ACCEPTED)
async def alertmanager_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
) -> dict[str, Any]:
    """
    Receive Prometheus Alertmanager webhook and immediately trigger the
    decision / rebalance flow for any firing alert whose name matches
    ALERTMANAGER_TRIGGER_ALERTS (comma-separated env var).

    Alertmanager webhook_config example:
        receivers:
          - name: drs-webhook
            webhook_configs:
              - url: http://<drs-host>:8000/api/v1/webhook/alertmanager
                http_config:
                  authorization:
                    credentials: <token>   # sent as "Authorization: Bearer <token>"
                # OR use a custom header:
                # headers:
                #   X-Webhook-Token: <token>
    """
    # --- Optional token auth ---
    expected_token = getattr(config, "ALERTMANAGER_WEBHOOK_TOKEN", "")
    if expected_token:
        auth_header: str = request.headers.get("Authorization", "")
        bearer_token = auth_header.removeprefix("Bearer ").strip()
        provided = x_webhook_token or bearer_token
        if provided != expected_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")

    body: dict[str, Any] = await request.json()
    firing_alerts = _parse_alertmanager_payload(body)

    if not firing_alerts:
        logger.debug("alertmanager_webhook: no firing alerts in payload, skipping")
        return {"triggered": False, "reason": "no_firing_alerts"}

    # --- Filter by alert name whitelist ---
    trigger_alerts_raw: str = getattr(config, "ALERTMANAGER_TRIGGER_ALERTS", "")
    trigger_names: set[str] = {
        name.strip() for name in trigger_alerts_raw.split(",") if name.strip()
    }

    if trigger_names:
        matched = [a for a in firing_alerts if a.get("labels", {}).get("alertname", "") in trigger_names]
    else:
        # No filter configured → every firing alert triggers a cycle
        matched = firing_alerts

    if not matched:
        alert_names = [a.get("labels", {}).get("alertname", "unknown") for a in firing_alerts]
        logger.info(
            "alertmanager_webhook: firing alerts %s did not match trigger list %s, skipping",
            alert_names,
            sorted(trigger_names),
        )
        return {"triggered": False, "reason": "alert_not_in_trigger_list", "firing": alert_names}

    matched_names = [a.get("labels", {}).get("alertname", "unknown") for a in matched]
    logger.info(
        "alertmanager_webhook: matched alerts %s — scheduling immediate rebalance cycle",
        matched_names,
    )

    # Defer the heavy work so we return 202 immediately to Alertmanager
    background_tasks.add_task(_run_rebalance_from_alert, matched_names)

    return {"triggered": True, "alerts": matched_names}


async def _run_rebalance_from_alert(alert_names: list[str]) -> None:
    """Run the full monitor/decision cycle in a thread (same as the scheduler does)."""
    from app.scheduler.monitor_job import _monitor_cluster_sync

    logger.info("alertmanager_webhook: starting rebalance cycle triggered by alerts=%s", alert_names)
    try:
        await asyncio.to_thread(_monitor_cluster_sync)
        logger.info("alertmanager_webhook: rebalance cycle completed for alerts=%s", alert_names)
    except Exception as exc:
        logger.exception("alertmanager_webhook: rebalance cycle failed for alerts=%s: %s", alert_names, exc)
