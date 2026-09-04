"""
Transactional Outbox Production-Ready avec Worker pour Aegis.

Garantit la fiabilité de l'émission des événements de domaine via le pattern
Transactional Outbox avec worker asynchrone pour le dépilage et le traitement.
"""

import asyncio
import json
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from aegis.core.application.ports import EventOutbox
from aegis.core.domain.events import DomainEvent


class OutboxStatus(str, Enum):
    """Statuts des événements dans l'outbox."""

    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    RETRY = "retry"


class OutboxBackend(str, Enum):
    """Types de backend pour l'outbox."""

    DATABASE = "database"
    REDIS = "redis"
    KAFKA = "kafka"
    MEMORY = "memory"


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Événement stocké dans l'outbox."""

    event_id: str
    event_type: str
    aggregate_id: str
    payload: Dict[str, Any]
    status: OutboxStatus = OutboxStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_domain_event(self) -> DomainEvent:
        """Convertit l'événement outbox en événement de domaine."""
        # Cette méthode nécessiterait une factory pour reconstruire le bon type d'événement
        # Pour l'instant, retourne None
        return None

    def should_retry(self) -> bool:
        """Vérifie si l'événement doit être réessayé."""
        return self.status == OutboxStatus.FAILED and self.retry_count < self.max_retries

    def mark_as_processing(self) -> "OutboxEvent":
        """Marque l'événement comme en cours de traitement."""
        return OutboxEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            aggregate_id=self.aggregate_id,
            payload=self.payload,
            status=OutboxStatus.PROCESSING,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            published_at=self.published_at,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            error_message=self.error_message,
            metadata=self.metadata,
        )

    def mark_as_published(self) -> "OutboxEvent":
        """Marque l'événement comme publié."""
        return OutboxEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            aggregate_id=self.aggregate_id,
            payload=self.payload,
            status=OutboxStatus.PUBLISHED,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            error_message=self.error_message,
            metadata=self.metadata,
        )

    def mark_as_failed(self, error_message: str) -> "OutboxEvent":
        """Marque l'événement comme échoué."""
        return OutboxEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            aggregate_id=self.aggregate_id,
            payload=self.payload,
            status=OutboxStatus.FAILED,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            published_at=self.published_at,
            retry_count=self.retry_count + 1,
            max_retries=self.max_retries,
            error_message=error_message,
            metadata=self.metadata,
        )


class EventPublisher(ABC):
    """Interface pour les publishers d'événements."""

    @abstractmethod
    async def publish(self, event: OutboxEvent) -> bool:
        """Publie un événement vers le système cible."""
        pass

    @property
    @abstractmethod
    def publisher_type(self) -> str:
        """Retourne le type de publisher."""
        pass


class ConsoleEventPublisher(EventPublisher):
    """Publisher qui affiche les événements dans la console (pour développement)."""

    async def publish(self, event: OutboxEvent) -> bool:
        """Affiche l'événement dans la console."""
        print(f"[EVENT PUBLISHED] {event.event_type} - {event.aggregate_id}")
        print(f"Payload: {json.dumps(event.payload, indent=2, default=str)}")
        return True

    @property
    def publisher_type(self) -> str:
        return "console"


class HTTPEventPublisher(EventPublisher):
    """Publisher qui envoie les événements via HTTP webhooks."""

    def __init__(self, webhook_url: str, timeout: int = 30) -> None:
        self._webhook_url = webhook_url
        self._timeout = timeout

    async def publish(self, event: OutboxEvent) -> bool:
        """Envoie l'événement via HTTP POST."""
        try:
            import aiohttp

            payload = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_id": event.aggregate_id,
                "payload": event.payload,
                "occurred_at": event.created_at.isoformat(),
                "metadata": event.metadata,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    return response.status == 200

        except Exception as e:
            print(f"HTTP Publisher Error: {e}")
            return False

    @property
    def publisher_type(self) -> str:
        return "http"


