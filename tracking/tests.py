from __future__ import annotations

from decimal import Decimal
from queue import Queue
from threading import Event, Thread
from unittest.mock import patch

from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from rest_framework.exceptions import ValidationError

from .models import Ingredient, InventoryBalance, MenuItem, MenuItemIngredient, Order, OrderLine
from .serializers import OrderSerializer
from .services import InsufficientStock, InventoryDepletionService


class OrderSerializerTests(TestCase):
    def setUp(self) -> None:
        self.ingredient = Ingredient.objects.create(
            sku="ING-001",
            name="Burger Patty",
            unit=Ingredient.Unit.PIECE,
            reorder_point=Decimal("5.000"),
            par_level=Decimal("20.000"),
            is_active=True,
        )
        self.balance = InventoryBalance.objects.create(
            ingredient=self.ingredient,
            on_hand_qty=Decimal("10.000"),
            reserved_qty=Decimal("0.000"),
        )
        self.menu_item = MenuItem.objects.create(
            sku="MENU-001",
            name="Cheeseburger",
            base_price=Decimal("7.50"),
            is_active=True,
        )
        MenuItemIngredient.objects.create(
            menu_item=self.menu_item,
            ingredient=self.ingredient,
            quantity_required=Decimal("2.000"),
        )

    def test_successful_order_creates_order_and_depletes_inventory(self) -> None:
        serializer = OrderSerializer(
            data={
                "customer": {
                    "name": "Ava",
                    "phone": "555-0100",
                    "email": "ava@example.com",
                },
                "products": [
                    {"product_id": self.menu_item.pk, "quantity": 2},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tracking.signals.notify_kds_async"), self.captureOnCommitCallbacks(execute=True):
            order = serializer.save()

        order.refresh_from_db()
        self.balance.refresh_from_db()

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.customer_name, "Ava")
        self.assertEqual(order.total, Decimal("15.00"))
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(self.balance.on_hand_qty, Decimal("6.000"))
        self.assertEqual(order.inventory_depleted_at is not None, True)

    def test_order_fails_when_stock_is_insufficient(self) -> None:
        self.balance.on_hand_qty = Decimal("1.000")
        self.balance.save(update_fields=["on_hand_qty"])

        serializer = OrderSerializer(
            data={
                "customer": {"name": "Ben"},
                "products": [
                    {"product_id": self.menu_item.pk, "quantity": 1},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tracking.signals.notify_kds_async"), self.assertRaises(ValidationError) as exc_info:
            serializer.save()

        self.assertIn("detail", exc_info.exception.detail)
        self.assertEqual(Order.objects.count(), 0)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand_qty, Decimal("1.000"))


@skipUnlessDBFeature("has_select_for_update")
class InventoryDepletionServiceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.ingredient = Ingredient.objects.create(
            sku="ING-100",
            name="Chicken",
            unit=Ingredient.Unit.PIECE,
            reorder_point=Decimal("2.000"),
            par_level=Decimal("10.000"),
            is_active=True,
        )
        self.balance = InventoryBalance.objects.create(
            ingredient=self.ingredient,
            on_hand_qty=Decimal("1.000"),
            reserved_qty=Decimal("0.000"),
        )
        self.menu_item = MenuItem.objects.create(
            sku="MENU-100",
            name="Chicken Sandwich",
            base_price=Decimal("8.00"),
            is_active=True,
        )
        MenuItemIngredient.objects.create(
            menu_item=self.menu_item,
            ingredient=self.ingredient,
            quantity_required=Decimal("1.000"),
        )

    def _create_order(self) -> Order:
        with patch("tracking.signals.notify_kds_async"):
            order = Order.objects.create(
                customer_name="Concurrent Customer",
                customer_phone="555-0199",
                customer_email="concurrent@example.com",
                status=Order.Status.OPEN,
            )
        OrderLine.objects.create(
            order=order,
            menu_item=self.menu_item,
            quantity=1,
            unit_price=self.menu_item.base_price,
            line_total=self.menu_item.base_price,
        )
        return order

    def test_concurrent_depletion_waits_for_inventory_lock(self) -> None:
        second_order = self._create_order()

        lock_acquired = Event()
        release_lock = Event()
        contender_started = Event()
        results: Queue[str] = Queue()

        def locker() -> None:
            close_old_connections()
            with transaction.atomic():
                balance = InventoryBalance.objects.select_for_update().get(pk=self.balance.pk)
                balance.on_hand_qty = Decimal("0.000")
                balance.save(update_fields=["on_hand_qty"])
                lock_acquired.set()
                release_lock.wait(timeout=5)

        def contender() -> None:
            close_old_connections()
            lock_acquired.wait(timeout=5)
            contender_started.set()
            try:
                InventoryDepletionService().deplete_for_order(second_order)
            except InsufficientStock:
                results.put("insufficient")
            else:
                results.put("success")
            finally:
                release_lock.set()

        locker_thread = Thread(target=locker, daemon=True)
        contender_thread = Thread(target=contender, daemon=True)
        locker_thread.start()
        contender_thread.start()

        self.assertTrue(contender_started.wait(timeout=5))
        self.assertTrue(results.empty())

        release_lock.set()
        locker_thread.join(timeout=5)
        contender_thread.join(timeout=5)

        self.assertFalse(locker_thread.is_alive())
        self.assertFalse(contender_thread.is_alive())
        self.assertEqual(results.get_nowait(), "insufficient")

        self.balance.refresh_from_db()
        second_order.refresh_from_db()
        self.assertEqual(self.balance.on_hand_qty, Decimal("0.000"))
        self.assertIsNone(second_order.inventory_depleted_at)
        self.assertEqual(first_order.inventory_depleted_at, None)
