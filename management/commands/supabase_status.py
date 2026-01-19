"""
Command to check Supabase connection status and settings.
"""
from django.core.management.base import BaseCommand
from django.db import connections
from django.conf import settings
import time

class Command(BaseCommand):
    help = 'Check Supabase connection status and settings'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 Supabase Connection Status"))
        self.stdout.write("="*50)
        
        # Check current database settings
        db = settings.DATABASES['default']
        self.stdout.write(f"Database Engine: {db['ENGINE']}")
        
        if 'HOST' in db:
            self.stdout.write(f"Host: {db['HOST']}")
            self.stdout.write(f"Using Pooler: {'pooler.supabase.com' in str(db['HOST'])}")
        else:
            self.stdout.write(f"Database: {db.get('NAME', 'SQLite')}")
        
        self.stdout.write(f"CONN_MAX_AGE: {db.get('CONN_MAX_AGE', 'N/A')} seconds")
        
        # Try to connect and check
        try:
            conn = connections['default']
            start_time = time.time()
            
            with conn.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                
                self.stdout.write(self.style.SUCCESS(f"\n✅ Connected successfully!"))
                self.stdout.write(f"PostgreSQL Version: {version.split(',')[0]}")
                
                # Check active connections (PostgreSQL only)
                if db['ENGINE'] == 'django.db.backends.postgresql':
                    try:
                        cursor.execute("""
                            SELECT count(*) as active_connections 
                            FROM pg_stat_activity 
                            WHERE state = 'active' 
                            AND usename = current_user
                        """)
                        active_conns = cursor.fetchone()[0]
                        self.stdout.write(f"Your active connections: {active_conns}/20 (Supabase Free Tier Limit)")
                        
                        if active_conns > 15:
                            self.stdout.write(self.style.WARNING("⚠️  WARNING: Getting close to connection limit!"))
                        elif active_conns > 10:
                            self.stdout.write(self.style.NOTICE("ℹ️  Notice: Moderate connection usage"))
                        else:
                            self.stdout.write(self.style.SUCCESS("✓ Connection usage is good"))
                            
                    except Exception as e:
                        self.stdout.write(f"Could not check connection count: {e}")
                
                connection_time = time.time() - start_time
                self.stdout.write(f"Query time: {connection_time:.2f} seconds")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Connection error: {e}"))
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.MIGRATE_HEADING("💡 TIPS for Supabase Free Tier:"))
        self.stdout.write("1. Always run with: python manage.py runserver --nothreading")
        self.stdout.write("2. Use --noreload to prevent extra processes")
        self.stdout.write("3. Restart server if you see 'max clients reached'")
        self.stdout.write("4. Check status with: python manage.py supabase_status")
        self.stdout.write("="*50)
