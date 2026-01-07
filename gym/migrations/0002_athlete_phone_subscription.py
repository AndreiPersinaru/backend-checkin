# Generated migration for Athlete phone_number and subscription_active fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='athlete',
            name='phone_number',
            field=models.CharField(max_length=10, unique=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='athlete',
            name='subscription_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='athlete',
            name='name',
            field=models.CharField(max_length=100),
        ),
    ]
