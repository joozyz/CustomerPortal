import podman
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from models import Container

logger = logging.getLogger(__name__)

class PodmanManager:
    def __init__(self):
        try:
            self.client = podman.PodmanClient(base_url='unix:///run/podman/podman.sock')
            logger.info("Successfully connected to Podman")
        except Exception as e:
            logger.error(f"Failed to connect to Podman: {str(e)}")
            self.client = None

    def check_system(self) -> Tuple[bool, str]:
        """Check if Podman system is available and running"""
        try:
            if not self.client:
                return False, "Podman client not initialized"

            version = self.client.version()
            return True, f"Podman {version['Version']} running"
        except Exception as e:
            logger.error(f"Podman system check failed: {str(e)}")
            return False, str(e)

    def get_system_health(self) -> str:
        """Get overall system health status"""
        try:
            if not self.client:
                return "unhealthy"

            # Check basic connectivity
            status, _ = self.check_system()
            if not status:
                return "unhealthy"

            # Check container health
            containers = self.client.containers.list()
            unhealthy_containers = 0
            for container in containers:
                if container.status not in ['running', 'created']:
                    unhealthy_containers += 1

            return "healthy" if unhealthy_containers == 0 else "degraded"
        except Exception as e:
            logger.error(f"Failed to get system health: {str(e)}")
            return "unhealthy"

    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed system health information"""
        try:
            if not self.client:
                return {
                    'status': 'error',
                    'podman_available': False,
                    'message': 'Podman client not initialized'
                }

            # Get Podman version and info
            version = self.client.version()
            info = self.client.info()

            # Get container statistics
            containers = self.client.containers.list(all=True)
            container_stats = {
                'total': len(containers),
                'running': len([c for c in containers if c.status == 'running']),
                'stopped': len([c for c in containers if c.status == 'stopped']),
                'failed': len([c for c in containers if c.status == 'exited'])
            }

            # Get system resources
            return {
                'status': 'ok',
                'podman_available': True,
                'version': version['Version'],
                'containers': container_stats,
                'system_info': {
                    'os': info['host']['os'],
                    'kernel': info['host']['kernel'],
                    'memory': info['host']['memTotal'],
                    'cpu_count': info['host']['cpus']
                }
            }
        except Exception as e:
            logger.error(f"Failed to get detailed health: {str(e)}")
            return {
                'status': 'error',
                'podman_available': False,
                'message': str(e)
            }

    def deploy_service(self, service, user_id, environment=None):
        """Deploy a service as a container"""
        try:
            if not self.client:
                logger.error("Podman client not initialized")
                return None

            container_name = f"{service.name.lower()}-{user_id}"

            # Prepare container configuration
            container_config = {
                'Image': service.container_image,
                'Name': container_name,
                'HostConfig': {
                    'CpuQuota': int(service.cpu_quota * 100000),  # Convert cores to quota
                    'Memory': service.memory_quota * 1024 * 1024,  # Convert MB to bytes
                    'PortBindings': {
                        f'{service.container_port}/tcp': [{'HostPort': '0'}]  # Dynamic port allocation
                    }
                },
                'Env': [f"{k}={v}" for k, v in (environment or {}).items()]
            }

            # Create and start the container
            container = self.client.containers.create(**container_config)
            container.start()

            # Get the assigned host port
            container_info = container.inspect()
            host_port = int(container_info['NetworkSettings']['Ports'][f'{service.container_port}/tcp'][0]['HostPort'])

            # Create Container record
            new_container = Container(
                container_id=container.id,
                name=container_name,
                status='running',
                user_id=user_id,
                service_id=service.id,
                port=host_port,
                environment=environment,
                last_monitored=datetime.utcnow()
            )

            return new_container

        except Exception as e:
            logger.error(f"Failed to deploy service: {str(e)}")
            return None

    def get_container_status(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get current status and metrics of a container"""
        try:
            if not self.client:
                return None

            container = self.client.containers.get(container_id)
            container_info = container.inspect()

            # Update container metrics
            stats = container.stats(stream=False)
            cpu_stats = stats['cpu_stats']
            memory_stats = stats['memory_stats']

            return {
                'status': container_info['State']['Status'],
                'cpu_usage': cpu_stats['cpu_usage']['total_usage'] / cpu_stats['system_cpu_usage'],
                'memory_usage': memory_stats['usage'] / (1024 * 1024),  # Convert to MB
                'uptime': container_info['State']['StartedAt']
            }

        except Exception as e:
            logger.error(f"Failed to get container status: {str(e)}")
            return None

    def stop_container(self, container_id: str) -> bool:
        """Stop a running container"""
        try:
            if not self.client:
                return False

            container = self.client.containers.get(container_id)
            container.stop()
            return True

        except Exception as e:
            logger.error(f"Failed to stop container: {str(e)}")
            return False

    def remove_container(self, container_id: str) -> bool:
        """Remove a container"""
        try:
            if not self.client:
                return False

            container = self.client.containers.get(container_id)
            container.remove(force=True)
            return True

        except Exception as e:
            logger.error(f"Failed to remove container: {str(e)}")
            return False

# Create a singleton instance
podman_manager = PodmanManager()