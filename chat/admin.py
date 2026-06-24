from django.contrib import admin

from chat.models import (
    Conversation,
    FactoryLine,
    Message,
    Product,
    ProductionOrder,
    SalesRecord,
)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "content", "created_at")
    list_filter = ("role",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku")
    search_fields = ("name", "sku")


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ("product", "month", "units_sold", "revenue")
    list_filter = ("month",)
    search_fields = ("product__name",)


@admin.register(FactoryLine)
class FactoryLineAdmin(admin.ModelAdmin):
    list_display = ("name", "status")
    list_filter = ("status",)


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "line",
        "status",
        "quantity",
        "scheduled_start",
        "estimated_completion",
    )
    list_filter = ("status", "line")
    search_fields = ("product__name",)
