from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [("accounts", "0003_refreshtoken")]

    operations = [migrations.AddField(model_name="refreshtoken", name="token_blacklist", field=models.BooleanField(default=False))]
