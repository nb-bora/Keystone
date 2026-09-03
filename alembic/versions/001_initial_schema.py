"""
Script de migration Alembic pour Aegis IAM.

Contient les fonctions de migration pour les différents backends de stockage.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime, timezone


# revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crée le schéma initial de la base de données."""
    
    # Table des sujets (aggregates racines)
    op.create_table(
        'aegis_subjects',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('tenant_id', sa.String(64), nullable=True, index=True),
        sa.Column('subject_type', sa.String(32), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean, default=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        
        # Champs spécifiques à HumanIdentity
        sa.Column('email', sa.String(255), nullable=True, unique=True, index=True),
        sa.Column('first_name', sa.String(128), default=""),
        sa.Column('last_name', sa.String(128), default=""),
        sa.Column('is_email_verified', sa.Boolean, default=False),
        
        # Champs spécifiques à ServiceAccount
        sa.Column('client_id', sa.String(128), nullable=True, index=True),
        
        # Champs spécifiques à ApiKeyActor
        sa.Column('key_prefix', sa.String(32), nullable=True),
        sa.Column('key_name', sa.String(128), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        
        # Champs spécifiques à AIAgentActor
        sa.Column('agent_name', sa.String(128), nullable=True),
        sa.Column('owner_identity_id', sa.String(64), nullable=True, index=True),
        sa.Column('max_autonomy_level', sa.Integer, default=1),
        
        # JSON pour les permissions et scopes
        sa.Column('permissions', sa.JSON, nullable=True),
        sa.Column('allowed_scopes', sa.JSON, nullable=True),
        
        # Indexes optimisés
        sa.Index('ix_aegis_subjects_tenant_subject_type', 'tenant_id', 'subject_type'),
        sa.Index('ix_aegis_subjects_email_active', 'email', 'is_active'),
        sa.Index('ix_aegis_subjects_tenant_active', 'tenant_id', 'is_active'),
        sa.Index('ix_aegis_subjects_type_active', 'subject_type', 'is_active'),
        sa.Index('ix_aegis_subjects_created_at', 'created_at'),
        sa.Index('ix_aegis_subjects_updated_at', 'updated_at'),
    )
    
    # Table des rôles
    op.create_table(
        'aegis_roles',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False, unique=True),
        sa.Column('description', sa.Text, default=""),
        sa.Column('permissions', sa.JSON, nullable=False),
        sa.Column('parent_role_ids', sa.JSON, nullable=True),
        sa.Column('tenant_id', sa.String(64), nullable=True, index=True),
        sa.Column('is_system_role', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes optimisés
        sa.Index('ix_aegis_roles_tenant_system', 'tenant_id', 'is_system_role'),
        sa.Index('ix_aegis_roles_name_tenant', 'name', 'tenant_id'),
    )
    
    # Table des assignations de rôles
    op.create_table(
        'aegis_role_assignments',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('subject_id', sa.String(64), nullable=False, index=True),
        sa.Column('role_id', sa.String(64), nullable=False, index=True),
        sa.Column('tenant_id', sa.String(64), nullable=True, index=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigned_by', sa.String(64), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes composites optimisés
        sa.Index('ix_aegis_role_assignments_subject_role', 'subject_id', 'role_id'),
        sa.Index('ix_aegis_role_assignments_tenant_subject', 'tenant_id', 'subject_id'),
        sa.Index('ix_aegis_role_assignments_tenant_role', 'tenant_id', 'role_id'),
        sa.Index('ix_aegis_role_assignments_expires_at', 'expires_at'),
        sa.Index('ix_aegis_role_assignments_assigned_at', 'assigned_at'),
    )
    
    # Table des tenants
    op.create_table(
        'aegis_tenants',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('description', sa.Text, default=""),
        sa.Column('parent_tenant_id', sa.String(64), nullable=True, index=True),
        sa.Column('level', sa.String(32), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('settings', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes optimisés
        sa.Index('ix_aegis_tenants_parent_level', 'parent_tenant_id', 'level'),
        sa.Index('ix_aegis_tenants_level_active', 'level', 'is_active'),
        sa.Index('ix_aegis_tenants_name', 'name'),
    )
    
    # Table des événements d'outbox (Transactional Outbox)
    op.create_table(
        'aegis_outbox_events',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('event_type', sa.String(128), nullable=False, index=True),
        sa.Column('aggregate_id', sa.String(64), nullable=False, index=True),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('status', sa.String(32), nullable=False, default='pending', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes optimisés
        sa.Index('ix_aegis_outbox_status_created', 'status', 'created_at'),
        sa.Index('ix_aegis_outbox_type_aggregate', 'event_type', 'aggregate_id'),
        sa.Index('ix_aegis_outbox_retry_count', 'retry_count'),
        sa.Index('ix_aegis_outbox_updated_at', 'updated_at'),
    )
    
    # Table des sessions
    op.create_table(
        'aegis_sessions',
        sa.Column('session_id', sa.String(64), primary_key=True),
        sa.Column('subject_id', sa.String(64), nullable=False, index=True),
        sa.Column('user_agent', sa.Text, default=""),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('device_type', sa.String(32), default="unknown"),
        sa.Column('location', sa.String(256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, default='active', index=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes optimisés
        sa.Index('ix_aegis_sessions_subject_status', 'subject_id', 'status'),
        sa.Index('ix_aegis_sessions_expires_at', 'expires_at'),
        sa.Index('ix_aegis_sessions_last_activity', 'last_activity'),
        sa.Index('ix_aegis_sessions_ip_address', 'ip_address'),
    )
    
    # Table des consentements RGPD
    op.create_table(
        'aegis_consents',
        sa.Column('consent_id', sa.String(64), primary_key=True),
        sa.Column('subject_id', sa.String(64), nullable=False, index=True),
        sa.Column('consent_type', sa.String(64), nullable=False),
        sa.Column('granted', sa.Boolean, nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.String(32), default="1.0"),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes
        sa.Index('ix_aegis_consents_subject_type', 'subject_id', 'consent_type'),
    )
    
    # Table des enregistrements de rétention RGPD
    op.create_table(
        'aegis_data_retention',
        sa.Column('subject_id', sa.String(64), primary_key=True),
        sa.Column('status', sa.String(32), nullable=False, default='active'),
        sa.Column('anonymization_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_deletion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deletion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.Text, default=""),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes
        sa.Index('ix_aegis_data_retention_status', 'status'),
        sa.Index('ix_aegis_data_retention_anonymization', 'anonymization_date'),
    )
    
    # Table des tuples de relations ReBAC
    op.create_table(
        'aegis_relationships',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('subject_id', sa.String(64), nullable=False, index=True),
        sa.Column('relation', sa.String(64), nullable=False),
        sa.Column('resource_id', sa.String(64), nullable=False),
        sa.Column('resource_type', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        # Indexes
        sa.Index('ix_aegis_relationships_subject_relation', 'subject_id', 'relation'),
        sa.Index('ix_aegis_relationships_resource_type', 'resource_id', 'resource_type'),
    )


def downgrade() -> None:
    """Supprime le schéma initial de la base de données."""
    
    # Supprimer les tables dans l'ordre inverse des dépendances
    op.drop_table('aegis_relationships')
    op.drop_table('aegis_data_retention')
    op.drop_table('aegis_consents')
    op.drop_table('aegis_sessions')
    op.drop_table('aegis_outbox_events')
    op.drop_table('aegis_tenants')
    op.drop_table('aegis_role_assignments')
    op.drop_table('aegis_roles')
    op.drop_table('aegis_subjects')
