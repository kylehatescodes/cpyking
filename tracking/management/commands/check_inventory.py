from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import DecimalField, Value
from django.db.models.functions import Coalesce

from tracking.models import Ingredient


class Command(BaseCommand):
    help = "Print the current on_hand_qty for all ingredients."

    def handle(self, *args, **options):
        ingredients = (
            Ingredient.objects.annotate(
                current_on_hand_qty=Coalesce(
                    "inventory_balance__on_hand_qty",
                    Value(Decimal("0.000"), output_field=DecimalField(max_digits=14, decimal_places=3)),
                )
            )
            .order_by("name")
            .values("sku", "name", "current_on_hand_qty")
        )

        if not ingredients:
            self.stdout.write(self.style.WARNING("No ingredients found."))
            return

        self.stdout.write(self.style.SUCCESS("Current inventory levels:"))
        for ingredient in ingredients:
            self.stdout.write(
                f"{ingredient['sku']} | {ingredient['name']} | on_hand_qty={ingredient['current_on_hand_qty']}"
            )
