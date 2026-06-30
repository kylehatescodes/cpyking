from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import MenuItem, Order, OrderLine
from .services import InsufficientStock, InventoryDepletionService


class OrderProcessingView(View):
    http_method_names = ["post"]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

        try:
            order = self._process_order(payload)
        except InsufficientStock as exc:
            return JsonResponse(
                {
                    "detail": str(exc),
                    "shortages": exc.shortages,
                },
                status=409,
            )
        except ValueError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)

        return JsonResponse(
            {
                "detail": "Order processed successfully.",
                "order_number": order.order_number,
                "status": order.status,
                "total": str(order.total),
            },
            status=201,
        )

    @transaction.atomic
    def _process_order(self, payload: dict) -> Order:
        customer = payload.get("customer") or {}
        products = payload.get("products") or []

        if not isinstance(customer, dict):
            raise ValueError("customer must be an object.")
        if not isinstance(products, list) or not products:
            raise ValueError("products must be a non-empty list.")

        customer_name = str(customer.get("name", "")).strip()
        customer_phone = str(customer.get("phone", "")).strip()
        customer_email = str(customer.get("email", "")).strip()

        order = Order.objects.create(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            status=Order.Status.OPEN,
        )

        menu_item_ids: list[int] = []
        normalized_products: list[dict] = []
        for product in products:
            if not isinstance(product, dict):
                raise ValueError("Each product must be an object.")
            try:
                menu_item_id = int(product["menu_item_id"])
                quantity = int(product["quantity"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Each product requires menu_item_id and quantity.") from exc
            if quantity <= 0:
                raise ValueError("Product quantity must be greater than zero.")
            menu_item_ids.append(menu_item_id)
            normalized_products.append({"menu_item_id": menu_item_id, "quantity": quantity})

        menu_items = MenuItem.objects.in_bulk(menu_item_ids)
        missing_ids = [menu_item_id for menu_item_id in menu_item_ids if menu_item_id not in menu_items]
        if missing_ids:
            raise ValueError(f"Unknown menu item ids: {missing_ids}")

        subtotal = Decimal("0.00")
        order_lines: list[OrderLine] = []
        for product in normalized_products:
            menu_item = menu_items[product["menu_item_id"]]
            quantity = product["quantity"]
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

        InventoryDepletionService().deplete_for_order(order)
        order.refresh_from_db()
        return order
