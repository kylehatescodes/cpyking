from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order
from .services import InventoryDepletionService


@receiver(post_save, sender=Order)
def deplete_inventory_on_order_save(sender, instance: Order, created: bool, **kwargs) -> None:
    InventoryDepletionService().deplete_for_order(instance)
