"""
Django management command для импорта CDR из Asterisk
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from voip.utils.cdr_import import AsteriskCDRImporter


class Command(BaseCommand):
    help = "Import Call Detail Records (CDR) from Asterisk"

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            choices=['csv', 'database'],
            default='csv',
            help='CDR source (csv or database)',
        )
        parser.add_argument(
            '--file',
            type=str,
            help='Path to CSV file (for csv source)',
        )
        parser.add_argument(
            '--db-host',
            type=str,
            default='localhost',
            help='Database host (for database source)',
        )
        parser.add_argument(
            '--db-user',
            type=str,
            default='asterisk',
            help='Database user (for database source)',
        )
        parser.add_argument(
            '--db-password',
            type=str,
            default='',
            help='Database password (for database source)',
        )
        parser.add_argument(
            '--db-name',
            type=str,
            default='asteriskcdrdb',
            help='Database name (for database source)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to import (for database source)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Importing CDR from Asterisk"))
        self.stdout.write("")

        importer = AsteriskCDRImporter()
        source = options['source']

        try:
            if source == 'csv':
                csv_file = options.get('file')
                if not csv_file:
                    raise CommandError("--file is required for CSV import")
                
                self.stdout.write(f"Importing from CSV: {csv_file}")
                result = importer.import_from_csv(csv_file)
                
            elif source == 'database':
                from datetime import datetime, timedelta
                from django.utils import timezone
                
                db_config = {
                    'host': options['db_host'],
                    'user': options['db_user'],
                    'password': options['db_password'],
                    'database': options['db_name'],
                }
                
                days = options['days']
                end_date = timezone.now()
                start_date = end_date - timedelta(days=days)
                
                self.stdout.write(f"Importing from database: {db_config['host']}/{db_config['database']}")
                self.stdout.write(f"Date range: {start_date.date()} to {end_date.date()}")
                self.stdout.write("")
                
                result = importer.import_from_database(db_config, start_date, end_date)
            
            else:
                raise CommandError(f"Unknown source: {source}")
            
            # Выводим результаты
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Import Results"))
            self.stdout.write(f"Total processed: {result['total_processed']}")
            self.stdout.write(self.style.SUCCESS(f"Imported: {result['imported']}"))
            self.stdout.write(f"Skipped: {result['skipped']}")
            
            if result['errors'] > 0:
                self.stdout.write(self.style.ERROR(f"Errors: {result['errors']}"))
                
                if result['error_details']:
                    self.stdout.write("")
                    self.stdout.write("Error details:")
                    for error in result['error_details']:
                        self.stdout.write(f"  - {error}")
            
            if result['success']:
                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("CDR import completed successfully"))
            else:
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("CDR import completed with errors"))
                
        except Exception as e:
            raise CommandError(f"Import failed: {e}")
