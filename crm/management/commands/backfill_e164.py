"""
Management command to backfill phone_e164 fields for existing Contact, Lead, Company records.
"""
from django.core.management.base import BaseCommand
from crm.models import Contact, Lead, Company
from common.utils.phone import to_e164


class Command(BaseCommand):
    help = 'Backfill phone_e164 and mobile_e164 fields for existing records'

    def handle(self, *args, **options):
        self.stdout.write('Backfilling Contact phone_e164 and mobile_e164...')
        contact_count = 0
        for contact in Contact.objects.all():
            changed = False
            if contact.phone and not contact.phone_e164:
                contact.phone_e164 = to_e164(contact.phone)
                changed = True
            if contact.mobile and not contact.mobile_e164:
                contact.mobile_e164 = to_e164(contact.mobile)
                changed = True
            if changed:
                contact.save(update_fields=['phone_e164', 'mobile_e164'])
                contact_count += 1

        self.stdout.write(self.style.SUCCESS(f'Updated {contact_count} contacts'))

        self.stdout.write('Backfilling Lead phone_e164 and mobile_e164...')
        lead_count = 0
        for lead in Lead.objects.all():
            changed = False
            if lead.phone and not lead.phone_e164:
                lead.phone_e164 = to_e164(lead.phone)
                changed = True
            if lead.mobile and not lead.mobile_e164:
                lead.mobile_e164 = to_e164(lead.mobile)
                changed = True
            if changed:
                lead.save(update_fields=['phone_e164', 'mobile_e164'])
                lead_count += 1

        self.stdout.write(self.style.SUCCESS(f'Updated {lead_count} leads'))

        self.stdout.write('Backfilling Company phone_e164...')
        company_count = 0
        for company in Company.objects.all():
            if company.phone and not company.phone_e164:
                company.phone_e164 = to_e164(company.phone)
                company.save(update_fields=['phone_e164'])
                company_count += 1

        self.stdout.write(self.style.SUCCESS(f'Updated {company_count} companies'))
        self.stdout.write(self.style.SUCCESS('Backfill completed'))
