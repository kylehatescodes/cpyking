from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import F
from django.db.models.functions import Now
from django.db import transaction


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Ingredient(TimeStampedModel):
    class Unit(models.TextChoices):
        GRAM = "g", "Gram"
        KILOGRAM = "kg", "Kilogram"
        MILLILITER = "ml", "Milliliter"
        LITER = "l", "Liter"
        PIECE = "pc", "Piece"

    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120, db_index=True)
    unit = models.CharField(max_length=8, choices=Unit.choices)
    reorder_point = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    par_level = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="uq_ingredient_name"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class InventoryBalance(TimeStampedModel):
    ingredient = models.OneToOneField(Ingredient, on_delete=models.PROTECT, related_name="inventory_balance")
    on_hand_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    reserved_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    last_counted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["on_hand_qty"]),
            models.Index(fields=["last_counted_at"]),
        ]

    @property
    def available_qty(self) -> Decimal:
        return self.on_hand_qty - self.reserved_qty


class InventoryTransaction(TimeStampedModel):
    class TransactionType(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        CONSUMPTION = "consumption", "Consumption"
        ADJUSTMENT = "adjustment", "Adjustment"
        WASTE = "waste", "Waste"

    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="inventory_transactions")
    transaction_type = models.CharField(max_length=16, choices=TransactionType.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    reference = models.CharField(max_length=64, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["ingredient", "-created_at"]),
            models.Index(fields=["transaction_type", "-created_at"]),
        ]
        ordering = ["-created_at"]

    @transaction.atomic
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        balance, _ = InventoryBalance.objects.select_for_update().get_or_create(
            ingredient=self.ingredient,
            defaults={"on_hand_qty": Decimal("0"), "reserved_qty": Decimal("0")},
        )
        InventoryBalance.objects.filter(pk=balance.pk).update(
            on_hand_qty=F("on_hand_qty") + self.quantity_delta,
            updated_at=Now(),
        )


class MenuItem(TimeStampedModel):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120, db_index=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MenuItemIngredient(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="recipe_items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="recipe_usages")
    quantity_required = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["menu_item", "ingredient"], name="uq_menuitem_ingredient"),
        ]
        indexes = [
            models.Index(fields=["menu_item", "ingredient"]),
        ]


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PAID = "paid", "Paid"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    order_number = models.BigAutoField(primary_key=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    placed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    inventory_depleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    class Meta:
        indexes = [
            models.Index(fields=["status", "-placed_at"]),
            models.Index(fields=["-placed_at", "status"]),
        ]
        ordering = ["-placed_at"]


class OrderLine(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="order_lines")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["order", "menu_item"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="ck_orderline_quantity_positive"),
        ]


class StaffMember(TimeStampedModel):
    employee_id = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    role = models.CharField(max_length=80, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "role"]),
            models.Index(fields=["last_name", "first_name"]),
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name}"


class StaffShift(TimeStampedModel):
    class ShiftStatus(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        MISSED = "missed", "Missed"
        CANCELED = "canceled", "Canceled"

    staff_member = models.ForeignKey(StaffMember, on_delete=models.PROTECT, related_name="shifts")
    scheduled_start = models.DateTimeField(db_index=True)
    scheduled_end = models.DateTimeField(db_index=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=ShiftStatus.choices, default=ShiftStatus.SCHEDULED, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["staff_member", "scheduled_start"]),
            models.Index(fields=["status", "scheduled_start"]),
            models.Index(fields=["scheduled_start", "scheduled_end"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(scheduled_end__gt=models.F("scheduled_start")),
                name="ck_shift_scheduled_end_after_start",
            ),
        ]
        ordering = ["-scheduled_start"]


class OrderIngredientConsumption(TimeStampedModel):
    order_line = models.OneToOneField(OrderLine, on_delete=models.CASCADE, related_name="ingredient_consumption")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="order_consumptions")
    quantity_used = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        indexes = [
            models.Index(fields=["ingredient", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(quantity_used__gt=0), name="ck_consumption_quantity_positive"),
        ]
