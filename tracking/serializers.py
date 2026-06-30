from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import MenuItem, Order, OrderLine
from .error_handlers import log_exception
from .services import InsufficientStock, InventoryDepletionService


class CustomerSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    email = serializers.EmailField(required=False, allow_blank=True)


class OrderItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.Serializer):
    customer = CustomerSerializer(required=False)
    products = OrderItemSerializer(many=True, allow_empty=False)

    def validate_products(self, products):
        seen_product_ids: set[int] = set()
        duplicate_ids: set[int] = set()

        for item in products:
            product_id = item["product_id"]
            if product_id in seen_product_ids:
                duplicate_ids.add(product_id)
            seen_product_ids.add(product_id)

        if duplicate_ids:
            raise serializers.ValidationError(
                f"Duplicate product_id values are not allowed: {sorted(duplicate_ids)}"
            )

        return products

    @transaction.atomic
    def create(self, validated_data):
        customer = validated_data.get("customer", {})
        products = validated_data["products"]
        product_ids = [item["product_id"] for item in products]
        menu_items = MenuItem.objects.in_bulk(product_ids)

        missing_product_ids = [product_id for product_id in product_ids if product_id not in menu_items]
        if missing_product_ids:
            raise serializers.ValidationError(
                {"products": f"Unknown product_id values: {missing_product_ids}"}
            )

        order = Order.objects.create(
            customer_name=customer.get("name", ""),
            customer_phone=customer.get("phone", ""),
            customer_email=customer.get("email", ""),
            status=Order.Status.OPEN,
        )

        subtotal = Decimal("0.00")
        order_lines = []
        for item in products:
            menu_item = menu_items[item["product_id"]]
            quantity = item["quantity"]
            unit_price = Decimal(menu_item.base_price)
            line_total = unit_price * quantity
            subtotal += line_total
            order_lines.append(
                OrderLine(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        OrderLine.objects.bulk_create(order_lines)
        order.subtotal = subtotal
        order.tax = Decimal("0.00")
        order.total = subtotal
        order.save(update_fields=["subtotal", "tax", "total", "updated_at"])

        try:
            InventoryDepletionService().deplete_for_order(order)
        except InsufficientStock as exc:
            log_exception(
                exc,
                level="warning",
                message="Inventory depletion failed for order",
                order_id=order.pk,
            )
            transaction.set_rollback(True)
            raise serializers.ValidationError(
                {"detail": str(exc), "shortages": exc.shortages}
            ) from exc
        except Exception as exc:
            log_exception(
                exc,
                level="critical",
                message="Unexpected system failure while creating order",
                order_id=order.pk,
            )
            transaction.set_rollback(True)
            raise

        order.refresh_from_db()
        return order
