import uuid

from django.db import models

from chat.monthly_data import (
    effective_inventory_quantity,
    effective_production_quantity,
    effective_sales_units,
    is_past_month,
)


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return str(self.id)


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"


class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    sku = models.CharField(max_length=50, unique=True)
    reorder_point = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    warehouse = models.CharField(max_length=100, default="Main Warehouse")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SalesMonthlyData(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sales_monthly_data",
    )
    month = models.DateField()
    actual_units = models.PositiveIntegerField(null=True, blank=True)
    actual_revenue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    plan_units = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month"]
        unique_together = ("product", "month")

    def __str__(self) -> str:
        return f"{self.product.name} sales ({self.month:%Y-%m})"

    @property
    def data_kind(self) -> str:
        return "actual" if is_past_month(self.month) else "plan"

    @property
    def effective_units(self) -> int | None:
        return effective_sales_units(self.actual_units, self.plan_units, self.month)


class InventoryMonthlyData(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory_monthly_data",
    )
    month = models.DateField()
    actual_quantity = models.PositiveIntegerField(null=True, blank=True)
    plan_quantity = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-month"]
        unique_together = ("product", "month")

    def __str__(self) -> str:
        return f"{self.product.name} inventory ({self.month:%Y-%m})"

    @property
    def data_kind(self) -> str:
        return "actual" if is_past_month(self.month) else "plan"

    @property
    def effective_quantity(self) -> int | None:
        return effective_inventory_quantity(
            self.actual_quantity,
            self.plan_quantity,
            self.month,
        )


class ProductionMonthlyData(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="production_monthly_data",
    )
    month = models.DateField()
    actual_quantity = models.PositiveIntegerField(null=True, blank=True)
    plan_quantity = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-month"]
        unique_together = ("product", "month")

    def __str__(self) -> str:
        return f"{self.product.name} production ({self.month:%Y-%m})"

    @property
    def data_kind(self) -> str:
        return "actual" if is_past_month(self.month) else "plan"

    @property
    def effective_quantity(self) -> int | None:
        return effective_production_quantity(
            self.actual_quantity,
            self.plan_quantity,
            self.month,
        )


class FactoryLine(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        MAINTENANCE = "maintenance", "Maintenance"
        IDLE = "idle", "Idle"

    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
