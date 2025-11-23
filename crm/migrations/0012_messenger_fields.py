from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0011_calllog'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='telegram_username',
            field=models.CharField(blank=True, default='', help_text='Telegram username without @', max_length=64, verbose_name='Telegram username'),
        ),
        migrations.AddField(
            model_name='contact',
            name='instagram_username',
            field=models.CharField(blank=True, default='', help_text='Instagram handle without @', max_length=64, verbose_name='Instagram username'),
        ),
        migrations.AddField(
            model_name='lead',
            name='telegram_username',
            field=models.CharField(blank=True, default='', help_text='Telegram username without @', max_length=64, verbose_name='Telegram username'),
        ),
        migrations.AddField(
            model_name='lead',
            name='instagram_username',
            field=models.CharField(blank=True, default='', help_text='Instagram handle without @', max_length=64, verbose_name='Instagram username'),
        ),
    ]
