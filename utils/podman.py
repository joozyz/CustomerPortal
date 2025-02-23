import podman
import logging
from typing import Optional, Dict, Any, List, Tuple
from models import Container, Service
import os

class PodmanManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        try:
            self.connect()
        except Exception as e:
            self.logger.warning(f"Podman initialization failed (this is okay if Podman is not required): {str(e)}")

    def connect(self) -> bool:
        """Initialize connection to Podman"""
        try:
            # Try rootless connection first
            uri = 'unix:///run/user/1000/podman/podman.sock'
            self.client = podman.PodmanClient(uri=uri)
            # Test connection by listing containers
            self.client.containers.list()
            self.logger.info("Successfully connected to Podman (rootless)")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to connect to Podman (non-critical): {str(e)}")
            return False

    def check_system(self) -> Tuple[bool, str]:
        """Check Podman system status and return (is_healthy, status_message)"""
        try:
            if not self.client:
                return False, "Podman service unavailable"

            # Test connection by listing images
            self.client.images.list()

            # Get Podman version info
            version = self.client.version()

            return True, f"Podman {version['Version']} running"
        except Exception as e:
            error_msg = str(e)
            self.logger.warning(f"Podman system check failed (non-critical): {error_msg}")
            return False, f"Podman service unavailable"

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
                    self.client.images.pull(image)
                except Exception as e:
                    self.logger.error(f"Failed to pull image {image}: {str(e)}")
                    return None

            # Create MariaDB container
            db_container = self.client.containers.create(
                name=f"{stack_name}-db",
                image='docker.io/mariadb:latest',
                environment={
                    'MYSQL_ROOT_PASSWORD': 'changeme',
                    'MYSQL_DATABASE': 'wordpress',
                    'MYSQL_USER': 'wordpress',
                    'MYSQL_PASSWORD': 'wordpress'
                },
                detach=True
            )

            # Create PHP-FPM container
            php_container = self.client.containers.create(
                name=f"{stack_name}-php",
                image='docker.io/php:8.2-fpm',
                detach=True
            )

            # Create Nginx container with port mapping
            nginx_container = self.client.containers.create(
                name=f"{stack_name}-nginx",
                image='docker.io/nginx:latest',
                ports={'80/tcp': None},  # Dynamically assign host port
                detach=True
            )

            # Create Adminer container
            adminer_container = self.client.containers.create(
                name=f"{stack_name}-adminer",
                image='docker.io/adminer:latest',
                ports={'8080/tcp': None},
                detach=True
            )

            # Start containers in order
            containers = [db_container, php_container, nginx_container, adminer_container]
            started_containers = []

            for container in containers:
                try:
                    self.logger.info(f"Starting container: {container.name}")
                    container.start()
                    started_containers.append(container)
                except Exception as e:
                    self.logger.error(f"Failed to start container {container.name}: {str(e)}")
                    # Clean up any containers that were started
                    for started in started_containers:
                        try:
                            started.stop()
                            started.remove()
                        except:
                            pass
                    return None

            # Get the assigned Nginx port
            nginx_info = nginx_container.inspect()
            nginx_port = int(nginx_info['NetworkSettings']['Ports']['80/tcp'][0]['HostPort'])

            # Create Container record in database
            db_container = Container(
                container_id=nginx_container.id,  # Use Nginx container as main reference
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
        if not self.client:
            return

        try:
            containers = self.client.containers.list(all=True)
            for container in containers:
                if container.name.startswith(stack_name):
                    try:
                        container.remove(force=True)
                    except Exception as e:
                        self.logger.error(f"Failed to remove container {container.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error cleaning up stack {stack_name}: {str(e)}")

    def deploy_wordpress(self, service: Service, user_id: int) -> Optional[Container]:
        """Deploy a WordPress instance with MySQL database"""
        if not self.check_system()[0]:
            self.logger.error("Cannot deploy WordPress: Podman system check failed")
            return None

        try:
            stack_name = f"wordpress-{user_id}"

            # Create a pod for WordPress and MySQL
            pod = self.client.pods.create(name=stack_name)

            # Generate random passwords
            db_password = os.urandom(16).hex()
            wp_password = os.urandom(16).hex()

            # Deploy MySQL container
            mysql_container = self.client.containers.create(
                name=f"{stack_name}-mysql",
                image='docker.io/mysql:8.0',
                environment={
                    'MYSQL_ROOT_PASSWORD': db_password,
                    'MYSQL_DATABASE': 'wordpress',
                    'MYSQL_USER': 'wordpress',
                    'MYSQL_PASSWORD': wp_password
                },
                pod=pod.id,
                volumes=[f"{stack_name}-mysql-data:/var/lib/mysql"]
            )

            # Deploy WordPress container
            wordpress_container = self.client.containers.create(
                name=f"{stack_name}-wordpress",
                image='docker.io/wordpress:latest',
                environment={
                    'WORDPRESS_DB_HOST': 'localhost',
                    'WORDPRESS_DB_USER': 'wordpress',
                    'WORDPRESS_DB_PASSWORD': wp_password,
                    'WORDPRESS_DB_NAME': 'wordpress'
                },
                pod=pod.id,
                ports={'80/tcp': None},
                volumes=[f"{stack_name}-wordpress:/var/www/html"]
            )

            # Start the pod which will start all containers
            pod.start()

            # Get the assigned WordPress port
            pod_info = pod.inspect()
            wordpress_port = int(pod_info['Ports'][0]['HostPort'])

            # Create Container record in database
            db_container = Container(
                container_id=pod.id,
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
        if not self.client:
            return

        try:
            # Remove the pod (this will remove all containers in the pod)
            pods = self.client.pods.list()
            for pod in pods:
                if pod.name == stack_name:
                    pod.remove(force=True)

            # Remove volumes
            volumes = self.client.volumes.list()
            for volume in volumes:
                if volume.name.startswith(stack_name):
                    volume.remove(force=True)

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
                self.client.images.pull(service.container_image)
            except Exception as e:
                self.logger.error(f"Failed to pull image {service.container_image}: {str(e)}")
                return None

            try:
                container = self.client.containers.create(
                    name=container_name,
                    image=service.container_image,
                    environment=environment,
                    ports={f'{service.container_port}/tcp': None},
                    detach=True
                )
                container.start()
            except Exception as e:
                self.logger.error(f"Failed to create/start container: {str(e)}")
                return None

            # Create Container record
            db_container = Container(
                container_id=container.id,
                name=container_name,
                status='running',
                user_id=user_id,
                service_id=service.id,
                port=container.ports[f'{service.container_port}/tcp'][0]['HostPort'],
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
            container = self.client.containers.get(container_id)
            container.stop()
            return True
        except Exception as e:
            self.logger.error(f"Error stopping container: {str(e)}")
            return False

    def remove_container(self, container_id: str) -> bool:
        if not self.check_system()[0]:
            return False

        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            return True
        except Exception as e:
            self.logger.error(f"Error removing container: {str(e)}")
            return False

    def get_container_status(self, container_id: str) -> Optional[str]:
        if not self.check_system()[0]:
            return None

        try:
            container = self.client.containers.get(container_id)
            return container.status
        except Exception as e:
            self.logger.error(f"Error getting container status: {str(e)}")
            return None

# Create a singleton instance
podman_manager = PodmanManager()