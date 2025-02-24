import os
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import subprocess
import json
from models import Container, Service

logger = logging.getLogger(__name__)

class PodmanManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.available = False
        try:
            # Check if podman is installed and running using subprocess
            result = subprocess.run(['podman', 'version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.available = True
                logger.info("Podman is available on the system")
            else:
                logger.warning("Podman version check failed")
        except FileNotFoundError:
            logger.warning("Podman is not installed on the system")
        except Exception as e:
            logger.error(f"Error checking podman availability: {str(e)}")

    def check_system(self) -> Tuple[bool, str]:
        """Check if Podman system is available and running"""
        if not self.available:
            return False, "Podman is not available on the system"

        try:
            result = subprocess.run(['podman', 'info'], capture_output=True, text=True)
            if result.returncode == 0:
                return True, "Podman is running"
            return False, "Podman service is not running"
        except Exception as e:
            logger.error(f"Podman system check failed: {str(e)}")
            return False, str(e)

    def get_system_health(self) -> str:
        """Get overall system health status"""
        if not self.available:
            return "unavailable"

        try:
            status, _ = self.check_system()
            if not status:
                return "unhealthy"

            return "healthy"
        except Exception as e:
            logger.error(f"Failed to get system health: {str(e)}")
            return "unhealthy"

    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed system health information"""
        health_info = {
            'status': 'error',
            'podman_available': self.available,
            'message': 'Podman is not available on the system',
            'containers': {
                'total': 0,
                'running': 0,
                'stopped': 0,
                'failed': 0
            },
            'system_info': {
                'os': os.uname().sysname,
                'kernel': os.uname().release,
            }
        }

        if not self.available:
            return health_info

        try:
            # Get version info
            version_result = subprocess.run(['podman', 'version', '--format', '{{.Version}}'], 
                                       capture_output=True, text=True)

            if version_result.returncode == 0:
                health_info['version'] = version_result.stdout.strip()
                health_info['status'] = 'ok'
                health_info['message'] = 'Podman is running'

                # Get container statistics if version check passed
                stats_result = subprocess.run(['podman', 'ps', '-a', '--format', '{{.Status}}'], 
                                         capture_output=True, text=True)

                if stats_result.returncode == 0:
                    containers = stats_result.stdout.strip().split('\n')
                    if containers and containers[0]:  # Check if there are any containers
                        health_info['containers'] = {
                            'total': len(containers),
                            'running': sum(1 for c in containers if c and c.startswith('Up')),
                            'stopped': sum(1 for c in containers if c and c.startswith('Exited')),
                            'failed': sum(1 for c in containers if c and 'Error' in c)
                        }

            return health_info

        except Exception as e:
            logger.error(f"Failed to get detailed health: {str(e)}")
            health_info['message'] = str(e)
            return health_info

    def get_container_status(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get current status and metrics of a container"""
        if not self.available:
            return None

        try:
            result = subprocess.run(['podman', 'inspect', container_id], 
                                capture_output=True, text=True)
            if result.returncode == 0:
                container_info = json.loads(result.stdout)[0]
                return {
                    'status': container_info['State']['Status'],
                    'started_at': container_info['State']['StartedAt'],
                    'finished_at': container_info['State']['FinishedAt']
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get container status: {str(e)}")
            return None

    def stop_container(self, container_id: str) -> bool:
        """Stop a running container"""
        if not self.available:
            return False

        try:
            result = subprocess.run(['podman', 'stop', container_id], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to stop container: {str(e)}")
            return False

    def remove_container(self, container_id: str) -> bool:
        """Remove a container"""
        if not self.available:
            return False

        try:
            result = subprocess.run(['podman', 'rm', '-f', container_id], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to remove container: {str(e)}")
            return False

    def deploy_lemp_stack(self, service: Service, user_id: int) -> Optional[Container]:
        if not self.check_system()[0]:
            self.logger.error("Cannot deploy LEMP stack: Podman system check failed")
            return None

        try:
            stack_name = f"sites-{user_id}"

            # Pull required images
            images = [
                'docker.io/nginx:latest',
                'docker.io/php:8.2-fpm',
                'docker.io/mariadb:latest',
                'docker.io/adminer:latest'
            ]

            for image in images:
                try:
                    self.logger.info(f"Pulling image: {image}")
                    subprocess.run(['podman', 'pull', image], check=True)
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Failed to pull image {image}: {str(e)}")
                    return None
                except Exception as e:
                    self.logger.error(f"An unexpected error occurred while pulling image {image}: {str(e)}")
                    return None


            # Create MariaDB container
            db_container_create_result = subprocess.run(['podman', 'create', '--name', f"{stack_name}-db", '--env', 'MYSQL_ROOT_PASSWORD=changeme', '--env', 'MYSQL_DATABASE=wordpress', '--env', 'MYSQL_USER=wordpress', '--env', 'MYSQL_PASSWORD=wordpress', 'docker.io/mariadb:latest'], capture_output=True, text=True)

            # Create PHP-FPM container
            php_container_create_result = subprocess.run(['podman', 'create', '--name', f"{stack_name}-php", 'docker.io/php:8.2-fpm'], capture_output=True, text=True)

            # Create Nginx container with port mapping
            nginx_container_create_result = subprocess.run(['podman', 'create', '--name', f"{stack_name}-nginx", '-p', '80:80', 'docker.io/nginx:latest'], capture_output=True, text=True)

            # Create Adminer container
            adminer_container_create_result = subprocess.run(['podman', 'create', '--name', f"{stack_name}-adminer", '-p', '8080:8080', 'docker.io/adminer:latest'], capture_output=True, text=True)

            if (db_container_create_result.returncode != 0 or php_container_create_result.returncode != 0 or nginx_container_create_result.returncode != 0 or adminer_container_create_result.returncode != 0):
                self.logger.error("Failed to create containers")
                return None

            containers = [f"{stack_name}-db", f"{stack_name}-php", f"{stack_name}-nginx", f"{stack_name}-adminer"]
            started_containers = []

            for container in containers:
                try:
                    self.logger.info(f"Starting container: {container}")
                    subprocess.run(['podman', 'start', container], check=True)
                    started_containers.append(container)
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Failed to start container {container}: {str(e)}")
                    # Clean up any containers that were started
                    for started in started_containers:
                        try:
                            subprocess.run(['podman', 'stop', started], check=True)
                            subprocess.run(['podman', 'rm', '-f', started], check=True)
                        except subprocess.CalledProcessError as e:
                            pass
                    return None
                except Exception as e:
                    self.logger.error(f"An unexpected error occurred while starting container {container}: {str(e)}")
                    return None

            # Get the assigned Nginx port (using inspect is unreliable with subprocess method)
            nginx_port = 80

            # Create Container record in database
            db_container = Container(
                container_id=f"{stack_name}-nginx",  # Use Nginx container as main reference
                name=stack_name,
                status='running',
                user_id=user_id,
                service_id=service.id,
                port=nginx_port,
                environment={'stack_name': stack_name}
            )

            return db_container

        except Exception as e:
            self.logger.error(f"Error deploying LEMP stack: {str(e)}")
            self.cleanup_stack(stack_name)
            return None

    def cleanup_stack(self, stack_name: str):
        """Remove all containers in a stack if deployment fails"""
        if not self.available:
            return

        try:
            containers = subprocess.run(['podman', 'ps', '-a', '--format', '{{.ID}} {{.Names}}'], capture_output=True, text=True).stdout.strip().split('\n')
            for container in containers:
                if container.strip() and container.split()[1].startswith(stack_name):
                    try:
                        subprocess.run(['podman', 'rm', '-f', container.split()[0]], check=True)
                    except subprocess.CalledProcessError as e:
                        self.logger.error(f"Failed to remove container {container.split()[1]}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error cleaning up stack {stack_name}: {str(e)}")

    def deploy_wordpress(self, service: Service, user_id: int) -> Optional[Container]:
        """Deploy a WordPress instance with MySQL database"""
        if not self.check_system()[0]:
            self.logger.error("Cannot deploy WordPress: Podman system check failed")
            return None

        try:
            stack_name = f"wordpress-{user_id}"

            # Generate random passwords
            db_password = os.urandom(16).hex()
            wp_password = os.urandom(16).hex()

            # Deploy MySQL container
            mysql_container_create_result = subprocess.run(['podman', 'create', '--name', f"{stack_name}-mysql", '--env', f'MYSQL_ROOT_PASSWORD={db_password}', '--env', 'MYSQL_DATABASE=wordpress', '--env', 'MYSQL_USER=wordpress', '--env', f'MYSQL_PASSWORD={wp_password}', 'docker.io/mysql:8.0'], capture_output=True, text=True)

            # Deploy WordPress container
            wordpress_container_create_result = subprocess.run(['podman', 'create', '--name', f"{stack_name}-wordpress", '--env', 'WORDPRESS_DB_HOST=localhost', '--env', 'WORDPRESS_DB_USER=wordpress', '--env', f'WORDPRESS_DB_PASSWORD={wp_password}', '--env', 'WORDPRESS_DB_NAME=wordpress', '-p', '80:80', 'docker.io/wordpress:latest'], capture_output=True, text=True)

            if (mysql_container_create_result.returncode != 0 or wordpress_container_create_result.returncode != 0):
                self.logger.error("Failed to create containers")
                return None
            
            containers = [f"{stack_name}-mysql", f"{stack_name}-wordpress"]
            started_containers = []

            for container in containers:
                try:
                    self.logger.info(f"Starting container: {container}")
                    subprocess.run(['podman', 'start', container], check=True)
                    started_containers.append(container)
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Failed to start container {container}: {str(e)}")
                    # Clean up any containers that were started
                    for started in started_containers:
                        try:
                            subprocess.run(['podman', 'stop', started], check=True)
                            subprocess.run(['podman', 'rm', '-f', started], check=True)
                        except subprocess.CalledProcessError as e:
                            pass
                    return None
                except Exception as e:
                    self.logger.error(f"An unexpected error occurred while starting container {container}: {str(e)}")
                    return None

            # Get the assigned WordPress port
            wordpress_port = 80

            # Create Container record in database
            db_container = Container(
                container_id=f"{stack_name}-wordpress",
                name=stack_name,
                status='running',
                user_id=user_id,
                service_id=service.id,
                port=wordpress_port,
                environment={
                    'stack_name': stack_name,
                    'db_password': db_password,
                    'wp_password': wp_password
                }
            )

            return db_container

        except Exception as e:
            self.logger.error(f"Error deploying WordPress: {str(e)}")
            self.cleanup_wordpress(stack_name)
            return None

    def cleanup_wordpress(self, stack_name: str):
        """Remove WordPress deployment and associated volumes"""
        if not self.available:
            return

        try:
            containers = subprocess.run(['podman', 'ps', '-a', '--format', '{{.ID}} {{.Names}}'], capture_output=True, text=True).stdout.strip().split('\n')
            for container in containers:
                if container.strip() and container.split()[1].startswith(stack_name):
                    try:
                        subprocess.run(['podman', 'rm', '-f', container.split()[0]], check=True)
                    except subprocess.CalledProcessError as e:
                        self.logger.error(f"Failed to remove container {container.split()[1]}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error cleaning up WordPress deployment {stack_name}: {str(e)}")

    def deploy_service(self, service: Service, user_id: int, environment: Optional[Dict[str, Any]] = None) -> Optional[Container]:
        if not self.check_system()[0]:
            self.logger.error("Cannot deploy service: Podman system check failed")
            return None

        if service.name.lower() == 'wordpress':
            return self.deploy_wordpress(service, user_id)
        elif service.name.lower() == 'sites':
            return self.deploy_lemp_stack(service, user_id)

        try:
            if not service.container_image or not service.container_port:
                self.logger.error("Service does not have container configuration")
                return None

            container_name = f"{service.name.lower()}-{user_id}"
            environment = environment or {}

            self.logger.info(f"Pulling image: {service.container_image}")
            try:
                subprocess.run(['podman', 'pull', service.container_image], check=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to pull image {service.container_image}: {str(e)}")
                return None
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while pulling image {service.container_image}: {str(e)}")
                return None

            try:
                # Construct the podman create command with environment variables
                command = ['podman', 'create', '--name', container_name, '-p', f'{service.container_port}:{service.container_port}', service.container_image]
                for key, value in environment.items():
                    command.extend(['--env', f'{key}={value}'])

                subprocess.run(command, check=True)
                subprocess.run(['podman', 'start', container_name], check=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to create/start container: {str(e)}")
                return None
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while creating/starting container: {str(e)}")
                return None


            # Create Container record
            db_container = Container(
                container_id=container_name,
                name=container_name,
                status='running',
                user_id=user_id,
                service_id=service.id,
                port=service.container_port, # Assuming port mapping is successful
                environment=environment
            )

            return db_container

        except Exception as e:
            self.logger.error(f"Error deploying service: {str(e)}")
            return None

    def stop_container(self, container_id: str) -> bool:
        if not self.check_system()[0]:
            return False

        try:
            result = subprocess.run(['podman', 'stop', container_id], capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error stopping container: {str(e)}")
            return False

    def remove_container(self, container_id: str) -> bool:
        if not self.check_system()[0]:
            return False

        try:
            result = subprocess.run(['podman', 'rm', '-f', container_id], capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error removing container: {str(e)}")
            return False

    def get_container_status(self, container_id: str) -> Optional[str]:
        if not self.check_system()[0]:
            return None

        try:
            result = subprocess.run(['podman', 'inspect', '--format', '{{.State.Status}}', container_id], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            self.logger.error(f"Error getting container status: {str(e)}")
            return None

# Create a singleton instance
podman_manager = PodmanManager()