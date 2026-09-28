import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0002_availability_slots"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="availability_slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservations",
                to="reservations.availabilityslot",
            ),
        ),
    ]
