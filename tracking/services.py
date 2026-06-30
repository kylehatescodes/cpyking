from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import InventoryBalance, MenuItemIngredient, Order


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

        inventory_rows = (
            InventoryBalance.objects.select_for_update()
            .filter(ingredient_id__in=required_by_ingredient.keys())
            .values("ingredient_id", "on_hand_qty")
        )
        available_by_ingredient = {row["ingredient_id"]: Decimal(row["on_hand_qty"]) for row in inventory_rows}

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
