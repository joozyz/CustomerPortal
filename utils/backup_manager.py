import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from models import Service, Container

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

            # Create a simple backup file with service information
            try:
                # Create a temporary directory for the backup
                temp_dir = os.path.join(backup_dir, f"temp_{timestamp}")
                os.makedirs(temp_dir, exist_ok=True)

                # Create backup info file
                with open(os.path.join(temp_dir, "backup_info.txt"), "w") as f:
                    f.write(f"Backup created at: {timestamp}\n")
                    f.write(f"Service: {service.name}\n")
                    f.write(f"Domain: {service.domain}\n")
                    f.write(f"Container ID: {container.container_id}\n")

                # Create tar archive
                os.system(f"cd {temp_dir} && tar -czf {backup_file} .")

                # Clean up temp directory
                shutil.rmtree(temp_dir)

            except Exception as e:
                self.logger.error(f"Failed to create backup archive: {str(e)}")
                return False, f"Backup creation failed: {str(e)}"

            # Update service backup timestamp
            service.last_backup_at = datetime.utcnow()

            return True, backup_file

        except Exception as e:
            self.logger.error(f"Backup creation failed: {str(e)}")
            return False, str(e)

    def restore_backup(self, service: Service, container: Container, backup_file: str) -> Tuple[bool, str]:
        """Restore a backup for a WordPress service"""
        try:
            if not os.path.exists(backup_file):
                return False, "Backup file not found"

            # Create temporary directory for restoration
            temp_dir = os.path.join(self.backup_base_path, f"restore_temp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(temp_dir, exist_ok=True)

            try:
                # Extract backup
                subprocess.run(["tar", "-xzf", backup_file, "-C", temp_dir], check=True)

                # Stop the container before restore
                subprocess.run(["podman", "stop", container.container_id], check=True)

                # Restore data to container volume
                container_data_path = f"/var/lib/containers/storage/volumes/{container.name}/_data"
                if os.path.exists(container_data_path):
                    # Backup existing data
                    backup_existing = os.path.join(temp_dir, "existing_data_backup")
                    shutil.move(container_data_path, backup_existing)

                    # Restore from backup
                    shutil.copytree(os.path.join(temp_dir, "data"), container_data_path)

                # Start the container
                subprocess.run(["podman", "start", container.container_id], check=True)

                # Clean up
                shutil.rmtree(temp_dir)

                return True, "Backup restored successfully"

            except Exception as e:
                self.logger.error(f"Failed to restore backup: {str(e)}")
                # Attempt to start container in case of failure
                try:
                    subprocess.run(["podman", "start", container.container_id])
                except:
                    pass
                return False, f"Restore failed: {str(e)}"

        except Exception as e:
            self.logger.error(f"Backup restoration failed: {str(e)}")
            return False, str(e)

    def list_backups(self, service: Service) -> List[dict]:
        """List all backups for a service"""
        try:
            backup_dir = os.path.join(self.backup_base_path, str(service.id))
            if not os.path.exists(backup_dir):
                return []

            backups = []
            for backup_file in os.listdir(backup_dir):
                if backup_file.startswith("wordpress_backup_") and backup_file.endswith(".tar.gz"):
                    file_path = os.path.join(backup_dir, backup_file)
                    file_stats = os.stat(file_path)
                    backups.append({
                        'filename': backup_file,
                        'path': file_path,
                        'size': file_stats.st_size,
                        'created_at': datetime.fromtimestamp(file_stats.st_mtime)
                    })

            return sorted(backups, key=lambda x: x['created_at'], reverse=True)

        except Exception as e:
            self.logger.error(f"Failed to list backups: {str(e)}")
            return []

    def cleanup_old_backups(self, service: Service) -> None:
        """Remove backups older than retention period"""
        try:
            backup_dir = os.path.join(self.backup_base_path, str(service.id))
            if not os.path.exists(backup_dir):
                return

            retention_days = service.backup_retention_days or 7
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            for backup_file in os.listdir(backup_dir):
                if not backup_file.startswith("wordpress_backup_") or not backup_file.endswith(".tar.gz"):
                    continue

                file_path = os.path.join(backup_dir, backup_file)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_mtime < cutoff_date:
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Removed old backup: {backup_file}")
                    except Exception as e:
                        self.logger.error(f"Failed to remove old backup {backup_file}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {str(e)}")

# Create singleton instance
backup_manager = BackupManager()