# Generated by Django 5.0.6 on 2024-06-27 04:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("matching", "0001_initial")]

    operations = [
        migrations.AddField(model_name="userrequest", name="is_accepted", field=models.BooleanField(default=False)),
        migrations.AlterField(model_name="userrequest", name="verification_code", field=models.CharField(blank=True, max_length=6, null=True)),
        migrations.DeleteModel(name="UserGroup"),
    ]