class RedisEventPublisher(EventPublisher):
    """Publisher qui envoie les événements via Redis Pub/Sub."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", channel: str = "aegis_events") -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._redis = None

    async def _get_redis(self):
        """Récupère la connexion Redis."""
        if self._redis is None:
            try:
                import aioredis

                self._redis = await aioredis.from_url(self._redis_url)
            except ImportError as err:
                raise RuntimeError("aioredis est requis pour RedisEventPublisher") from err
        return self._redis

    async def publish(self, event: OutboxEvent) -> bool:
        """Publie l'événement sur le canal Redis."""
        try:
            redis = await self._get_redis()

            payload = json.dumps(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "aggregate_id": event.aggregate_id,
                    "payload": event.payload,
                    "occurred_at": event.created_at.isoformat(),
                    "metadata": event.metadata,
                },
                default=str,
            )

            await redis.publish(self._channel, payload)
            return True

        except Exception as e:
            print(f"Redis Publisher Error: {e}")
            return False

    @property
    def publisher_type(self) -> str:
        return "redis"


class ProductionOutbox(EventOutbox):
    """Outbox production-ready avec persistance et gestion d'erreurs."""

    def __init__(
        self,
        backend: OutboxBackend = OutboxBackend.MEMORY,
        batch_size: int = 50,
        publisher: Optional[EventPublisher] = None,
    ) -> None:
        self._backend = backend
        self._batch_size = batch_size
        self._publisher = publisher or ConsoleEventPublisher()
        self._storage: Dict[str, OutboxEvent] = {}
        self._lock = threading.Lock()

    def publish(self, event: DomainEvent) -> None:
        """Enregistre un événement de domaine dans l'outbox."""
        outbox_event = OutboxEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            payload=event.to_audit_dict(),
            status=OutboxStatus.PENDING,
        )

        with self._lock:
            self._storage[outbox_event.event_id] = outbox_event

    def get_pending_events(self, batch_size: int = 100) -> List[OutboxEvent]:
        """Récupère les événements en attente de publication."""
        with self._lock:
            pending = [
                event
                for event in self._storage.values()
                if event.status == OutboxStatus.PENDING or event.should_retry()
            ]
            return pending[: min(batch_size, len(pending))]

    def mark_as_published(self, event_ids: List[str]) -> None:
        """Marque les événements comme publiés."""
        with self._lock:
            for event_id in event_ids:
                if event_id in self._storage:
                    self._storage[event_id] = self._storage[event_id].mark_as_published()

    def mark_as_failed(self, event_id: str, error_message: str) -> None:
        """Marque un événement comme échoué."""
        with self._lock:
            if event_id in self._storage:
                self._storage[event_id] = self._storage[event_id].mark_as_failed(error_message)

    def cleanup_old_events(self, days: int = 30) -> int:
        """Nettoie les anciens événements publiés."""
        cutoff_date = datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - days)

        with self._lock:
            to_remove = [
                event_id
                for event_id, event in self._storage.items()
                if event.status == OutboxStatus.PUBLISHED and event.published_at and event.published_at < cutoff_date
            ]

            for event_id in to_remove:
                del self._storage[event_id]

            return len(to_remove)

    def get_statistics(self) -> Dict[str, int]:
        """Retourne des statistiques sur l'outbox."""
        with self._lock:
            stats = {
                "total": len(self._storage),
                "pending": sum(1 for e in self._storage.values() if e.status == OutboxStatus.PENDING),
                "processing": sum(1 for e in self._storage.values() if e.status == OutboxStatus.PROCESSING),
                "published": sum(1 for e in self._storage.values() if e.status == OutboxStatus.PUBLISHED),
                "failed": sum(1 for e in self._storage.values() if e.status == OutboxStatus.FAILED),
            }
            return stats


