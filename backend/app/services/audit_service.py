# -----------------------------------------------------------------------------
# backend/app/services/audit_service.py
#
# Scaffold placeholder — superseded by audit_log_service.py.
# The audit logging concern was originally planned here but was implemented
# under the more descriptive name AuditLogService in audit_log_service.py,
# which provides AuditLogService.log(user_id, action, entity_type, entity_id,
# old_value, new_value). All callers (fraud_service.py, wallet_service.py,
# setting_service.py) import from audit_log_service, not this file.
# This file is kept to avoid breaking any future import that uses the shorter
# name; it remains empty.
# -----------------------------------------------------------------------------
