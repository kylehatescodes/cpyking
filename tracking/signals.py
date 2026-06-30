from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order
from .tasks import notify_kds_async


@receiver(post_save, sender=Order)
def update_kds_queue_on_order_create(sender, instance: Order, created: bool, **kwargs) -> None:
    if not created:
        return

    transaction.on_commit(lambda: notify_kds_async(instance.pk))
