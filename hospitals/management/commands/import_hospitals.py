# hospitals/management/commands/import_hospitals.py
"""
Django management command to import hospital data from Excel
Usage: python manage.py import_hospitals path/to/hospitals.xlsx
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import pandas as pd
from hospitals.models import HospitalProfile
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Import hospitals from Excel file into PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to the Excel file')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        
        self.stdout.write(self.style.WARNING(f'Starting import from {excel_file}...'))
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            self.stdout.write(f'Found {len(df)} rows in Excel file')
            self.stdout.write(f'Columns: {list(df.columns)}')
            
            # Clean data (remove rows with missing critical data)
            df = df.dropna(subset=['Hospital Name'])
            
            imported_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Use transaction for atomicity
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Map Excel columns to our fields
                        hospital_name = row['Hospital Name']
                        email = row['Email']
                        phone = str(row['Phone Number']) if pd.notna(row.get('Phone Number')) else ''
                        address = row.get('Address', '')
                        username = row.get('Username', row.get('Username.1', ''))
                        password = row.get('Password', 'ChangeMe123!')
                        
                        # Optional fields (if you add them to Excel later)
                        latitude = row.get('latitude')
                        longitude = row.get('longitude')
                        license_number = row.get('license_number', row.get('license', ''))
                        
                        if not hospital_name:
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing hospital name'))
                            skipped_count += 1
                            continue
                        
                        if not email or pd.isna(email):
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing email for {hospital_name}'))
                            skipped_count += 1
                            continue
                        
                        # Create or get User account for this hospital
                        if not username or pd.isna(username):
                            username = email.split('@')[0].lower().replace(' ', '_')[:30]
                        
                        user, user_created = User.objects.get_or_create(
                            email=email,
                            defaults={
                                'username': username,
                                'is_active': True,
                            }
                        )
                        
                        # Set password - use the one from Excel or default
                        if user_created:
                            if password and not pd.isna(password):
                                user.set_password(password)
                            else:
                                user.set_password('ChangeMe123!')
                            user.save()
                            self.stdout.write(f'  → Created user: {user.email} (password from Excel)')
                        
                        # Create or update HospitalProfile
                        hospital, created = HospitalProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'hospital_name': hospital_name,
                                'phone': phone,
                                'address': address,
                                'license_number': license_number,
                                'latitude': float(latitude) if pd.notna(latitude) else None,
                                'longitude': float(longitude) if pd.notna(longitude) else None,
                                'is_verified': False,
                            }
                        )
                        
                        if created:
                            imported_count += 1
                            self.stdout.write(self.style.SUCCESS(f'✓ Created: {hospital.hospital_name}'))
                        else:
                            updated_count += 1
                            self.stdout.write(f'↻ Updated: {hospital.hospital_name}')
                            
                    except Exception as e:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'✗ Error at row {index + 2}: {str(e)}')
                        )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*50}\n'
                    f'✅ Import Complete!\n'
                    f'{"="*50}\n'
                    f'Created: {imported_count}\n'
                    f'Updated: {updated_count}\n'
                    f'Skipped: {skipped_count}\n'
                    f'Total: {imported_count + updated_count}\n'
                    f'{"="*50}'
                )
            )
            
            if imported_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️  Passwords were imported from Excel.\n'
                        f'Hospitals can login with their email and password from the Excel file.'
                    )
                )
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {excel_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Import failed: {str(e)}'))