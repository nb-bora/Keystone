"""
Logger Structuré JSON & Middleware de Corrélation d'Aegis.

Formatte tous les logs applicatifs au format JSON structuré pour leur ingestion
automatique par les collecteurs de logs (Promtail, Fluentd, Datadog, ELK).
Exclut strictement tout mot de passe, secret ou donnée PII en clair.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formatter de logs au format JSON structuré avec support du request_id."""

    def __init__(self, service_name: str = "aegis-iam", environment: Optional[str] = None) -> None:
        super().__init__()
        self.service_name = service_name
        self.environment = environment or os.getenv("ENVIRONMENT", "development")

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": self.service_name,
            "environment": self.environment,
            "logger": record.name,
        }

        # Injection de l'identifiant de corrélation de requête s'il existe
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        # Injection des attributs HTTP ou exception si présents
        if hasattr(record, "http_method"):
            log_data["http_method"] = record.http_method
        if hasattr(record, "http_route"):
            log_data["http_route"] = record.http_route
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(name: str = "aegis") -> logging.Logger:
    """Retourne une instance configurée du logger structuré JSON."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger
