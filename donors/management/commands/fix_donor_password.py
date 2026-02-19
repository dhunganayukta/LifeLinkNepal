# donors/management/commands/fix_donor_passwords.py
"""
Django management command to fix donor passwords from Excel
This updates existing donor user passwords to match the Excel file
Usage: python manage.py fix_donor_passwords path/to/donors.xlsx
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import pandas as pd
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Fix donor passwords from Excel file (for users already imported)'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        
        self.stdout.write(self.style.WARNING(f'Starting password fix from {excel_file}...'))
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            self.stdout.write(f'Found {len(df)} rows in Excel file')
            
            updated_count = 0
            not_found_count = 0
            skipped_count = 0
            
            # Use transaction for atomicity
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        email = row.get('email')
                        password = row.get('password')
                        
                        if not email or pd.isna(email):
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing email'))
                            skipped_count += 1
                            continue
                        
                        if not password or pd.isna(password):
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing password for {email}'))
                            skipped_count += 1
                            continue
                        
                        # Find user by email
                        try:
                            user = User.objects.get(email=email)
                            user.set_password(password)
                            user.save()
                            updated_count += 1
                            self.stdout.write(self.style.SUCCESS(f'✓ Updated password for: {email}'))
                        except User.DoesNotExist:
                            not_found_count += 1
                            self.stdout.write(self.style.ERROR(f'✗ User not found: {email}'))
                            
                    except Exception as e:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'✗ Error at row {index + 2}: {str(e)}')
                        )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*50}\n'
                    f'✅ Password Update Complete!\n'
                    f'{"="*50}\n'
                    f'Updated: {updated_count}\n'
                    f'Not Found: {not_found_count}\n'
                    f'Skipped: {skipped_count}\n'
                    f'{"="*50}'
                )
            )
            
            if updated_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n✅ {updated_count} donor passwords have been updated.\n'
                        f'Donors can now login with their email and password from the Excel file.'
                    )
                )
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {excel_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Password fix failed: {str(e)}'))