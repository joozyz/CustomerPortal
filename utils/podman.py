import podman
import logging
from typing import Optional, Dict, Any
from models import Container, Service

class PodmanManager:
    def __init__(self):
        try:
            # Initialize podman client with system connection
            self.client = podman.PodmanClient(uri='unix:///run/podman/podman.sock')
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            self.logger.error(f"Failed to initialize Podman client: {str(e)}")
            raise

    def deploy_service(self, service: Service, user_id: int, environment: Optional[Dict[str, Any]] = None) -> Optional[Container]:
        try:
            # Create container configuration
            container_name = f"{service.name.lower()}-{user_id}"
            environment = environment or {}

            # Pull the image
            self.logger.info(f"Pulling image: {service.container_image}")
            self.client.images.pull(service.container_image)

            # Create and start the container
            self.logger.info(f"Creating container: {container_name}")
            container = self.client.containers.create(
                name=container_name,
                image=service.container_image,
                environment=environment,
                ports={f'{service.container_port}/tcp': None},  # Dynamically assign host port
                detach=True
            )

            self.logger.info(f"Starting container: {container_name}")
            container.start()

            # Get the assigned port
            container_info = container.inspect()
            port_bindings = container_info['NetworkSettings']['Ports']
            host_port = None
            if f'{service.container_port}/tcp' in port_bindings:
                host_port = int(port_bindings[f'{service.container_port}/tcp'][0]['HostPort'])

            # Create Container record in database
            db_container = Container(
                container_id=container.id,
                name=container_name,
                status='running',
                user_id=user_id,
                service_id=service.id,
                port=host_port,
                environment=environment
            )

            return db_container

        except Exception as e:
            self.logger.error(f"Error deploying service: {str(e)}")
            return None

    def stop_container(self, container_id: str) -> bool:
        try:
            self.logger.info(f"Stopping container: {container_id}")
            container = self.client.containers.get(container_id)
            container.stop()
            return True
        except Exception as e:
            self.logger.error(f"Error stopping container: {str(e)}")
            return False

    def remove_container(self, container_id: str) -> bool:
        try:
            self.logger.info(f"Removing container: {container_id}")
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