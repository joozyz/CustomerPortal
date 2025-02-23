import podman
import logging
from typing import Optional, Dict, Any, List
from models import Container, Service

class PodmanManager:
    def __init__(self):
        try:
            # Initialize podman client with rootless connection
            self.client = podman.PodmanClient(uri='unix:///run/user/1000/podman/podman.sock')
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            self.logger.error(f"Failed to initialize Podman client: {str(e)}")
            raise

    def deploy_lemp_stack(self, service: Service, user_id: int) -> Optional[Container]:
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
            for container in [db_container, php_container, nginx_container, adminer_container]:
                try:
                    container.start()
                except Exception as e:
                    self.logger.error(f"Failed to start container {container.name}: {str(e)}")
                    self.cleanup_stack(stack_name)
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
        try:
            containers = self.client.containers.list(all=True)
            for container in containers:
                if container.name.startswith(stack_name):
                    try:
                        container.remove(force=True)
                    except:
                        pass
        except Exception as e:
            self.logger.error(f"Error cleaning up stack {stack_name}: {str(e)}")

    def deploy_service(self, service: Service, user_id: int, environment: Optional[Dict[str, Any]] = None) -> Optional[Container]:
        if service.name.lower() == 'sites':
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
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            return True
        except Exception as e:
            self.logger.error(f"Error stopping container: {str(e)}")
            return False

    def remove_container(self, container_id: str) -> bool:
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            return True
        except Exception as e:
            self.logger.error(f"Error removing container: {str(e)}")
            return False

    def get_container_status(self, container_id: str) -> Optional[str]:
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except Exception as e:
            self.logger.error(f"Error getting container status: {str(e)}")
            return None

# Create a singleton instance
podman_manager = PodmanManager()