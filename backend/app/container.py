"""
Container orchestration for isolated user terminals.

Architecture decisions (documented):
1. ONE CONTAINER PER USER (pool), not one per terminal session.
   - Container startup latency (~1-3s) is paid once per user; subsequent
     terminal tabs use `docker exec` inside the same container.
   - Each container runs as a non-root user with a read-only rootfs, tmpfs
     writable dirs, all capabilities dropped, no-new-privileges,
     network disabled, and no Docker socket mounted.
   - This gives per-user filesystem isolation without the overhead of
     booting a container per terminal tab.
2. The Docker socket is NOT mounted into user containers. The backend talks
   to the Docker daemon over the host socket (default unix:///var/run/docker.sock).
   This socket itself must be protected on the host (rootless Docker or
   restricted group access).
3. In this development environment Docker is not available, so all container
   operations degrade gracefully by raising DockerUnavailable. Auth/DB/WS
   flows remain fully testable here.

Security model (defense in depth):
  - Container runs as uid 1000 (non-root).
  - read-only rootfs; only /tmp, /home/appuser/work are writable tmpfs.
  - cap-drop ALL; no new privileges.
  - network=none (no outbound/inbound network from the container).
  - no /var/run/docker.sock, no /proc/sys, no host mounts.
  - pids/memory/cpu limits enforced per container.
  - Processes cannot escape to the host or to other users' containers.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

from .logging import get_logger

logger = get_logger(__name__)


class DockerUnavailable(RuntimeError):
    """Raised when Docker orchestration cannot be performed (dev/offline)."""


class ContainerManager:
    """Manages one isolated container per user and exec sessions within it."""

    def __init__(self) -> None:
        self.enabled = os.getenv("DOCKER_ENABLED", "true").lower() == "true"
        self.host = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
        self.image = os.getenv("TERMINAL_IMAGE", "ubuntu:22.04")
        self._client = None
        self._lock = threading.Lock()
        self._docker_error: Optional[str] = None
        self._containers: dict[int, dict] = {}  # user_id -> container info

    # ------------------------------------------------------------------ #
    # Docker client (lazy, degraded when unavailable)
    # ------------------------------------------------------------------ #
    def _get_client(self):
        if not self.enabled:
            raise DockerUnavailable("Docker orchestration disabled (DOCKER_ENABLED=false)")
        if self._client is not None:
            return self._client
        if self._docker_error:
            raise DockerUnavailable(self._docker_error)
        try:
            import docker  # type: ignore
            self._client = docker.DockerClient(base_url=self.host, timeout=5)
            # Probe the daemon.
            self._client.ping()
            self._ensure_image()
            logger.info("Connected to Docker daemon at %s", self.host)
            return self._client
        except Exception as exc:
            self._docker_error = str(exc)
            self._client = None
            logger.warning("Docker unavailable: %s", exc)
            raise DockerUnavailable(str(exc))

    def _ensure_image(self) -> None:
        assert self._client is not None
        try:
            self._client.images.get(self.image)
        except Exception:
            logger.info("Pulling terminal image %s ...", self.image)
            self._client.images.pull(self.image)

    # ------------------------------------------------------------------ #
    # Container lifecycle
    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        try:
            self._get_client()
            return True
        except DockerUnavailable:
            return False

    def ensure_user_container(self, user_id: int) -> dict:
        """Return (and create if needed) the isolated container for a user."""
        with self._lock:
            existing = self._containers.get(user_id)
            if existing:
                # Verify the container is still running.
                try:
                    c = self._get_client().containers.get(existing["container_name"])
                    if c.status == "running":
                        return existing
                except Exception:
                    pass
                # Stale entry; remove and recreate.
                self._stop_container_locked(user_id)

            client = self._get_client()
            name = f"term-user-{user_id}"
            # Remove any previously stopped container with the same name.
            try:
                old = client.containers.get(name)
                old.remove(force=True)
            except Exception:
                pass

            host_config = client.api.create_host_config(
                # Isolation controls
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                network_mode="none",
                pids_limit=int(os.getenv("DEFAULT_PIDS_LIMIT", "64")),
                mem_limit=f"{int(os.getenv('DEFAULT_RAM_LIMIT_MB', '512'))}m",
                mem_swap=f"{int(os.getenv('DEFAULT_RAM_LIMIT_MB', '512'))}m",
                cpu_quota=int(float(os.getenv("DEFAULT_CPU_LIMIT", "1.0")) * 100000),
                cpu_period=100000,
                # No privileged access, no docker socket
                auto_remove=False,
            )
            # Writable tmpfs dirs on read-only rootfs.
            mounts = [
                "/tmp",
                "/home/appuser/work",
            ]

            container = client.containers.run(
                self.image,
                command=["sleep", "infinity"],
                name=name,
                detach=True,
                tty=True,
                stdin_open=True,
                user="1000:1000",  # non-root
                read_only=True,
                tmpfs={
                    "/tmp": "rw,noexec,nosuid,size=64m",
                    "/home/appuser/work": "rw,noexec,nosuid,size=64m",
                },
                host_config=host_config,
                environment={
                    "USER": "appuser",
                    "HOME": "/home/appuser",
                    "TERM": "xterm-256color",
                },
            )
            info = {
                "container_name": name,
                "container_id": container.id,
                "created_at": time.time(),
            }
            self._containers[user_id] = info
            logger.info("Created isolated container %s for user %d", name, user_id)
            return info

    def _stop_container_locked(self, user_id: int) -> None:
        info = self._containers.pop(user_id, None)
        if not info:
            return
        try:
            client = self._get_client()
            c = client.containers.get(info["container_name"])
            try:
                c.stop(timeout=5)
            except Exception:
                pass
            try:
                c.remove(force=True)
            except Exception:
                pass
        except DockerUnavailable:
            pass
        except Exception as exc:
            logger.warning("Error stopping container for user %d: %s", user_id, exc)

    def stop_user_container(self, user_id: int) -> None:
        with self._lock:
            self._stop_container_locked(user_id)

    def stop_all_containers(self) -> None:
        with self._lock:
            for user_id in list(self._containers.keys()):
                self._stop_container_locked(user_id)

    # ------------------------------------------------------------------ #
    # Exec (terminal session) lifecycle
    # ------------------------------------------------------------------ #
    def create_exec(
        self,
        user_id: int,
        command: str = "/bin/bash",
        cols: int = 80,
        rows: int = 24,
    ) -> dict:
        """Start an exec session inside the user's container.

        Returns a dict with exec_id and container info for WS pumping.
        """
        with self._lock:
            container = self.ensure_user_container(user_id)
        client = self._get_client()
        c = client.containers.get(container["container_name"])
        exec_id = c.exec_run(
            command,
            tty=True,
            stdin=True,
            stdout=True,
            stderr=True,
            privileged=False,
            user="1000:1000",
            workdir="/home/appuser/work",
        ).id
        # Resize the PTY.
        try:
            client.api.exec_resize(exec_id, height=rows, width=cols)
        except Exception:
            pass
        info = {
            "exec_id": exec_id,
            "container_name": container["container_name"],
            "container_id": container["container_id"],
            "user_id": user_id,
            "command": command,
            "cols": cols,
            "rows": rows,
            "created_at": time.time(),
        }
        logger.info("Created exec %s for user %d", exec_id, user_id)
        return info

    def resize_exec(self, exec_id: str, cols: int, rows: int) -> None:
        try:
            client = self._get_client()
            client.api.exec_resize(exec_id, height=rows, width=cols)
        except DockerUnavailable:
            pass
        except Exception as exc:
            logger.warning("Failed to resize exec %s: %s", exec_id, exc)

    def stop_exec(self, exec_id: str) -> None:
        """Best-effort stop of an exec session."""
        try:
            client = self._get_client()
            # exec sessions cannot be 'stopped' individually; close the stream.
            # We note the exec as ended by letting the WS side close.
        except DockerUnavailable:
            pass
        except Exception as exc:
            logger.warning("Failed to stop exec %s: %s", exec_id, exc)

    # ------------------------------------------------------------------ #
    # Stats / resource monitoring
    # ------------------------------------------------------------------ #
    def container_stats(self, user_id: int) -> Optional[dict]:
        """Return current resource usage for a user's container."""
        try:
            with self._lock:
                container = self._containers.get(user_id)
            if not container:
                return None
            client = self._get_client()
            c = client.containers.get(container["container_name"])
            stats = c.stats(stream=False)
            return self._parse_stats(stats)
        except DockerUnavailable:
            return None
        except Exception as exc:
            logger.warning("Failed to get stats for user %d: %s", user_id, exc)
            return None

    @staticmethod
    def _parse_stats(stats: dict) -> dict:
        # CPU percentage
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta >= 0:
            cpu_percent = (cpu_delta / system_delta) * 100.0 * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])

        # Memory usage
        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 0)
        mem_percent = (mem_usage / mem_limit * 100.0) if mem_limit else 0.0

        # Pids
        pids = stats.get("pids_stats", {}).get("current", 0)

        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_usage_mb": round(mem_usage / (1024 * 1024), 2),
            "memory_limit_mb": round(mem_limit / (1024 * 1024), 2),
            "memory_percent": round(mem_percent, 2),
            "pids": pids,
        }


# Singleton instance used by routes.
container_manager = ContainerManager()
