from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import InventoryBalance, MenuItemIngredient, Order


logger = logging.getLogger(__name__)


class InsufficientStock(Exception):
    """Raised when one or more ingredients cannot satisfy an order."""

    def __init__(self, message: str, shortages: dict[str, Decimal] | None = None) -> None:
        super().__init__(message)
        self.shortages = shortages or {}


@dataclass(frozen=True)
class InventoryShortage:
    ingredient_id: int
    ingredient_name: str
    required_qty: Decimal
    available_qty: Decimal


class InventoryDepletionService:
    """Depletes ingredient inventory for a saved order."""

    @transaction.atomic
    def deplete_for_order(self, order: Order) -> None:
        order = Order.objects.select_for_update().prefetch_related("lines__menu_item").get(pk=order.pk)
        if order.inventory_depleted_at is not None:
            return

        order_lines = list(order.lines.all())
        if not order_lines:
            return

        quantities_by_menu_item: dict[int, Decimal] = {
            line.menu_item_id: Decimal(line.quantity) for line in order_lines
        }
        required_by_ingredient: dict[int, Decimal] = {}
        ingredient_names: dict[int, str] = {}

        recipe_rows = (
            MenuItemIngredient.objects.filter(menu_item_id__in=quantities_by_menu_item.keys())
            .select_related("ingredient", "menu_item")
            .values("ingredient_id", "ingredient__name", "menu_item_id", "quantity_required")
        )

        if not recipe_rows.exists():
            return

        for row in recipe_rows:
            menu_item_quantity = quantities_by_menu_item.get(row["menu_item_id"], Decimal("0"))
            required_qty = Decimal(row["quantity_required"]) * menu_item_quantity
            ingredient_id = row["ingredient_id"]
            required_by_ingredient[ingredient_id] = required_by_ingredient.get(ingredient_id, Decimal("0")) + required_qty
            ingredient_names[ingredient_id] = row["ingredient__name"]

        inventory_balances = list(
            InventoryBalance.objects.select_for_update()
            .select_related("ingredient")
            .filter(ingredient_id__in=required_by_ingredient.keys())
        )
        available_by_ingredient = {
            balance.ingredient_id: Decimal(balance.on_hand_qty)
            for balance in inventory_balances
        }

        shortages: list[InventoryShortage] = []
        for ingredient_id, required_qty in required_by_ingredient.items():
            available_qty = available_by_ingredient.get(ingredient_id, Decimal("0"))
            if available_qty < required_qty:
                shortages.append(
                    InventoryShortage(
                        ingredient_id=ingredient_id,
                        ingredient_name=ingredient_names.get(ingredient_id, str(ingredient_id)),
                        required_qty=required_qty,
                        available_qty=available_qty,
                    )
                )

        if shortages:
            shortage_summary = {
                item.ingredient_name: item.required_qty - item.available_qty
                for item in shortages
            }
            raise InsufficientStock("Insufficient stock for order depletion.", shortage_summary)

        for ingredient_id, required_qty in required_by_ingredient.items():
            InventoryBalance.objects.filter(ingredient_id=ingredient_id).update(
                on_hand_qty=F("on_hand_qty") - required_qty,
            )

        Order.objects.filter(pk=order.pk, inventory_depleted_at__isnull=True).update(
            inventory_depleted_at=timezone.now(),
        )


class KitchenDisplayQueueService:
    """Builds and publishes a KDS payload outside of the order save path."""

    def enqueue_order(self, order: Order) -> dict[str, Any]:
        order = Order.objects.prefetch_related("lines__menu_item").get(pk=order.pk)
        payload = {
            "order_number": order.order_number,
            "placed_at": order.placed_at.isoformat(),
            "status": order.status,
            "items": [
                {
                    "menu_item_id": line.menu_item_id,
                    "menu_item_name": line.menu_item.name,
                    "quantity": line.quantity,
                    "line_total": str(line.line_total),
                }
                for line in order.lines.all()
            ],
        }
        logger.info("Queued order %s for KDS", order.order_number, extra={"kds_payload": payload})
        return payload