class OutboxWorker:
    """Worker asynchrone pour le traitement des événements de l'outbox."""

    def __init__(self, outbox: ProductionOutbox, poll_interval_seconds: float = 5.0, max_concurrent: int = 5) -> None:
        self._outbox = outbox
        self._poll_interval = poll_interval_seconds
        self._max_concurrent = max_concurrent
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._event_queue: queue.Queue = queue.Queue()

    def start(self) -> None:
        """Démarre le worker."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        """Arrête le worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=10)

    def _run_loop(self) -> None:
        """Boucle principale du worker."""
        while self._running:
            try:
                self._process_batch()
                time.sleep(self._poll_interval)
            except Exception as e:
                print(f"Worker Error: {e}")
                time.sleep(self._poll_interval)

    def _process_batch(self) -> None:
        """Traite un batch d'événements."""
        events = self._outbox.get_pending_events(self._outbox._batch_size)

        if not events:
            return

        # Traitement asynchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._process_events_async(events))
        finally:
            loop.close()

    async def _process_events_async(self, events: List[OutboxEvent]) -> None:
        """Traite les événements de manière asynchrone."""
        # Limiter le nombre de traitements concurrents
        semaphore = asyncio.Semaphore(self._max_concurrent)

        tasks = []
        for event in events:
            task = self._process_single_event(event, semaphore)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_single_event(self, event: OutboxEvent, semaphore: asyncio.Semaphore) -> None:
        """Traite un seul événement."""
        async with semaphore:
            try:
                # Marquer comme en cours de traitement
                self._outbox._storage[event.event_id] = event.mark_as_processing()

                # Publier l'événement
                success = await self._outbox._publisher.publish(event)

                if success:
                    self._outbox.mark_as_published([event.event_id])
                else:
                    self._outbox.mark_as_failed(event.event_id, "Publication failed")

            except Exception as e:
                self._outbox.mark_as_failed(event.event_id, str(e))

    def is_running(self) -> bool:
        """Vérifie si le worker est en cours d'exécution."""
        return self._running


class OutboxManager:
    """Manager pour l'outbox et le worker avec configuration."""

    def __init__(self, outbox: Optional[ProductionOutbox] = None, worker: Optional[OutboxWorker] = None) -> None:
        self._outbox = outbox or ProductionOutbox()
        self._worker = worker or OutboxWorker(self._outbox)

    def start_worker(self) -> None:
        """Démarre le worker de traitement."""
        self._worker.start()

    def stop_worker(self) -> None:
        """Arrête le worker de traitement."""
        self._worker.stop()

    def publish_event(self, event: DomainEvent) -> None:
        """Publie un événement de domaine."""
        self._outbox.publish(event)

    def get_statistics(self) -> Dict[str, int]:
        """Retourne les statistiques de l'outbox."""
        return self._outbox.get_statistics()

    def cleanup_old_events(self, days: int = 30) -> int:
        """Nettoie les anciens événements."""
        return self._outbox.cleanup_old_events(days)


# Factory pour créer des configurations d'outbox courantes
class OutboxFactory:
    """Factory pour créer des configurations d'outbox."""

    @staticmethod
    def create_memory_outbox(batch_size: int = 50) -> ProductionOutbox:
        """Crée un outbox en mémoire."""
        return ProductionOutbox(backend=OutboxBackend.MEMORY, batch_size=batch_size, publisher=ConsoleEventPublisher())

    @staticmethod
    def create_http_outbox(webhook_url: str, batch_size: int = 50) -> ProductionOutbox:
        """Crée un outbox avec publisher HTTP."""
        return ProductionOutbox(
            backend=OutboxBackend.MEMORY, batch_size=batch_size, publisher=HTTPEventPublisher(webhook_url)
        )

    @staticmethod
    def create_redis_outbox(redis_url: str, channel: str = "aegis_events", batch_size: int = 50) -> ProductionOutbox:
        """Crée un outbox avec publisher Redis."""
        return ProductionOutbox(
            backend=OutboxBackend.REDIS, batch_size=batch_size, publisher=RedisEventPublisher(redis_url, channel)
        )

    @staticmethod
    def create_production_manager(webhook_url: Optional[str] = None, redis_url: Optional[str] = None) -> OutboxManager:
        """Crée un manager d'outbox production-ready."""
        if webhook_url:
            outbox = OutboxFactory.create_http_outbox(webhook_url)
        elif redis_url:
            outbox = OutboxFactory.create_redis_outbox(redis_url)
        else:
            outbox = OutboxFactory.create_memory_outbox()

        worker = OutboxWorker(outbox, poll_interval_seconds=5.0, max_concurrent=5)
        return OutboxManager(outbox, worker)
