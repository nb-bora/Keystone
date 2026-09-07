"""
Système de Cache des Décisions d'Autorisation pour Aegis.

Optimise les performances en mettant en cache les décisions d'autorisation
avec support pour différents backends (memory, Redis) et stratégies d'invalidation.
"""

import hashlib
import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Set

from aegis.core.domain.policies import PolicyDecision


class CacheBackend(str, Enum):
    """Types de backend pour le cache."""

    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


class CacheEvictionPolicy(str, Enum):
    """Politiques d'éviction du cache."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Clé de cache pour les décisions d'autorisation."""

    subject_id: str
    action: str
    resource_id: str
    context_hash: str
    policy_engine: str = "rbac"

    def to_string(self) -> str:
        """Convertit la clé en string pour le stockage."""
        return f"auth:{self.subject_id}:{self.action}:{self.resource_id}:{self.context_hash}:{self.policy_engine}"

    @classmethod
    def from_components(
        cls, subject_id: str, action: str, resource_id: str, context: Dict[str, Any], policy_engine: str = "rbac"
    ) -> "CacheKey":
        """Crée une clé depuis les composants."""
        # Hasher le contexte pour créer une clé stable
        context_str = json.dumps(context, sort_keys=True, default=str)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]

        return cls(
            subject_id=subject_id,
            action=action,
            resource_id=resource_id,
            context_hash=context_hash,
            policy_engine=policy_engine,
        )


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Entrée de cache pour une décision d'autorisation."""

    decision: PolicyDecision
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 300  # 5 minutes par défaut
    access_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self) -> bool:
        """Vérifie si l'entrée a expiré."""
        return datetime.now(timezone.utc) > self.cached_at + timedelta(seconds=self.ttl_seconds)

    def is_valid(self) -> bool:
        """Vérifie si l'entrée est valide."""
        return not self.is_expired()

    def record_access(self) -> "CacheEntry":
        """Enregistre un accès à l'entrée."""
        return CacheEntry(
            decision=self.decision,
            cached_at=self.cached_at,
            ttl_seconds=self.ttl_seconds,
            access_count=self.access_count + 1,
            last_accessed=datetime.now(timezone.utc),
        )


