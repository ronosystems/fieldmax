from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Create initial superuser if none exists'

    def handle(self, *args, **options):
        User = get_user_model()
        
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING('Superuser already exists. Skipping.')
            )
            return
        
        try:
            User.objects.create_superuser(
                username='FIELDMAX',
                email='fieldmaxsuppliers@gmail.com',
                password='Fsl#2026'
            )
            self.stdout.write(
                self.style.SUCCESS('✅ Superuser "FIELDMAX" created successfully!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating superuser: {e}')
            )
