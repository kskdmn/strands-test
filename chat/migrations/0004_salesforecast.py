import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_inventoryrecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalesForecast",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("month", models.DateField()),
                ("forecast_units", models.PositiveIntegerField()),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sales_forecasts",
                        to="chat.product",
                    ),
                ),
            ],
            options={
                "ordering": ["month"],
                "unique_together": {("product", "month")},
            },
        ),
    ]