class AuthorizationCache(ABC):
    """Interface abstraite pour le cache d'autorisation."""

    @abstractmethod
    def get(self, key: CacheKey) -> Optional[PolicyDecision]:
        """Récupère une décision d'autorisation depuis le cache."""
        pass

    @abstractmethod
    def set(self, key: CacheKey, decision: PolicyDecision, ttl_seconds: int = 300) -> None:
        """Stocke une décision d'autorisation dans le cache."""
        pass

    @abstractmethod
    def invalidate(self, key: CacheKey) -> bool:
        """Invalide une entrée spécifique du cache."""
        pass

    @abstractmethod
    def invalidate_subject(self, subject_id: str) -> int:
        """Invalide toutes les entrées pour un sujet."""
        pass

    @abstractmethod
    def invalidate_resource(self, resource_id: str) -> int:
        """Invalide toutes les entrées pour une ressource."""
        pass

    @abstractmethod
    def clear(self) -> int:
        """Vide tout le cache."""
        pass

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur le cache."""
        pass


class InMemoryAuthorizationCache(AuthorizationCache):
    """Implémentation en mémoire du cache d'autorisation."""

    def __init__(self, max_size: int = 10000, eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.LRU) -> None:
        self._cache: Dict[str, CacheEntry] = {}
        self._subject_index: Dict[str, Set[str]] = {}
        self._resource_index: Dict[str, Set[str]] = {}
        self._max_size = max_size
        self._eviction_policy = eviction_policy
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: CacheKey) -> Optional[PolicyDecision]:
        """Récupère une décision d'autorisation depuis le cache."""
        cache_key = key.to_string()

        with self._lock:
            entry = self._cache.get(cache_key)

            if entry is None:
                self._misses += 1
                return None

            if not entry.is_valid():
                # Entrée expirée, la supprimer
                self._remove_entry(cache_key)
                self._misses += 1
                return None

            # Enregistrer l'accès et mettre à jour
            updated_entry = entry.record_access()
            self._cache[cache_key] = updated_entry
            self._hits += 1

            return entry.decision

    def set(self, key: CacheKey, decision: PolicyDecision, ttl_seconds: int = 300) -> None:
        """Stocke une décision d'autorisation dans le cache."""
        cache_key = key.to_string()

        with self._lock:
            # Vérifier si on doit faire de l'éviction
            if len(self._cache) >= self._max_size and cache_key not in self._cache:
                self._evict_entries()

            entry = CacheEntry(decision=decision, ttl_seconds=ttl_seconds)

            self._cache[cache_key] = entry

            # Mettre à jour les index
            if key.subject_id not in self._subject_index:
                self._subject_index[key.subject_id] = set()
            self._subject_index[key.subject_id].add(cache_key)

            if key.resource_id not in self._resource_index:
                self._resource_index[key.resource_id] = set()
            self._resource_index[key.resource_id].add(cache_key)

    def invalidate(self, key: CacheKey) -> bool:
        """Invalide une entrée spécifique du cache."""
        cache_key = key.to_string()

        with self._lock:
            return self._remove_entry(cache_key)

    def invalidate_subject(self, subject_id: str) -> int:
        """Invalide toutes les entrées pour un sujet."""
        with self._lock:
            cache_keys = self._subject_index.get(subject_id, set()).copy()
            count = 0

            for cache_key in cache_keys:
                if self._remove_entry(cache_key):
                    count += 1

            return count

    def invalidate_resource(self, resource_id: str) -> int:
        """Invalide toutes les entrées pour une ressource."""
        with self._lock:
            cache_keys = self._resource_index.get(resource_id, set()).copy()
            count = 0

            for cache_key in cache_keys:
                if self._remove_entry(cache_key):
                    count += 1

            return count

    def clear(self) -> int:
        """Vide tout le cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._subject_index.clear()
            self._resource_index.clear()
            return count

    def get_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur le cache."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "eviction_policy": self._eviction_policy.value,
            }

    def _remove_entry(self, cache_key: str) -> bool:
        """Supprime une entrée du cache et ses index."""
        if cache_key not in self._cache:
            return False

        del self._cache[cache_key]

        # Nettoyer les index
        # Pour l'instant, on ne sait pas quelle était la clé originale, donc on scanne
        for subject_id, keys in list(self._subject_index.items()):
            if cache_key in keys:
                keys.discard(cache_key)
                if not keys:
                    del self._subject_index[subject_id]

        for resource_id, keys in list(self._resource_index.items()):
            if cache_key in keys:
                keys.discard(cache_key)
                if not keys:
                    del self._resource_index[resource_id]

        return True

    def _evict_entries(self) -> None:
        """Applique la politique d'éviction."""
        if self._eviction_policy == CacheEvictionPolicy.LRU:
            self._evict_lru()
        elif self._eviction_policy == CacheEvictionPolicy.LFU:
            self._evict_lfu()
        elif self._eviction_policy == CacheEvictionPolicy.FIFO:
            self._evict_fifo()
        elif self._eviction_policy == CacheEvictionPolicy.TTL:
            self._evict_expired()

    def _evict_lru(self) -> None:
        """Évince les entrées les moins récemment utilisées."""
        # Trier par last_accessed et supprimer les 10% les plus anciens
        if not self._cache:
            return

        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].last_accessed)

        to_remove = max(1, len(sorted_entries) // 10)
        for cache_key, _ in sorted_entries[:to_remove]:
            self._remove_entry(cache_key)

    def _evict_lfu(self) -> None:
        """Évince les entrées les moins fréquemment utilisées."""
        if not self._cache:
            return

        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].access_count)

        to_remove = max(1, len(sorted_entries) // 10)
        for cache_key, _ in sorted_entries[:to_remove]:
            self._remove_entry(cache_key)

    def _evict_fifo(self) -> None:
        """Évince les entrées les plus anciennes (FIFO)."""
        if not self._cache:
            return

        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].cached_at)

        to_remove = max(1, len(sorted_entries) // 10)
        for cache_key, _ in sorted_entries[:to_remove]:
            self._remove_entry(cache_key)

    def _evict_expired(self) -> None:
        """Évince les entrées expirées."""
        expired_keys = [cache_key for cache_key, entry in self._cache.items() if entry.is_expired()]

        for cache_key in expired_keys:
            self._remove_entry(cache_key)


class CachedPolicyEngine:
    """Wrapper de policy engine avec cache."""

    def __init__(
        self,
        underlying_engine: Any,
        cache: Optional[AuthorizationCache] = None,
        ttl_seconds: int = 300,
        cache_on_deny: bool = False,
    ) -> None:
        self._engine = underlying_engine
        self._cache = cache or InMemoryAuthorizationCache()
        self._ttl_seconds = ttl_seconds
        self._cache_on_deny = cache_on_deny

    def evaluate(
        self, subject: Any, action: str, resource_id: str, context: Optional[Dict[str, Any]] = None
    ) -> PolicyDecision:
        """Évalue une autorisation avec cache."""

        # Créer la clé de cache
        subject_id = subject.id.value if hasattr(subject, "id") else str(subject)
        context = context or {}

        cache_key = CacheKey.from_components(
            subject_id=subject_id,
            action=action,
            resource_id=resource_id,
            context=context,
            policy_engine="rbac",  # À adapter selon le type d'engine
        )

        # Essayer de récupérer depuis le cache
        cached_decision = self._cache.get(cache_key)
        if cached_decision is not None:
            return cached_decision

        # Évaluer avec l'engine sous-jacent
        decision = self._engine.evaluate(subject, action, resource_id, context)

        # Mettre en cache uniquement si autorisé ou si configuré
        if decision.effect.value == "ALLOW" or self._cache_on_deny:
            self._cache.set(cache_key, decision, self._ttl_seconds)

        return decision

    def invalidate_subject(self, subject_id: str) -> int:
        """Invalide toutes les entrées pour un sujet."""
        return self._cache.invalidate_subject(subject_id)

    def invalidate_resource(self, resource_id: str) -> int:
        """Invalide toutes les entrées pour une ressource."""
        return self._cache.invalidate_resource(resource_id)

    def clear_cache(self) -> int:
        """Vide tout le cache."""
        return self._cache.clear()

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache."""
        return self._cache.get_statistics()


class CacheInvalidationStrategy(ABC):
    """Interface pour les stratégies d'invalidation de cache."""

    @abstractmethod
    def on_permission_granted(self, subject_id: str, permission: str) -> None:
        """Appelé quand une permission est accordée."""
        pass

    @abstractmethod
    def on_permission_revoked(self, subject_id: str, permission: str) -> None:
        """Appelé quand une permission est révoquée."""
        pass

    @abstractmethod
    def on_role_assigned(self, subject_id: str, role_id: str) -> None:
        """Appelé quand un rôle est assigné."""
        pass

    @abstractmethod
    def on_role_revoked(self, subject_id: str, role_id: str) -> None:
        """Appelé quand un rôle est révoqué."""
        pass


class SubjectCacheInvalidationStrategy(CacheInvalidationStrategy):
    """Stratégie d'invalidation qui invalide tout le cache d'un sujet."""

    def __init__(self, cache: AuthorizationCache) -> None:
        self._cache = cache

    def on_permission_granted(self, subject_id: str, permission: str) -> None:
        """Invalide le cache du sujet quand une permission est accordée."""
        self._cache.invalidate_subject(subject_id)

    def on_permission_revoked(self, subject_id: str, permission: str) -> None:
        """Invalide le cache du sujet quand une permission est révoquée."""
        self._cache.invalidate_subject(subject_id)

    def on_role_assigned(self, subject_id: str, role_id: str) -> None:
        """Invalide le cache du sujet quand un rôle est assigné."""
        self._cache.invalidate_subject(subject_id)

    def on_role_revoked(self, subject_id: str, role_id: str) -> None:
        """Invalide le cache du sujet quand un rôle est révoqué."""
        self._cache.invalidate_subject(subject_id)


# Factory pour créer des configurations de cache courantes
class CacheFactory:
    """Factory pour créer des configurations de cache."""

    @staticmethod
    def create_memory_cache(
        max_size: int = 10000, eviction_policy: CacheEvictionPolicy = CacheEvictionPolicy.LRU
    ) -> InMemoryAuthorizationCache:
        """Crée un cache en mémoire."""
        return InMemoryAuthorizationCache(max_size=max_size, eviction_policy=eviction_policy)

    @staticmethod
    def create_high_performance_cache() -> InMemoryAuthorizationCache:
        """Crée un cache haute performance."""
        return InMemoryAuthorizationCache(max_size=50000, eviction_policy=CacheEvictionPolicy.LRU)

    @staticmethod
    def create_conservative_cache() -> InMemoryAuthorizationCache:
        """Crée un cache conservateur (TTL court)."""
        return InMemoryAuthorizationCache(max_size=5000, eviction_policy=CacheEvictionPolicy.TTL)
