# donors/management/commands/import_donors.py
"""
Django management command to import donor data from Excel
Usage: python manage.py import_donors path/to/donors.xlsx
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import pandas as pd
from donors.models import DonorProfile
from django.db import transaction
from datetime import datetime

User = get_user_model()


class Command(BaseCommand):
    help = 'Import donors from Excel file into PostgreSQL database'

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
            df = df.dropna(subset=['full_name'])
            
            imported_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Use transaction for atomicity
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        full_name = row.get('full_name', row.get('name', ''))
                        email = row.get('email', f"donor_{index}@lifelink.np")
                        phone = row.get('phone_number', '')          # was 'phone'
                        blood_type = row.get('blood_group', 'O+')    # was 'blood_type'
                        age = row.get('age', 25)
                        address = row.get('address', '')
                        
                        # Optional fields
                        latitude = row.get('latitude')
                        longitude = row.get('longitude')
                        weight = row.get('weight')
                        medical_conditions = row.get('medical_conditions', '')
                        last_donation_date = row.get('last_donation_date')
                        donation_count = row.get('donation_count', 0)
                        
                        # Validation
                        if not full_name:
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Missing name'))
                            skipped_count += 1
                            continue
                        
                        # Validate age (18-65)
                        try:
                            age = int(age)
                            if age < 18 or age > 65:
                                self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Age {age} out of range (18-65)'))
                                skipped_count += 1
                                continue
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Invalid age'))
                            skipped_count += 1
                            continue
                        
                        # Validate blood type
                        valid_blood_types = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']
                        if blood_type not in valid_blood_types:
                            self.stdout.write(self.style.WARNING(f'Skipping row {index + 2}: Invalid blood type {blood_type}'))
                            skipped_count += 1
                            continue
                        
                        # Create or get User account for this donor
                        username = email.split('@')[0].lower().replace(' ', '_')[:30]
                        user, user_created = User.objects.get_or_create(
                            email=email,
                            defaults={
                                'username': username,
                                'is_active': True,
                            }
                        )
                        
                        # Set a default password if user was just created
                        if user_created:
                            user.set_password('ChangeMe123!')  # Donor should change this
                            user.save()
                        
                        # Parse last donation date if present
                        parsed_last_donation = None
                        if pd.notna(last_donation_date):
                            try:
                                if isinstance(last_donation_date, str):
                                    parsed_last_donation = datetime.strptime(last_donation_date, '%Y-%m-%d').date()
                                else:
                                    parsed_last_donation = pd.to_datetime(last_donation_date).date()
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f'Invalid date format at row {index + 2}: {e}'))
                        
                        # Create or update DonorProfile
                        donor, created = DonorProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'full_name': full_name,
                                'age': age,
                                'phone': phone,
                                'blood_type': blood_type,
                                'address': address,
                                'latitude': float(latitude) if pd.notna(latitude) else None,
                                'longitude': float(longitude) if pd.notna(longitude) else None,
                                'weight': float(weight) if pd.notna(weight) else None,
                                'medical_conditions': medical_conditions,
                                'last_donation_date': parsed_last_donation,
                                'donation_count': int(donation_count) if pd.notna(donation_count) else 0,
                                'is_available': True,
                            }
                        )
                        
                        if created:
                            imported_count += 1
                            self.stdout.write(f'✓ Created: {donor.full_name} ({donor.blood_type}) - {user.email}')
                        else:
                            updated_count += 1
                            self.stdout.write(f'↻ Updated: {donor.full_name} ({donor.blood_type})')
                            
                    except Exception as e:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'✗ Error at row {index + 2}: {str(e)}')
                        )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Import complete!\n'
                    f'Created: {imported_count}\n'
                    f'Updated: {updated_count}\n'
                    f'Skipped: {skipped_count}\n'
                    f'Total: {imported_count + updated_count}'
                )
            )
            
            if imported_count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️  NOTE: Default password is "ChangeMe123!" for new donor accounts.\n'
                        f'Donors should change their password on first login.'
                    )
                )
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {excel_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Import failed: {str(e)}'))