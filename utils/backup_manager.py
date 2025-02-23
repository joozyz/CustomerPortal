import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
from models import Service, Container
import subprocess

class BackupManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.backup_base_path = "/backups"
        
    def create_backup(self, service: Service, container: Container) -> Tuple[bool, str]:
        """Create a backup for a WordPress service"""
        try:
            if not service.backup_enabled:
                return False, "Backup is not enabled for this service"

            # Ensure backup directory exists
            backup_dir = os.path.join(self.backup_base_path, str(service.id))
            os.makedirs(backup_dir, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f"wordpress_backup_{timestamp}.tar.gz")

            # Get container environment variables
            env = container.environment or {}
            
            # Backup MySQL database
            db_backup = self._backup_database(
                container_name=f"{container.name}-mysql",
                db_name="wordpress",
                db_user="wordpress",
                db_password=env.get('wp_password', '')
            )
            
            if not db_backup:
                return False, "Database backup failed"

            # Backup WordPress files
            files_backup = self._backup_wordpress_files(
                container_name=f"{container.name}-wordpress",
                backup_file=backup_file
            )
            
            if not files_backup:
                return False, "WordPress files backup failed"

            # Update service backup timestamp
            service.last_backup_at = datetime.utcnow()
            
            return True, backup_file

        except Exception as e:
            self.logger.error(f"Backup creation failed: {str(e)}")
            return False, str(e)

    def _backup_database(self, container_name: str, db_name: str, db_user: str, db_password: str) -> bool:
        """Backup MySQL database from container"""
        try:
            # Use podman exec to run mysqldump inside the container
            cmd = [
                "podman", "exec", container_name,
                "mysqldump",
                f"--user={db_user}",
                f"--password={db_password}",
                db_name
            ]
            
            with open(f"{self.backup_base_path}/temp_db_backup.sql", 'w') as f:
                subprocess.run(cmd, stdout=f, check=True)
            
            return True
        except Exception as e:
            self.logger.error(f"Database backup failed: {str(e)}")
            return False

    def _backup_wordpress_files(self, container_name: str, backup_file: str) -> bool:
        """Backup WordPress files from container"""
        try:
            # Use podman to create tar archive of WordPress files
            cmd = [
                "podman", "exec", container_name,
                "tar", "czf", "-", "/var/www/html"
            ]
            
            with open(backup_file, 'wb') as f:
                subprocess.run(cmd, stdout=f, check=True)
            
            return True
        except Exception as e:
            self.logger.error(f"WordPress files backup failed: {str(e)}")
            return False

    def cleanup_old_backups(self, service: Service) -> None:
        """Remove backups older than retention period"""
        try:
            backup_dir = os.path.join(self.backup_base_path, str(service.id))
            if not os.path.exists(backup_dir):
                return

            retention_days = service.backup_retention_days or 7
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            for backup_file in os.listdir(backup_dir):
                file_path = os.path.join(backup_dir, backup_file)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_mtime < cutoff_date:
                    os.remove(file_path)
                    self.logger.info(f"Removed old backup: {backup_file}")

        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {str(e)}")

# Create singleton instance
backup_manager = BackupManager()
