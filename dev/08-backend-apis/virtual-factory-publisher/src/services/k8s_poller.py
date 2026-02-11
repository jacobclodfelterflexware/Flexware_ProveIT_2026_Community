"""Polls Kubernetes API for pod/node state and metrics, publishes to MQTT."""
import asyncio
import logging
from datetime import datetime, timezone

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)

NAMESPACES = [
    "services",
    "frontends",
    "backend-apis",
    "emqx-curated",
    "neo4j",
    "data-sources",
]


class K8sPoller:
    """
    Polls Kubernetes API for pod status, resource usage, and node state.
    Publishes to VirtualFactory2.0/kubernetes/...
    """

    def __init__(self, publisher: MQTTPublisher):
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._last_poll: datetime | None = None
        self.pods_published = 0
        self.nodes_published = 0

        # Init k8s client (in-cluster)
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        self._core = client.CoreV1Api()
        self._custom = client.CustomObjectsApi()

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("K8s poller started")

    async def stop(self) -> None:
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        prefix = config.topic_prefix
        while self._is_running:
            try:
                await self._poll_all(prefix)
            except Exception as e:
                logger.error(f"K8s poll error: {e}")
            await asyncio.sleep(config.k8s_poll_interval)

    async def _poll_all(self, prefix: str) -> None:
        loop = asyncio.get_event_loop()

        # Run blocking k8s API calls in executor
        pods_by_ns = {}
        for ns in NAMESPACES:
            try:
                pod_list = await loop.run_in_executor(
                    None, lambda n=ns: self._core.list_namespaced_pod(n)
                )
                pods_by_ns[ns] = pod_list.items
            except ApiException as e:
                logger.warning(f"K8s: failed to list pods in {ns}: {e.reason}")

        # Get pod metrics
        pod_metrics = {}
        for ns in NAMESPACES:
            try:
                metrics = await loop.run_in_executor(
                    None,
                    lambda n=ns: self._custom.list_namespaced_custom_object(
                        "metrics.k8s.io", "v1beta1", n, "pods"
                    ),
                )
                for item in metrics.get("items", []):
                    key = f"{ns}/{item['metadata']['name']}"
                    containers = item.get("containers", [])
                    if containers:
                        cpu_total = sum(
                            self._parse_cpu(c.get("usage", {}).get("cpu", "0"))
                            for c in containers
                        )
                        mem_total = sum(
                            self._parse_memory(c.get("usage", {}).get("memory", "0"))
                            for c in containers
                        )
                        pod_metrics[key] = {
                            "cpuMillicores": cpu_total,
                            "memoryMi": round(mem_total, 1),
                        }
            except ApiException:
                pass

        # Publish pod data
        for ns, pods in pods_by_ns.items():
            for pod in pods:
                name = pod.metadata.name
                base = f"{prefix}/kubernetes/pods/{ns}/{name}"

                # Status
                phase = pod.status.phase
                ready = False
                restarts = 0
                container_statuses = []

                if pod.status.container_statuses:
                    for cs in pod.status.container_statuses:
                        ready = ready or cs.ready
                        restarts += cs.restart_count
                        container_statuses.append({
                            "name": cs.name,
                            "ready": cs.ready,
                            "restartCount": cs.restart_count,
                            "started": cs.started,
                        })

                await self.publisher.publish(f"{base}/status", {
                    "phase": phase,
                    "ready": ready,
                    "restarts": restarts,
                    "containers": container_statuses,
                })

                # Resources (requests/limits + live usage)
                resources = {}
                if pod.spec.containers:
                    c = pod.spec.containers[0]
                    req = c.resources.requests or {} if c.resources else {}
                    lim = c.resources.limits or {} if c.resources else {}
                    resources = {
                        "requests": {k: str(v) for k, v in req.items()},
                        "limits": {k: str(v) for k, v in lim.items()},
                    }

                metrics_key = f"{ns}/{name}"
                if metrics_key in pod_metrics:
                    resources["usage"] = pod_metrics[metrics_key]

                if resources:
                    await self.publisher.publish(f"{base}/resources", resources)

                self.pods_published += 1

        # Get nodes
        try:
            node_list = await loop.run_in_executor(
                None, self._core.list_node
            )
        except ApiException as e:
            logger.warning(f"K8s: failed to list nodes: {e.reason}")
            node_list = None

        # Get node metrics
        node_metrics = {}
        try:
            nm = await loop.run_in_executor(
                None,
                lambda: self._custom.list_cluster_custom_object(
                    "metrics.k8s.io", "v1beta1", "nodes"
                ),
            )
            for item in nm.get("items", []):
                node_name = item["metadata"]["name"]
                usage = item.get("usage", {})
                node_metrics[node_name] = {
                    "cpuMillicores": self._parse_cpu(usage.get("cpu", "0")),
                    "memoryMi": round(
                        self._parse_memory(usage.get("memory", "0")), 1
                    ),
                }
        except ApiException:
            pass

        if node_list:
            for node in node_list.items:
                name = node.metadata.name
                base = f"{prefix}/kubernetes/nodes/{name}"

                # Conditions
                conditions = {}
                if node.status.conditions:
                    for cond in node.status.conditions:
                        conditions[cond.type] = cond.status

                await self.publisher.publish(f"{base}/status", {
                    "conditions": conditions,
                })

                # Resources
                alloc = node.status.allocatable or {}
                cap = node.status.capacity or {}
                node_res = {
                    "allocatable": {k: str(v) for k, v in alloc.items()},
                    "capacity": {k: str(v) for k, v in cap.items()},
                }
                if name in node_metrics:
                    node_res["usage"] = node_metrics[name]

                await self.publisher.publish(f"{base}/resources", node_res)
                self.nodes_published += 1

        self._last_poll = datetime.now(timezone.utc)

    @staticmethod
    def _parse_cpu(value: str) -> int:
        """Parse k8s CPU value to millicores."""
        if value.endswith("n"):
            return int(value[:-1]) // 1_000_000
        if value.endswith("u"):
            return int(value[:-1]) // 1_000
        if value.endswith("m"):
            return int(value[:-1])
        try:
            return int(float(value) * 1000)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_memory(value: str) -> float:
        """Parse k8s memory value to MiB."""
        if value.endswith("Ki"):
            return int(value[:-2]) / 1024
        if value.endswith("Mi"):
            return int(value[:-2])
        if value.endswith("Gi"):
            return int(value[:-2]) * 1024
        if value.endswith("Ti"):
            return int(value[:-2]) * 1024 * 1024
        try:
            return int(value) / (1024 * 1024)
        except (ValueError, TypeError):
            return 0

    def get_stats(self) -> dict:
        return {
            "pods_published": self.pods_published,
            "nodes_published": self.nodes_published,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
        }
