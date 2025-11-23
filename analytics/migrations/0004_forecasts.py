from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0003_bistat'),
        ('crm', '0012_messenger_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ForecastPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('series_key', models.CharField(max_length=64, db_index=True)),
                ('date', models.DateField(db_index=True)),
                ('yhat', models.FloatField()),
                ('yhat_lower', models.FloatField(null=True, blank=True)),
                ('yhat_upper', models.FloatField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Forecast point',
                'verbose_name_plural': 'Forecast points',
                'unique_together': {('series_key', 'date')},
            },
        ),
        migrations.CreateModel(
            name='NextActionForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deal_id', models.BigIntegerField(db_index=True)),
                ('suggested_action', models.CharField(max_length=64)),
                ('probability', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Next action forecast',
                'verbose_name_plural': 'Next action forecasts',
                'unique_together': {('deal_id', 'suggested_action')},
            },
        ),
    ]
