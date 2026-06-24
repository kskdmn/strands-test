import uuid

from django.db import models


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

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SalesRecord(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sales_records",
    )
    month = models.DateField()
    units_sold = models.PositiveIntegerField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["-month"]
        unique_together = ("product", "month")

    def __str__(self) -> str:
        return f"{self.product.name} ({self.month:%Y-%m})"


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


class InventoryRecord(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    quantity_on_hand = models.PositiveIntegerField()
    reserved_quantity = models.PositiveIntegerField(default=0)
    reorder_point = models.PositiveIntegerField()
    warehouse = models.CharField(max_length=100, default="Main Warehouse")
    last_updated = models.DateTimeField()

    class Meta:
        ordering = ["product__name"]

    def __str__(self) -> str:
        return f"{self.product.name} ({self.quantity_on_hand} on hand)"


class SalesForecast(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sales_forecasts",
    )
    month = models.DateField()
    forecast_units = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["month"]
        unique_together = ("product", "month")

    def __str__(self) -> str:
        return f"{self.product.name} forecast ({self.month:%Y-%m}): {self.forecast_units}"


class ProductionOrder(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="production_orders",
    )
    line = models.ForeignKey(
        FactoryLine,
        on_delete=models.CASCADE,
        related_name="production_orders",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    quantity = models.PositiveIntegerField()
    scheduled_start = models.DateTimeField()
    estimated_completion = models.DateTimeField()

    class Meta:
        ordering = ["scheduled_start"]

    def __str__(self) -> str:
        return f"{self.product.name} on {self.line.name}"
