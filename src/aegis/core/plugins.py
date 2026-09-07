"""
Plugin System avec Hooks d'Extension pour Aegis.

Permet l'extension du système via des plugins personnalisés avec hooks
avant/après exécution des use cases, authentification, autorisation, etc.
"""

import importlib
import inspect
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4


class HookType(str, Enum):
    """Types de hooks disponibles."""

    PRE_USE_CASE = "pre_use_case"
    POST_USE_CASE = "post_use_case"
    PRE_AUTHENTICATION = "pre_authentication"
    POST_AUTHENTICATION = "post_authentication"
    PRE_AUTHORIZATION = "pre_authorization"
    POST_AUTHORIZATION = "post_authorization"
    PRE_DATA_ACCESS = "pre_data_access"
    POST_DATA_ACCESS = "post_data_access"
    ERROR_HANDLER = "error_handler"


class PluginStatus(str, Enum):
    """Statuts des plugins."""

    LOADED = "loaded"
    ERROR = "error"
    DISABLED = "disabled"
    UNLOADED = "unloaded"


@dataclass(frozen=True, slots=True)
class HookContext:
    """Contexte transmis aux hooks."""

    hook_type: HookType
    hook_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_metadata(self, **kwargs) -> "HookContext":
        """Crée un nouveau contexte avec des métadonnées additionnelles."""
        return HookContext(
            hook_type=self.hook_type,
            hook_id=self.hook_id,
            timestamp=self.timestamp,
            metadata={**self.metadata, **kwargs},
        )


@dataclass(frozen=True, slots=True)
class HookResult:
    """Résultat d'exécution d'un hook."""

    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    should_abort: bool = False  # Si True, arrête l'exécution de la chaîne
    abort_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Plugin:
    """Plugin avec ses métadonnées et hooks."""

    plugin_id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    enabled: bool = True
    status: PluginStatus = PluginStatus.UNLOADED
    hooks: Dict[HookType, List[Callable]] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    loaded_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_hook(self, hook_type: HookType) -> bool:
        """Vérifie si le plugin a un hook du type spécifié."""
        return hook_type in self.hooks and len(self.hooks[hook_type]) > 0

    def get_hooks(self, hook_type: HookType) -> List[Callable]:
        """Récupère les hooks d'un type spécifique."""
        return self.hooks.get(hook_type, [])


class Hook(ABC):
    """Interface abstraite pour les hooks."""

    @abstractmethod
    def execute(self, context: HookContext, **kwargs) -> HookResult:
        """Exécute le hook avec le contexte fourni."""
        pass

    @property
    @abstractmethod
    def hook_type(self) -> HookType:
        """Retourne le type de hook."""
        pass

    @property
    def priority(self) -> int:
        """Priorité du hook (plus élevé = exécuté en premier)."""
        return 0


class BaseHook(Hook):
    """Classe de base pour les hooks personnalisés."""

    def __init__(self, hook_type: HookType, priority: int = 0):
        self._hook_type = hook_type
        self._priority = priority

    @property
    def hook_type(self) -> HookType:
        return self._hook_type

    @property
    def priority(self) -> int:
        return self._priority

    def execute(self, context: HookContext, **kwargs) -> HookResult:
        """Méthode par défaut à surcharger."""
        return HookResult(success=True, data={})


