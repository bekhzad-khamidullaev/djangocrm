from __future__ import annotations

import sys
from typing import Optional

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Generate comprehensive demo data across CRM, Tasks, Marketing, Massmail, VOIP, Chat, and Analytics.\n"
        "This will: run setupdata, run loaddemo, generate analytics demo data, and add marketing/massmail samples.\n"
        "Use --reset to safely remove previously generated demo data."
    )

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=6, help='Months back for analytics demo data')
        parser.add_argument('--per-month', type=int, default=5, help='Objects per month for analytics demo data')
        parser.add_argument('--intensity', type=str, choices=['low','medium','high'], default='medium', help='Scale of extra demo generation across all models')
        parser.add_argument('--dashboard', action='store_true', help='Also create analytics dashboard for a user')
        parser.add_argument('--dashboard-user', type=str, default='IamSUPER', help='Username to own dashboard')
        parser.add_argument('--reset', action='store_true', help='Remove prior demo-generated data before creating new')

    def handle(self, *args, **opts):
        months: int = opts['months']
        per_month: int = opts['per_month']
        intensity: str = opts['intensity']
        dashboard: bool = opts['dashboard']
        dashboard_user: str = opts['dashboard_user']
        do_reset: bool = opts['reset']

        # map intensity -> sizes
        size_map = {
            'low':  {'companies': 5,  'contacts': 10, 'leads': 15, 'products': 5, 'deals': 20, 'payments': 20, 'requests': 20,
                     'projects': 2, 'tasks': 20, 'memos': 5,
                     'chat_threads': 5, 'chat_msgs': 5,
                     'calls': 10,
                     'ext_msgs': 10,
                     'marketing_campaigns': 1, 'marketing_templates': 2, 'marketing_segments': 1,
                     'eml_messages': 2},
            'medium':{'companies': 10, 'contacts': 25, 'leads': 40, 'products': 8, 'deals': 50, 'payments': 50, 'requests': 50,
                     'projects': 4, 'tasks': 60, 'memos': 10,
                     'chat_threads': 10, 'chat_msgs': 10,
                     'calls': 30,
                     'ext_msgs': 30,
                     'marketing_campaigns': 2, 'marketing_templates': 4, 'marketing_segments': 2,
                     'eml_messages': 6},
            'high': {'companies': 20, 'contacts': 60, 'leads': 100,'products': 12, 'deals': 120,'payments': 120,'requests': 120,
                     'projects': 6, 'tasks': 150,'memos': 25,
                     'chat_threads': 20, 'chat_msgs': 20,
                     'calls': 80,
                     'ext_msgs': 80,
                     'marketing_campaigns': 4, 'marketing_templates': 6, 'marketing_segments': 3,
                     'eml_messages': 12},
        }
        sizes = size_map[intensity]

        # Ensure base fixtures and a superuser exist
        self.stdout.write(self.style.MIGRATE_HEADING('Ensuring base fixtures via setupdata...'))
        call_command('setupdata', verbosity=0)

        if do_reset:
            self.stdout.write(self.style.WARNING('Reset requested: removing previous demo data...'))
            self._reset_demo_data()
            self.stdout.write(self.style.SUCCESS('Previous demo data removed.'))

        created_total = 0
        with transaction.atomic():
            # Existing basic demo
            self.stdout.write(self.style.MIGRATE_HEADING('Running loaddemo (base demo records)...'))
            call_command('loaddemo', verbosity=0)

            # Analytics-oriented bulk demo
            self.stdout.write(self.style.MIGRATE_HEADING('Generating analytics demo data...'))
            call_command('loadanalyticsdemo', months=months, per_month=per_month, verbosity=0)

            # Bulk enrichers
            self.stdout.write(self.style.MIGRATE_HEADING('Generating extra CRM data...'))
            created_total += self._bulk_crm(sizes)

            self.stdout.write(self.style.MIGRATE_HEADING('Generating Tasks data...'))
            created_total += self._bulk_tasks(sizes)

            self.stdout.write(self.style.MIGRATE_HEADING('Generating Chat threads...'))
            created_total += self._bulk_chat(sizes)

            self.stdout.write(self.style.MIGRATE_HEADING('Generating VOIP calls...'))
            created_total += self._bulk_voip(sizes)

            self.stdout.write(self.style.MIGRATE_HEADING('Generating Integrations messages...'))
            created_total += self._bulk_integrations(sizes)

            # Expanded Marketing and Massmail demo
            self.stdout.write(self.style.MIGRATE_HEADING('Ensuring Marketing demo data...'))
            created_total += self._ensure_marketing_demo(sizes)

            self.stdout.write(self.style.MIGRATE_HEADING('Ensuring Massmail demo data...'))
            created_total += self._ensure_massmail_demo(sizes)

        if dashboard:
            try:
                self.stdout.write(self.style.MIGRATE_HEADING('Setting up analytics dashboard...'))
                call_command('setup_dashboard', user=dashboard_user, layout='2_col', verbosity=0)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to setup dashboard: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Demo data generation complete. Additional created: ~{created_total}'))

    # --------- Bulk enrichers ---------
    def _bulk_crm(self, sizes) -> int:
        created = 0
        from django.contrib.auth import get_user_model
        from decimal import Decimal
        from common.models import Department
        from crm.models import Company, Contact, Lead, Deal, Product, Payment, Request as CrmRequest
        from crm.models.others import LeadSource
        from crm.models import Currency
        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        dept = Department.objects.order_by('id').first()
        usd = Currency.objects.filter(name__icontains='US').first() or Currency.objects.first()
        lead_sources = list(LeadSource.objects.all())

        # Companies
        for i in range(1, sizes['companies'] + 1):
            name = f'Demo Company #{i}'
            obj, was = Company.objects.get_or_create(full_name=name, defaults={'owner': owner, 'department': dept})
            created += int(was)
        companies = list(Company.objects.filter(full_name__startswith='Demo Company #'))

        # Contacts
        for i in range(1, sizes['contacts'] + 1):
            comp = companies[(i - 1) % len(companies)] if companies else None
            email = f'user{i}@demo.test'
            _, was = Contact.objects.get_or_create(email=email, defaults={
                'first_name': f'User{i}', 'last_name': 'Demo', 'owner': owner, 'company': comp, 'department': dept,
            })
            created += int(was)

        # Leads
        for i in range(1, sizes['leads'] + 1):
            email = f'lead{i}@demo.test'
            ls = lead_sources[(i - 1) % len(lead_sources)] if lead_sources else None
            _, was = Lead.objects.get_or_create(email=email, defaults={
                'first_name': f'Lead{i}', 'last_name': 'Demo', 'owner': owner, 'lead_source': ls, 'department': dept,
                'company_name': f'Demo Company #{(i % max(1,len(companies)))+1}',
            })
            created += int(was)

        # Products
        for i in range(1, sizes['products'] + 1):
            name = f'Demo Product #{i}'
            _, was = Product.objects.get_or_create(name=name, defaults={'price': Decimal(str(49 + i * 5)), 'type': 'G'})
            created += int(was)

        # Deals and Payments
        products = list(Product.objects.filter(name__startswith='Demo Product #'))
        contacts = list(Contact.objects.filter(email__endswith='@demo.test'))
        from uuid import uuid4
        for i in range(1, sizes['deals'] + 1):
            comp = companies[(i - 1) % len(companies)] if companies else None
            cont = contacts[(i - 1) % len(contacts)] if contacts else None
            name = f'Demo Deal #{i}'
            obj, was = Deal.objects.get_or_create(name=name, defaults={
                'company': comp, 'contact': cont, 'owner': owner, 'amount': 200 + i*10, 'currency': usd, 'department': dept,
                'next_step': 'Follow-up', 'next_step_date': timezone.now().date(),
                'ticket': f'DB-{uuid4().hex[:12]}',
            })
            created += int(was)
            # payments
            if obj:
                for p in range(1, max(1, sizes['payments']//max(1,sizes['deals'])) + 1):
                    _, pwas = Payment.objects.get_or_create(deal=obj, amount=100 + p*10, defaults={'currency': usd})
                    created += int(pwas)

        # Requests
        for i in range(1, sizes['requests'] + 1):
            ls = lead_sources[(i - 1) % len(lead_sources)] if lead_sources else None
            _, was = CrmRequest.objects.get_or_create(
                description=f'Demo request bulk #{i}',
                defaults={'department': dept, 'lead_source': ls, 'receipt_date': timezone.now().date(), 'email': f'req{i}@demo.test'},
            )
            created += int(was)

        return created

    def _bulk_tasks(self, sizes) -> int:
        created = 0
        from django.contrib.auth import get_user_model
        from common.models import Department
        from tasks.models import Project, Task, Memo, Tag, TaskStage
        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        dept = Department.objects.order_by('id').first()
        default_stage = TaskStage.objects.filter(default=True).first() or TaskStage.objects.first()

        # Projects
        for i in range(1, sizes['projects'] + 1):
            _, was = Project.objects.get_or_create(name=f'Demo Project #{i}', defaults={'owner': owner})
            created += int(was)
        projects = list(Project.objects.filter(name__startswith='Demo Project #'))

        # Tag
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Task)
        tag, was = Tag.objects.get_or_create(name='demo', defaults={'for_content': ct})
        if not was and getattr(tag, 'for_content_id', None) is None:
            tag.for_content = ct
            tag.save(update_fields=['for_content'])
        created += int(was)

        # Tasks and Memos
        for i in range(1, sizes['tasks'] + 1):
            pr = projects[(i - 1) % len(projects)] if projects else None
            t, was = Task.objects.get_or_create(name=f'Demo Task #{i}', defaults={'owner': owner, 'project': pr, 'stage': default_stage})
            created += int(was)
            t.tags.add(tag)
        for i in range(1, sizes['memos'] + 1):
            pr = projects[(i - 1) % len(projects)] if projects else None
            _, was = Memo.objects.get_or_create(
                name=f'Demo Memo #{i}',
                defaults={'owner': owner, 'to': owner, 'project': pr, 'note': 'Demo note'}
            )
            created += int(was)
        return created

    def _bulk_chat(self, sizes) -> int:
        created = 0
        from django.contrib.contenttypes.models import ContentType
        from chat.models import ChatMessage
        from crm.models import Request as CrmRequest
        reqs = list(CrmRequest.objects.order_by('-id')[:sizes['chat_threads']])
        for idx, req in enumerate(reqs, start=1):
            ct = ContentType.objects.get_for_model(req)
            for j in range(1, sizes['chat_msgs'] + 1):
                _, was = ChatMessage.objects.get_or_create(content_type=ct, object_id=req.id, content=f'Demo chat message {idx}-{j}', defaults={'owner_id': getattr(req, 'owner_id', None)})
                created += int(was)
        return created

    def _bulk_voip(self, sizes) -> int:
        created = 0
        try:
            from voip.models import IncomingCall
            from crm.models.others import CallLog
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            for i in range(1, sizes['calls'] + 1):
                num = f'+99890{1000000+i:07d}'[-12:]
                _, was = IncomingCall.objects.get_or_create(user=user, caller_id=num, defaults={'client_name': f'Demo Caller {i}'})
                created += int(was)
                _, was = CallLog.objects.get_or_create(user=user, number=num, direction='inbound', defaults={'duration': 30 + (i % 120)})
                created += int(was)
        except Exception:
            pass
        return created

    def _bulk_integrations(self, sizes) -> int:
        created = 0
        try:
            from integrations.models import ChannelAccount, ExternalMessage
            chans = list(ChannelAccount.objects.filter(is_active=True))
            for i in range(1, sizes['ext_msgs'] + 1):
                if not chans:
                    break
                ch = chans[(i - 1) % len(chans)]
                _, was = ExternalMessage.objects.get_or_create(channel=ch, direction='out', external_id=f'demo-bulk-{i}', defaults={'text': f'Demo message #{i}', 'sender_id': 'demo', 'recipient_id': 'client'})
                created += int(was)
        except Exception:
            pass
        return created

    # --------- Reset helpers ---------
    def _reset_demo_data(self) -> None:
        """Delete objects that are clearly recognized as demo-generated.
        We only delete items with our known demo markers to be safe.
        """
        # CRM-related
        try:
            from crm.models import Deal, Company, Contact, Payment, Request
            from django.db.models import Q

            # Payments attached to demo deals
            demo_deals = Deal.objects.filter(
                Q(name__startswith='Demo deal') | Q(name='Analytics Demo Deal')
            )
            Payment.objects.filter(deal__in=demo_deals).delete()

            # Deals
            demo_deals.delete()

            # Requests generated for analytics
            Request.objects.filter(description__icontains='Generated for analytics').delete()

            # A sample company and contact from loaddemo
            Company.objects.filter(full_name__in=['Acme Corp']).delete()
            Contact.objects.filter(email__in=['john.doe@acme.test']).delete()
        except Exception:
            # Keep going even if some apps are not migrated yet
            pass

        # VOIP and Call logs
        try:
            from voip.models import IncomingCall
            from crm.models.others import CallLog
            IncomingCall.objects.filter(client_name='Demo Caller').delete()
            CallLog.objects.filter(number__in=['+998901112233', '+998909998877']).delete()
        except Exception:
            pass

        # Chat threads
        try:
            from chat.models import ChatMessage
            from django.db.models import Q
            ChatMessage.objects.filter(
                Q(content__startswith='Welcome to chat!') | Q(content__icontains='Demo')
            ).delete()
        except Exception:
            pass

        # Integrations external messages
        try:
            from integrations.models import ExternalMessage
            ExternalMessage.objects.filter(external_id__startswith='demo-').delete()
        except Exception:
            pass

        # Marketing
        try:
            from marketing.models import Campaign, CampaignRun, Segment, MessageTemplate
            CampaignRun.objects.filter(campaign__name__startswith='Demo ').delete()
            Campaign.objects.filter(name__startswith='Demo ').delete()
            Segment.objects.filter(name__startswith='Demo ').delete()
            MessageTemplate.objects.filter(name__startswith='Demo ').delete()
        except Exception:
            pass

        # Massmail
        try:
            from massmail.models import EmlMessage, EmailAccount
            EmlMessage.objects.filter(subject__startswith='Demo ').delete()
            EmailAccount.objects.filter(name__in=['Gmail Demo', 'Corp SMTP Demo']).delete()
        except Exception:
            pass

    # --------- Demo generators ---------
    def _ensure_marketing_demo(self, sizes) -> int:
        from marketing.models import Segment, MessageTemplate, Campaign, CampaignRun
        created = 0

        # base entries
        seg, was = Segment.objects.get_or_create(
            name='Demo Segment: Recent Leads',
            defaults={
                'description': 'Auto-generated segment for demo (recent leads with email).',
                'rules': {
                    'model': 'crm.Lead',
                    'filters': {'email__contains': '@'},
                },
                'size_cache': 50,
            },
        )
        created += int(was)
        tmpl_sms, was = MessageTemplate.objects.get_or_create(
            name='Demo SMS Promo',
            defaults={
                'channel': 'sms',
                'locale': 'en',
                'subject': '',
                'body': 'Hi {{first_name}}, check our new offer: -20% this week!',
                'variables': ['first_name'],
            },
        )
        created += int(was)
        tmpl_email, was = MessageTemplate.objects.get_or_create(
            name='Demo Email Promo',
            defaults={
                'channel': 'email',
                'locale': 'en',
                'subject': 'Welcome to Demo CRM',
                'body': '<h3>Hello {{first_name}}</h3><p>Glad to see you! 🎉</p>',
                'variables': ['first_name'],
            },
        )
        created += int(was)

        camp, was = Campaign.objects.get_or_create(
            name='Demo Campaign: Spring Promo',
            defaults={
                'channel': 'sms',
                'segment': seg,
                'template': tmpl_sms,
                'start_at': timezone.now(),
                'is_active': True,
            },
        )
        created += int(was)
        if not camp.runs.exists():
            CampaignRun.objects.create(
                campaign=camp,
                size=seg.size_cache or 50,
                sent=40,
                delivered=35,
                failed=5,
                replied=7,
            )
            created += 1

        # extra entries based on intensity sizes
        # New segments
        for i in range(1, sizes['marketing_segments'] + 1):
            name = f'Demo Segment #{i}'
            _, was = Segment.objects.get_or_create(
                name=name,
                defaults={'description': 'Bulk demo segment', 'rules': {'model': 'crm.Contact'}, 'size_cache': 100},
            )
            created += int(was)
        # New templates (mix of sms/email)
        for i in range(1, sizes['marketing_templates'] + 1):
            name = f'Demo Template #{i}'
            channel = 'sms' if i % 2 == 0 else 'email'
            defaults = {'channel': channel, 'locale': 'en', 'subject': f'Demo Subj #{i}' if channel=='email' else '', 'body': f'Demo body #{i}', 'variables': []}
            _, was = MessageTemplate.objects.get_or_create(name=name, defaults=defaults)
            created += int(was)
        # New campaigns
        all_segments = list(Segment.objects.all()[:sizes['marketing_segments']])
        all_templates = list(MessageTemplate.objects.all()[:max(1, sizes['marketing_templates'])])
        for i in range(1, sizes['marketing_campaigns'] + 1):
            name = f'Demo Campaign #{i}'
            seg_pick = all_segments[(i-1) % len(all_segments)] if all_segments else None
            tmpl_pick = all_templates[(i-1) % len(all_templates)] if all_templates else None
            _, was = Campaign.objects.get_or_create(
                name=name,
                defaults={'channel': (tmpl_pick.channel if tmpl_pick else 'sms'), 'segment': seg_pick, 'template': tmpl_pick, 'start_at': timezone.now(), 'is_active': True},
            )
            created += int(was)
        return created

    def _ensure_massmail_demo(self, sizes) -> int:
        created = 0
        try:
            from massmail.models import EmailAccount, EmlMessage
            from django.contrib.auth import get_user_model
            User = get_user_model()
            owner = User.objects.filter(is_superuser=True).first() or User.objects.first()

            acc, was = EmailAccount.objects.get_or_create(
                name='Gmail Demo',
                defaults={
                    'owner': owner,
                    'main': True,
                    'massmail': True,
                    'email_host': 'smtp.gmail.com',
                    'imap_host': 'imap.gmail.com',
                    'email_host_user': 'demo@gmail.com',
                    'email_host_password': 'demo-password',
                    'email_port': 587,
                    'from_email': 'Demo <demo@gmail.com>',
                    'email_use_tls': True,
                },
            )
            created += int(was)

            from common.models import Department
            dept = Department.objects.order_by('id').first()

            # base two
            for subj, body in [
                ('Demo Welcome Letter', '<p>Welcome to the demo!</p>'),
                ('Demo Product Announcement', '<p>New features are available now.</p>'),
            ]:
                _, was = EmlMessage.objects.get_or_create(
                    subject=subj,
                    defaults={'owner': owner, 'department': dept, 'content': body},
                )
                created += int(was)

            # extra bulk
            for i in range(1, sizes['eml_messages'] + 1):
                subj = f'Demo Bulk Email #{i}'
                _, was = EmlMessage.objects.get_or_create(
                    subject=subj,
                    defaults={'owner': owner, 'department': dept, 'content': f'<p>Bulk message {i}</p>'},
                )
                created += int(was)
        except Exception:
            # Massmail app might be optional
            pass
        return created
