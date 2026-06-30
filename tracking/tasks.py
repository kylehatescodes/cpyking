from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from .models import Order
from .services import KitchenDisplayQueueService


logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)


def _notify_kds(order_id: int) -> None:
    try:
        order = Order.objects.get(pk=order_id)
        KitchenDisplayQueueService().enqueue_order(order)
    except Order.DoesNotExist:
        logger.warning("Skipping KDS notification for missing order %s", order_id)


def notify_kds_async(order_id: int) -> None:
    """Dispatch KDS queue updates asynchronously."""
    _executor.submit(_notify_kds, order_id)
