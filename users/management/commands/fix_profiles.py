"""
Management command to clean up profile issues
Save as: users/management/commands/fix_profiles.py
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import Profile
from django.db import connection

class Command(BaseCommand):
    help = 'Fix profile integrity issues'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Starting profile cleanup...\n')
        
        # Step 1: Find and delete orphaned profiles (profiles without users)
        self.stdout.write('Step 1: Checking for orphaned profiles...')
        orphaned_profiles = []
        for profile in Profile.objects.all():
            try:
                # Try to access the user
                _ = profile.user
            except User.DoesNotExist:
                orphaned_profiles.append(profile.id)
        
        if orphaned_profiles:
            Profile.objects.filter(id__in=orphaned_profiles).delete()
            self.stdout.write(
                self.style.SUCCESS(f'✅ Deleted {len(orphaned_profiles)} orphaned profiles')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ No orphaned profiles found'))
        
        # Step 2: Create profiles for users without them
        self.stdout.write('\nStep 2: Checking for users without profiles...')
        created_count = 0
        for user in User.objects.all():
            try:
                _ = user.profile
            except Profile.DoesNotExist:
                Profile.objects.create(user=user)
                created_count += 1
                self.stdout.write(f'  Created profile for: {user.username}')
        
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created {created_count} missing profiles')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ All users have profiles'))
        
        # Step 3: Check for duplicate profiles (shouldn't happen but let's verify)
        self.stdout.write('\nStep 3: Checking for duplicate profiles...')
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, COUNT(*) 
                FROM users_profile 
                GROUP BY user_id 
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
        
        if duplicates:
            self.stdout.write(self.style.WARNING(f'⚠️  Found {len(duplicates)} users with duplicate profiles'))
            for user_id, count in duplicates:
                # Keep the first profile, delete others
                profiles = Profile.objects.filter(user_id=user_id).order_by('id')
                profiles_to_delete = profiles[1:]  # All except first
                for profile in profiles_to_delete:
                    profile.delete()
                    self.stdout.write(f'  Deleted duplicate profile for user_id={user_id}')
            self.stdout.write(self.style.SUCCESS('✅ Fixed duplicate profiles'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ No duplicate profiles found'))
        
        # Step 4: Summary
        total_users = User.objects.count()
        total_profiles = Profile.objects.count()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 Summary:'))
        self.stdout.write(f'   Total Users: {total_users}')
        self.stdout.write(f'   Total Profiles: {total_profiles}')
        
        if total_users == total_profiles:
            self.stdout.write(self.style.SUCCESS('   ✅ All users have exactly one profile!'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ Mismatch: {total_users} users but {total_profiles} profiles'))
        
        self.stdout.write('='*60)
