# -*- coding: utf-8 -*-
"""
Management command to setup Asterisk Real-time configuration
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Setup Asterisk Real-time configuration for Django CRM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provision-users',
            action='store_true',
            help='Auto-provision endpoints for all active users'
        )
        parser.add_argument(
            '--create-transports',
            action='store_true',
            help='Create default transport configurations'
        )
        parser.add_argument(
            '--sync-internal-numbers',
            action='store_true',
            help='Sync InternalNumber records to Asterisk'
        )
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Test AMI and database connections'
        )
        parser.add_argument(
            '--create-test-endpoints',
            type=int,
            metavar='N',
            help='Create N test endpoints (1000-1000+N)'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate existing endpoint configurations'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Asterisk Real-time Setup ===\n'))

        # Test connection first
        if options['test_connection'] or not any([
            options['provision_users'],
            options['create_transports'],
            options['sync_internal_numbers'],
            options['create_test_endpoints'],
            options['validate']
        ]):
            self.test_connection()

        # Create default transports
        if options['create_transports']:
            self.create_default_transports()

        # Sync internal numbers
        if options['sync_internal_numbers']:
            self.sync_internal_numbers()

        # Provision users
        if options['provision_users']:
            self.provision_users()

        # Create test endpoints
        if options['create_test_endpoints']:
            self.create_test_endpoints(options['create_test_endpoints'])

        # Validate configurations
        if options['validate']:
            self.validate_endpoints()

        self.stdout.write(self.style.SUCCESS('\n=== Setup Complete ==='))

    def test_connection(self):
        """Test AMI and database connections"""
        self.stdout.write('\n--- Testing Connections ---')
        
        # Test database connection
        try:
            from voip.models import PsEndpoint
            count = PsEndpoint.objects.using('asterisk').count()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Database connection OK ({count} endpoints found)'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'✗ Database connection failed: {e}'
            ))
            return False

        # Test AMI connection
        try:
            from voip.backends.asteriskbackend import AsteriskRealtimeAPI
            from voip.models import AsteriskInternalSettings

            try:
                cfg = AsteriskInternalSettings.get_solo()
            except Exception as e:
                self.stdout.write(self.style.WARNING('⚠ Asterisk backend not configured in DB settings'))
                return False

            api = AsteriskRealtimeAPI(**cfg.to_options())
            result = api.test_connection()
            
            if result.get('ami_connected'):
                self.stdout.write(self.style.SUCCESS(
                    f'✓ AMI connection OK (Asterisk {result.get("asterisk_version", "Unknown")})'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    '⚠ AMI connection failed (some features will not work)'
                ))
            
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'✗ AMI test failed: {e}'
            ))
            return False

    def create_default_transports(self):
        """Create default transport configurations"""
        self.stdout.write('\n--- Creating Default Transports ---')
        
        from voip.models import PsTransport
        
        transports = [
            {
                'id': 'transport-udp',
                'protocol': 'udp',
                'bind': '0.0.0.0:5060',
            },
            {
                'id': 'transport-tcp',
                'protocol': 'tcp',
                'bind': '0.0.0.0:5060',
            },
            {
                'id': 'transport-wss',
                'protocol': 'wss',
                'bind': '0.0.0.0:8089',
            },
        ]
        
        for transport_data in transports:
            transport_id = transport_data['id']
            try:
                transport, created = PsTransport.objects.using('asterisk').get_or_create(
                    id=transport_id,
                    defaults=transport_data
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Created transport: {transport_id}'
                    ))
                else:
                    self.stdout.write(
                        f'  Transport {transport_id} already exists'
                    )
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'✗ Failed to create transport {transport_id}: {e}'
                ))

    def sync_internal_numbers(self):
        """Sync InternalNumber records to Asterisk"""
        self.stdout.write('\n--- Syncing Internal Numbers ---')
        
        from voip.utils.asterisk_realtime import sync_internal_numbers
        
        try:
            results = sync_internal_numbers()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created: {results["created"]}, Updated: {results["updated"]}, '
                f'Errors: {len(results["errors"])}'
            ))
            
            if results['errors']:
                self.stdout.write(self.style.WARNING('\nErrors:'))
                for error in results['errors']:
                    self.stdout.write(f'  - {error["number"]}: {error["error"]}')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Sync failed: {e}'))

    def provision_users(self):
        """Auto-provision endpoints for all active users"""
        self.stdout.write('\n--- Provisioning User Endpoints ---')
        
        from voip.utils.asterisk_realtime import bulk_provision_users
        
        try:
            results = bulk_provision_users()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Success: {results["success"]}, Failed: {results["failed"]}'
            ))
            
            if results['errors']:
                self.stdout.write(self.style.WARNING('\nErrors:'))
                for error in results['errors'][:10]:  # Show first 10
                    self.stdout.write(f'  - {error["user"]}: {error["error"]}')
                if len(results['errors']) > 10:
                    self.stdout.write(f'  ... and {len(results["errors"]) - 10} more')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Provisioning failed: {e}'))

    def create_test_endpoints(self, count):
        """Create test endpoints"""
        self.stdout.write(f'\n--- Creating {count} Test Endpoints ---')
        
        from voip.models import PsEndpoint, PsAuth, PsAor
        from voip.utils.asterisk_realtime import generate_secure_password, generate_dialplan_for_endpoint
        from django.db import transaction
        
        created = 0
        for i in range(count):
            endpoint_id = str(1000 + i)
            
            try:
                # Check if exists
                if PsEndpoint.objects.using('asterisk').filter(id=endpoint_id).exists():
                    self.stdout.write(f'  Endpoint {endpoint_id} already exists')
                    continue
                
                password = generate_secure_password()
                
                with transaction.atomic(using='asterisk'):
                    PsAuth.objects.using('asterisk').create(
                        id=endpoint_id,
                        auth_type='userpass',
                        username=endpoint_id,
                        password=password
                    )
                    
                    PsAor.objects.using('asterisk').create(
                        id=endpoint_id,
                        max_contacts=1,
                        qualify_frequency=60
                    )
                    
                    PsEndpoint.objects.using('asterisk').create(
                        id=endpoint_id,
                        transport='transport-udp',
                        context='from-internal',
                        aors=endpoint_id,
                        auth=endpoint_id,
                        callerid=f'"Test {endpoint_id}" <{endpoint_id}>',
                        disallow='all',
                        allow='ulaw,alaw,gsm',
                        direct_media='no',
                        rtp_symmetric='yes',
                        force_rport='yes',
                        rewrite_contact='yes'
                    )
                
                generate_dialplan_for_endpoint(endpoint_id, 'from-internal')
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Created test endpoint {endpoint_id} (password: {password})'
                ))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'✗ Failed to create endpoint {endpoint_id}: {e}'
                ))
        
        self.stdout.write(self.style.SUCCESS(f'\nCreated {created} test endpoints'))

    def validate_endpoints(self):
        """Validate all endpoint configurations"""
        self.stdout.write('\n--- Validating Endpoints ---')
        
        from voip.models import PsEndpoint
        from voip.utils.asterisk_realtime import validate_endpoint_config
        
        try:
            endpoints = PsEndpoint.objects.using('asterisk').all()
            total = endpoints.count()
            valid = 0
            invalid = 0
            
            for endpoint in endpoints:
                result = validate_endpoint_config(endpoint.id)
                
                if result['valid']:
                    valid += 1
                else:
                    invalid += 1
                    self.stdout.write(self.style.WARNING(
                        f'\n⚠ Endpoint {endpoint.id}:'
                    ))
                    for issue in result.get('issues', []):
                        self.stdout.write(f'  - {issue}')
                    for warning in result.get('warnings', []):
                        self.stdout.write(f'  ⚠ {warning}')
            
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Validation complete: {valid}/{total} valid, {invalid} with issues'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Validation failed: {e}'))
