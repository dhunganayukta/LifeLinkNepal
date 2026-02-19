# hospitals/management/commands/import_hospitals.py
"""
Django Management Command to Import Hospitals from Excel
Properly hashes passwords and creates/updates hospital accounts
NOW HANDLES DUPLICATE EMAILS!

USAGE:
    python manage.py import_hospitals path/to/excel_file.xlsx
    
    OR (if file is in project root):
    python manage.py import_hospitals nepal_hospitals_complete.xlsx
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from hospitals.models import HospitalProfile
from django.db import transaction
import pandas as pd
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Import hospitals from Excel file with proper password hashing'

    def add_arguments(self, parser):
        parser.add_argument(
            'excel_file',
            type=str,
            help='Path to Excel file containing hospital data'
        )

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        
        # Check if file exists
        if not os.path.exists(excel_file):
            self.stdout.write(self.style.ERROR(f'❌ File not found: {excel_file}'))
            return
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS('🏥 HOSPITAL IMPORT - WITH PASSWORD HASHING'))
        self.stdout.write("=" * 70)
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            total = len(df)
            self.stdout.write(f"\n📊 Found {total} hospitals in Excel file\n")
            
            # Verify required columns
            required_columns = ['Username', 'Email', 'Password', 'Hospital Name', 'Address', 'Phone Number']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                self.stdout.write(self.style.ERROR(f'❌ Missing columns: {", ".join(missing_columns)}'))
                return
            
            # Counters
            created_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0
            errors = []
            
            # Track emails we've seen to handle duplicates
            processed_emails = set()
            
            # Process each hospital
            for index, row in df.iterrows():
                username = str(row['Username']).strip()
                email = str(row['Email']).strip()
                password = str(row['Password']).strip()
                hospital_name = str(row['Hospital Name']).strip()
                address = str(row['Address']).strip()
                phone = str(row['Phone Number']).strip()
                
                # Optional fields
                license_number = str(row['license_number']).strip() if 'license_number' in row and pd.notna(row['license_number']) else ''
                latitude = float(row['latitude']) if 'latitude' in row and pd.notna(row['latitude']) else None
                longitude = float(row['longitude']) if 'longitude' in row and pd.notna(row['longitude']) else None
                
                try:
                    with transaction.atomic():
                        # Check if user already exists by username
                        user = User.objects.filter(username=username).first()
                        
                        if user:
                            # UPDATE EXISTING USER
                            # Only update email if it's different and not already taken by another user
                            if user.email != email:
                                # Check if new email is already used by someone else
                                if User.objects.filter(email=email).exclude(id=user.id).exists():
                                    # Email is taken by another user - make it unique
                                    unique_email = f"{username}@{email.split('@')[1]}"
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"⚠️  [{index+1}/{total}] Duplicate email {email} - using {unique_email} instead"
                                        )
                                    )
                                    email = unique_email
                                user.email = email
                            
                            user.set_password(password)  # ✅ PROPERLY HASH PASSWORD
                            user.user_type = 'hospital'
                            user.is_active = True
                            user.failed_attempts = 0  # Reset failed attempts
                            user.is_locked = False  # Unlock account
                            user.save()
                            
                            # Update or create hospital profile
                            hospital_profile, created = HospitalProfile.objects.get_or_create(user=user)
                            hospital_profile.hospital_name = hospital_name
                            hospital_profile.phone = phone
                            hospital_profile.address = address
                            hospital_profile.license_number = license_number
                            hospital_profile.latitude = latitude
                            hospital_profile.longitude = longitude
                            hospital_profile.save()
                            
                            updated_count += 1
                            self.stdout.write(
                                self.style.WARNING(f"🔄 [{index+1}/{total}] Updated: {username} - {hospital_name}")
                            )
                            
                        else:
                            # CREATE NEW USER
                            # Check for duplicate email in this batch or database
                            if email in processed_emails or User.objects.filter(email=email).exists():
                                # Make email unique by using username
                                original_email = email
                                email = f"{username}@{email.split('@')[1]}"
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"⚠️  [{index+1}/{total}] Duplicate email {original_email} - using {email} instead"
                                    )
                                )
                            
                            processed_emails.add(email)
                            
                            user = User.objects.create_user(
                                username=username,
                                email=email,
                                password=password,  # ✅ create_user() automatically hashes this
                                user_type='hospital',
                                is_active=True
                            )
                            
                            # Create hospital profile
                            HospitalProfile.objects.create(
                                user=user,
                                hospital_name=hospital_name,
                                phone=phone,
                                address=address,
                                license_number=license_number,
                                latitude=latitude,
                                longitude=longitude
                            )
                            
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"✅ [{index+1}/{total}] Created: {username} - {hospital_name}")
                            )
                            
                except Exception as e:
                    error_count += 1
                    error_msg = f"{username}: {str(e)}"
                    errors.append(error_msg)
                    self.stdout.write(
                        self.style.ERROR(f"❌ [{index+1}/{total}] Error: {error_msg}")
                    )
                    continue
            
            # Summary
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS('📊 IMPORT SUMMARY'))
            self.stdout.write("=" * 70)
            self.stdout.write(f"✅ Created:  {created_count} new hospitals")
            self.stdout.write(f"🔄 Updated:  {updated_count} existing hospitals")
            if skipped_count > 0:
                self.stdout.write(f"⏭️  Skipped:  {skipped_count} duplicates")
            self.stdout.write(f"❌ Errors:   {error_count}")
            self.stdout.write(f"📈 Total:    {total} hospitals processed")
            
            if errors:
                self.stdout.write("\n⚠️  ERRORS:")
                for error in errors:
                    self.stdout.write(f"   - {error}")
            
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS('✅ IMPORT COMPLETE!'))
            self.stdout.write("=" * 70)
            self.stdout.write('\n🔐 All hospitals can now login with their passwords from Excel!')
            self.stdout.write('Note: Passwords have been properly hashed in the database.')
            if skipped_count > 0 or any('Duplicate email' in str(e) for e in errors):
                self.stdout.write('\n⚠️  Some hospitals had duplicate emails - they were given unique emails.')
                self.stdout.write('Format: username@domain.com (e.g., patan_hosp@pahs.edu.np)\n')
            
            # Verify first 5
            self.stdout.write("\n📋 VERIFICATION - First 5 Hospitals:")
            self.stdout.write("-" * 70)
            for index, row in df.head(5).iterrows():
                username = str(row['Username']).strip()
                user = User.objects.filter(username=username).first()
                if user:
                    has_profile = hasattr(user, 'hospitalprofile')
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ {username}: Email={user.email} | Profile: {has_profile} | Active: {user.is_active}"
                        )
                    )
                else:
                    self.stdout.write(self.style.ERROR(f"❌ {username}: NOT FOUND"))
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'❌ File not found: {excel_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error reading Excel file: {str(e)}'))
            self.stdout.write(self.style.ERROR('Make sure pandas and openpyxl are installed:'))
            self.stdout.write('   pip install pandas openpyxl')