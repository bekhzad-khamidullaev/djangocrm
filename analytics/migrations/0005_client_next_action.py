from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0004_forecasts'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientNextActionForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_id', models.BigIntegerField(db_index=True)),
                ('suggested_action', models.CharField(max_length=64)),
                ('probability', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Client next action forecast',
                'verbose_name_plural': 'Client next action forecasts',
                'unique_together': {('company_id', 'suggested_action')},
            },
        ),
    ]