class PluginManager:
    """Gestionnaire de plugins avec système de hooks."""

    def __init__(self, plugin_directories: Optional[List[str]] = None) -> None:
        self._plugin_directories = plugin_directories or ["./plugins"]
        self._plugins: Dict[str, Plugin] = {}
        self._hooks: Dict[
            HookType, List[Tuple[str, Callable, int]]
        ] = {}  # hook_type -> [(plugin_id, hook_func, priority)]
        self._lock = threading.Lock()

    def load_plugin_from_file(self, file_path: str) -> Optional[Plugin]:
        """Charge un plugin depuis un fichier Python."""
        try:
            # Charger le module
            spec = importlib.util.spec_from_file_location("plugin_module", file_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Chercher la fonction ou classe de plugin
            plugin_class = getattr(module, "create_plugin", None)
            if plugin_class is None:
                plugin_class = getattr(module, "Plugin", None)

            if plugin_class is None:
                return None

            # Instancier le plugin
            if callable(plugin_class):
                plugin_instance = plugin_class()
            else:
                plugin_instance = plugin_class

            # Enregistrer le plugin
            plugin = self._register_plugin_instance(plugin_instance, file_path)
            return plugin

        except Exception as e:
            print(f"Error loading plugin from {file_path}: {e}")
            return None

    def load_plugins_from_directory(self, directory: str) -> int:
        """Charge tous les plugins depuis un répertoire."""
        plugin_path = Path(directory)
        if not plugin_path.exists():
            return 0

        loaded_count = 0
        for file_path in plugin_path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            plugin = self.load_plugin_from_file(str(file_path))
            if plugin:
                loaded_count += 1

        return loaded_count

    def load_all_plugins(self) -> int:
        """Charge tous les plugins depuis les répertoires configurés."""
        total_loaded = 0
        for directory in self._plugin_directories:
            total_loaded += self.load_plugins_from_directory(directory)
        return total_loaded

    def _register_plugin_instance(self, plugin_instance: Any, source: str) -> Plugin:
        """Enregistre une instance de plugin."""
        plugin_id = getattr(plugin_instance, "plugin_id", f"plugin_{uuid4().hex[:8]}")
        name = getattr(plugin_instance, "name", "Unnamed Plugin")
        version = getattr(plugin_instance, "version", "1.0.0")
        description = getattr(plugin_instance, "description", "")
        author = getattr(plugin_instance, "author", "")
        dependencies = getattr(plugin_instance, "dependencies", [])
        enabled = getattr(plugin_instance, "enabled", True)

        # Collecter les hooks
        hooks: Dict[HookType, List[Callable]] = {}

        # Chercher les méthodes décorées ou les attributs hook
        for _attr_name, attr_value in inspect.getmembers(plugin_instance):
            if isinstance(attr_value, Hook):
                hook_type = attr_value.hook_type
                if hook_type not in hooks:
                    hooks[hook_type] = []
                hooks[hook_type].append(attr_value.execute)
            elif hasattr(attr_value, "__hook_type__"):
                hook_type = attr_value.__hook_type__
                if hook_type not in hooks:
                    hooks[hook_type] = []
                hooks[hook_type].append(attr_value)

        plugin = Plugin(
            plugin_id=plugin_id,
            name=name,
            version=version,
            description=description,
            author=author,
            enabled=enabled,
            status=PluginStatus.LOADED,
            hooks=hooks,
            dependencies=dependencies,
            loaded_at=datetime.now(timezone.utc),
            metadata={"source": source},
        )

        with self._lock:
            self._plugins[plugin_id] = plugin

            # Enregistrer les hooks dans l'index global
            for hook_type, hook_functions in hooks.items():
                if hook_type not in self._hooks:
                    self._hooks[hook_type] = []

                for hook_func in hook_functions:
                    priority = getattr(hook_func, "priority", 0)
                    self._hooks[hook_type].append((plugin_id, hook_func, priority))

                # Trier par priorité (décroissante)
                self._hooks[hook_type].sort(key=lambda x: x[2], reverse=True)

        return plugin

    def register_hook(
        self, hook_type: HookType, hook_func: Callable, plugin_id: str = "custom", priority: int = 0
    ) -> None:
        """Enregistre un hook manuellement."""
        with self._lock:
            if hook_type not in self._hooks:
                self._hooks[hook_type] = []

            self._hooks[hook_type].append((plugin_id, hook_func, priority))
            self._hooks[hook_type].sort(key=lambda x: x[2], reverse=True)

    def execute_hooks(self, hook_type: HookType, context: HookContext, **kwargs) -> List[HookResult]:
        """Exécute tous les hooks d'un type donné."""
        with self._lock:
            hook_entries = self._hooks.get(hook_type, [])

        results = []
        for plugin_id, hook_func, _priority in hook_entries:
            try:
                # Vérifier si le plugin est actif
                plugin = self._plugins.get(plugin_id)
                if plugin and not plugin.enabled:
                    continue

                # Exécuter le hook
                if isinstance(hook_func, Hook):
                    result = hook_func.execute(context, **kwargs)
                else:
                    result = hook_func(context, **kwargs)
                    if not isinstance(result, HookResult):
                        result = HookResult(success=True, data={"result": result})

                results.append(result)

                # Si le hook demande l'arrêt
                if result.should_abort:
                    break

            except Exception as e:
                error_result = HookResult(success=False, error=str(e), should_abort=False)
                results.append(error_result)

        return results

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Récupère un plugin par son ID."""
        return self._plugins.get(plugin_id)

    def list_plugins(self, include_disabled: bool = False) -> List[Plugin]:
        """Liste tous les plugins."""
        plugins = list(self._plugins.values())
        if not include_disabled:
            plugins = [p for p in plugins if p.enabled]
        return plugins

    def enable_plugin(self, plugin_id: str) -> bool:
        """Active un plugin."""
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin:
                # Créer une nouvelle instance avec enabled=True
                self._plugins[plugin_id] = Plugin(
                    plugin_id=plugin.plugin_id,
                    name=plugin.name,
                    version=plugin.version,
                    description=plugin.description,
                    author=plugin.author,
                    enabled=True,
                    status=plugin.status,
                    hooks=plugin.hooks,
                    dependencies=plugin.dependencies,
                    loaded_at=plugin.loaded_at,
                    metadata=plugin.metadata,
                )
                return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """Désactive un plugin."""
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin:
                self._plugins[plugin_id] = Plugin(
                    plugin_id=plugin.plugin_id,
                    name=plugin.name,
                    version=plugin.version,
                    description=plugin.description,
                    author=plugin.author,
                    enabled=False,
                    status=plugin.status,
                    hooks=plugin.hooks,
                    dependencies=plugin.dependencies,
                    loaded_at=plugin.loaded_at,
                    metadata=plugin.metadata,
                )
                return True
        return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """Décharge un plugin."""
        with self._lock:
            if plugin_id in self._plugins:
                # Supprimer les hooks du plugin
                for hook_type in list(self._hooks.keys()):
                    self._hooks[hook_type] = [entry for entry in self._hooks[hook_type] if entry[0] != plugin_id]
                    if not self._hooks[hook_type]:
                        del self._hooks[hook_type]

                del self._plugins[plugin_id]
                return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur les plugins."""
        with self._lock:
            total_plugins = len(self._plugins)
            enabled_plugins = sum(1 for p in self._plugins.values() if p.enabled)
            total_hooks = sum(len(hooks) for hooks in self._hooks.values())

            hooks_by_type = {hook_type.value: len(hooks) for hook_type, hooks in self._hooks.items()}

            return {
                "total_plugins": total_plugins,
                "enabled_plugins": enabled_plugins,
                "disabled_plugins": total_plugins - enabled_plugins,
                "total_hooks": total_hooks,
                "hooks_by_type": hooks_by_type,
                "plugin_directories": self._plugin_directories,
            }


def hook(hook_type: HookType, priority: int = 0):
    """Décorateur pour marquer une méthode comme hook."""

    def decorator(func):
        func.__hook_type__ = hook_type
        func.priority = priority
        return func

    return decorator


# Factory pour créer des plugins courants
class PluginFactory:
    """Factory pour créer des plugins courants."""

    @staticmethod
    def create_logging_plugin() -> Plugin:
        """Crée un plugin de logging."""

        class LoggingPlugin:
            plugin_id = "logging_plugin"
            name = "Logging Plugin"
            version = "1.0.0"
            description = "Logs all use case executions"
            author = "Aegis"
            enabled = True

            @hook(HookType.PRE_USE_CASE, priority=100)
            def log_pre_use_case(self, context: HookContext, **kwargs):
                print(f"[PRE_USE_CASE] {context.metadata}")
                return HookResult(success=True)

            @hook(HookType.POST_USE_CASE, priority=100)
            def log_post_use_case(self, context: HookContext, **kwargs):
                print(f"[POST_USE_CASE] {context.metadata}")
                return HookResult(success=True)

        return LoggingPlugin()

    @staticmethod
    def create_audit_plugin() -> Plugin:
        """Crée un plugin d'audit."""

        class AuditPlugin:
            plugin_id = "audit_plugin"
            name = "Audit Plugin"
            version = "1.0.0"
            description = "Audits all authorization decisions"
            author = "Aegis"
            enabled = True

            @hook(HookType.POST_AUTHORIZATION, priority=50)
            def audit_authorization(self, context: HookContext, **kwargs):
                decision = kwargs.get("decision")
                if decision:
                    print(f"[AUDIT] Authorization: {decision.effect.value} for {context.metadata.get('subject_id')}")
                return HookResult(success=True)

        return AuditPlugin()

    @staticmethod
    def create_rate_limit_plugin(max_requests: int = 100, window_seconds: int = 60) -> Plugin:
        """Crée un plugin de rate limiting."""

        class RateLimitPlugin:
            plugin_id = "rate_limit_plugin"
            name = "Rate Limit Plugin"
            version = "1.0.0"
            description = "Rate limits API requests"
            author = "Aegis"
            enabled = True

            def __init__(self):
                self._request_counts: Dict[str, List[datetime]] = {}
                self._max_requests = max_requests
                self._window_seconds = window_seconds

            @hook(HookType.PRE_USE_CASE, priority=200)
            def check_rate_limit(self, context: HookContext, **kwargs):
                subject_id = context.metadata.get("subject_id", "anonymous")
                now = datetime.now(timezone.utc)

                # Nettoyer les anciennes requêtes
                if subject_id in self._request_counts:
                    self._request_counts[subject_id] = [
                        req_time
                        for req_time in self._request_counts[subject_id]
                        if (now - req_time).total_seconds() < self._window_seconds
                    ]
                else:
                    self._request_counts[subject_id] = []

                # Vérifier la limite
                if len(self._request_counts[subject_id]) >= self._max_requests:
                    return HookResult(success=False, should_abort=True, abort_reason="Rate limit exceeded")

                # Enregistrer la requête
                self._request_counts[subject_id].append(now)
                return HookResult(success=True)

        return RateLimitPlugin()
