"""Unit tests for data models: Tenant, User, UserTenant, EmailVerification, AuditLog."""

from app.models.audit_log import AuditLog
from app.models.email_verification import EmailVerification, VerificationType
from app.models.source_file import SourceFile
from app.models.tenant import PlanType, Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant


class TestTenantModel:
    def test_tenant_has_required_columns(self):
        table = Tenant.__table__
        col_names = {c.name for c in table.columns}
        assert {"id", "name", "nip", "plan", "is_active", "created_at", "updated_at"} <= col_names

    def test_plan_type_enum_values(self):
        assert PlanType.FREEMIUM.value == "freemium"
        assert PlanType.BASIC.value == "basic"
        assert PlanType.PREMIUM.value == "premium"

    def test_nip_column_is_unique(self):
        nip_col = Tenant.__table__.c.nip
        assert nip_col.unique is True

    def test_tablename(self):
        assert Tenant.__tablename__ == "tenants"


class TestUserModel:
    def test_user_has_required_columns(self):
        table = User.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id",
            "email",
            "password_hash",
            "name",
            "is_admin",
            "is_active",
            "email_verified_at",
            "notification_preferences",
            "created_at",
            "updated_at",
        }
        assert expected <= col_names

    def test_email_is_unique(self):
        email_col = User.__table__.c.email
        assert email_col.unique is True

    def test_email_is_indexed(self):
        email_col = User.__table__.c.email
        assert email_col.index is True

    def test_tablename(self):
        assert User.__tablename__ == "users"


class TestUserTenantModel:
    def test_user_tenant_has_required_columns(self):
        table = UserTenant.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id",
            "user_id",
            "tenant_id",
            "role",
            "invited_by",
            "created_at",
            "updated_at",
        }
        assert expected <= col_names

    def test_tenant_role_enum_values(self):
        assert TenantRole.USER.value == "user"
        assert TenantRole.OWNER.value == "owner"

    def test_user_id_is_indexed(self):
        user_id_col = UserTenant.__table__.c.user_id
        assert user_id_col.index is True

    def test_tenant_id_is_indexed(self):
        tenant_id_col = UserTenant.__table__.c.tenant_id
        assert tenant_id_col.index is True

    def test_unique_user_tenant_constraint(self):
        constraints = {c.name for c in UserTenant.__table__.constraints}
        assert "uq_user_tenants_user_tenant" in constraints

    def test_tablename(self):
        assert UserTenant.__tablename__ == "user_tenants"

    def test_user_id_fk_references_users(self):
        fks = list(UserTenant.__table__.c.user_id.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "users"

    def test_tenant_id_fk_references_tenants(self):
        fks = list(UserTenant.__table__.c.tenant_id.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tenants"

    def test_invited_by_fk_self_referential(self):
        fks = list(UserTenant.__table__.c.invited_by.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "users"


class TestEmailVerificationModel:
    def test_has_required_columns(self):
        table = EmailVerification.__table__
        col_names = {c.name for c in table.columns}
        expected = {"id", "user_id", "token", "type", "expires_at", "used_at", "created_at", "updated_at"}
        assert expected <= col_names

    def test_token_is_unique(self):
        token_col = EmailVerification.__table__.c.token
        assert token_col.unique is True

    def test_verification_type_enum_values(self):
        assert VerificationType.REGISTRATION.value == "registration"
        assert VerificationType.INVITATION.value == "invitation"
        assert VerificationType.PASSWORD_RESET.value == "password_reset"

    def test_tablename(self):
        assert EmailVerification.__tablename__ == "email_verifications"


class TestAuditLogModel:
    def test_has_required_columns(self):
        table = AuditLog.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "id",
            "tenant_id",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "changes",
            "ip_address",
            "created_at",
        }
        assert expected <= col_names

    def test_tenant_id_is_indexed(self):
        assert AuditLog.__table__.c.tenant_id.index is True

    def test_user_id_is_indexed(self):
        assert AuditLog.__table__.c.user_id.index is True

    def test_tablename(self):
        assert AuditLog.__tablename__ == "audit_logs"


class TestSourceFileModel:
    def test_has_preprocessing_columns(self):
        table = SourceFile.__table__
        col_names = {c.name for c in table.columns}
        expected = {
            "detected_language",
            "detected_framework",
            "requires_manual_classification",
            "loc_count",
        }
        assert expected <= col_names

    def test_requires_manual_classification_defaults_false(self):
        col = SourceFile.__table__.c.requires_manual_classification
        assert col.default.arg is False

    def test_loc_count_defaults_zero(self):
        col = SourceFile.__table__.c.loc_count
        assert col.default.arg == 0

    def test_detected_language_is_indexed(self):
        col = SourceFile.__table__.c.detected_language
        assert col.index is True

    def test_tablename(self):
        assert SourceFile.__tablename__ == "source_files"
