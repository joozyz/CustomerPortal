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

            # Create a simple file-based backup for now
            # Later we can add container-specific backup logic
            with open(os.path.join(backup_dir, "backup_info.txt"), "w") as f:
                f.write(f"Backup created at: {timestamp}\n")
                f.write(f"Service: {service.name}\n")
                f.write(f"Domain: {service.domain}\n")

            # Update service backup timestamp
            service.last_backup_at = datetime.utcnow()

            return True, backup_file

        except Exception as e:
            self.logger.error(f"Backup creation failed: {str(e)}")
            return False, str(e)

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