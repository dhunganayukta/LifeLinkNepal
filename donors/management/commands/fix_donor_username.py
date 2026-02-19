# donors/management/commands/fix_donor_usernames.py
"""
Django management command to fix donor usernames from Excel
This updates existing donor usernames to match the Excel file
Usage: python manage.py fix_donor_usernames path/to/donors.xlsx
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import pandas as pd
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Fix donor usernames from Excel file (for users already imported)'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        
        self.stdout.write(self.style.WARNING(f'Starting username fix from {excel_file}...'))
        
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
                        excel_username = row.get('username')
                        
                        if not email or pd.isna(email):
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing email'))
                            skipped_count += 1
                            continue
                        
                        if not excel_username or pd.isna(excel_username):
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing username for {email}'))
                            skipped_count += 1
                            continue
                        
                        new_username = str(excel_username).strip()[:30]
                        
                        # Find user by email
                        try:
                            user = User.objects.get(email=email)
                            
                            # Check if new username is already taken by another user
                            if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠️  Username "{new_username}" already taken, skipping {email}'
                                    )
                                )
                                skipped_count += 1
                                continue
                            
                            old_username = user.username
                            user.username = new_username
                            user.save()
                            
                            updated_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Updated: {email} | {old_username} → {new_username}'
                                )
                            )
                            
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
                    f'✅ Username Update Complete!\n'
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
                        f'\n✅ {updated_count} donor usernames have been updated.\n'
                        f'Donors can now login with their username from Excel file.'
                    )
                )
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {excel_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Username fix failed: {str(e)}'))