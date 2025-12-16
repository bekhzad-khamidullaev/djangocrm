from django.db import migrations, models


def forwards(apps, schema_editor):
    # Add e164 fields with index
    Contact = apps.get_model('crm', 'Contact')
    Lead = apps.get_model('crm', 'Lead')
    Company = apps.get_model('crm', 'Company')


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0012_messenger_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='phone_e164',
            field=models.CharField(max_length=32, blank=True, default='', db_index=True),
        ),
        migrations.AddField(
            model_name='contact',
            name='mobile_e164',
            field=models.CharField(max_length=32, blank=True, default='', db_index=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='phone_e164',
            field=models.CharField(max_length=32, blank=True, default='', db_index=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='mobile_e164',
            field=models.CharField(max_length=32, blank=True, default='', db_index=True),
        ),
        migrations.AddField(
            model_name='company',
            name='phone_e164',
            field=models.CharField(max_length=32, blank=True, default='', db_index=True),
        ),
    ]
