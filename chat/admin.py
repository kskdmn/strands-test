from django.contrib import admin

from chat.models import (
    Conversation,
    FactoryLine,
    InventoryMonthlyData,
    Message,
    Product,
    ProductionMonthlyData,
    SalesMonthlyData,
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
    list_display = ("name", "sku", "warehouse", "reorder_point", "reserved_quantity")
    search_fields = ("name", "sku")


@admin.register(SalesMonthlyData)
class SalesMonthlyDataAdmin(admin.ModelAdmin):
    list_display = ("product", "month", "actual_units", "plan_units", "updated_at")
    list_filter = ("month",)
    search_fields = ("product__name",)


@admin.register(InventoryMonthlyData)
class InventoryMonthlyDataAdmin(admin.ModelAdmin):
    list_display = ("product", "month", "actual_quantity", "plan_quantity")
    list_filter = ("month",)
    search_fields = ("product__name",)


@admin.register(ProductionMonthlyData)
class ProductionMonthlyDataAdmin(admin.ModelAdmin):
    list_display = ("product", "month", "actual_quantity", "plan_quantity")
    list_filter = ("month",)
    search_fields = ("product__name",)


@admin.register(FactoryLine)
class FactoryLineAdmin(admin.ModelAdmin):
    list_display = ("name", "status")
    list_filter = ("status",)
