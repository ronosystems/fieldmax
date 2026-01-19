"""
Command to close all database connections.
"""
from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = 'Close all database connections'
    
    def handle(self, *args, **options):
        self.stdout.write("Closing all database connections...")
        self.stdout.write("="*50)
        
        closed_count = 0
        error_count = 0
        
        for conn_name in connections:
            conn = connections[conn_name]
            try:
                if hasattr(conn, 'close'):
                    conn.close()
                    closed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"✓ Closed connection: {conn_name}"))
                else:
                    self.stdout.write(f"ℹ️  No close method for: {conn_name}")
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"✗ Error closing {conn_name}: {e}"))
        
        self.stdout.write("="*50)
        self.stdout.write(self.style.SUCCESS(f"Total connections closed: {closed_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("Next: Restart server with: python manage.py runserver --nothreading")
        self.stdout.write("="*50)
