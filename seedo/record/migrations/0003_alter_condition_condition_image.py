# Generated by Django 5.0.6 on 2024-07-18 02:38

import record.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("record", "0002_alter_accident_accident_video")]

    operations = [
        migrations.AlterField(model_name="condition", name="condition_image", field=models.ImageField(upload_to=record.models.upload_to_img))
    ]
