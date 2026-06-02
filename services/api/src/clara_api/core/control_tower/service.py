from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.control_tower.defaults import (
    CONTROL_TOWER_KEY,
    get_default_control_tower_config,
)
from clara_api.db.models import SystemSetting
from clara_api.schemas import SystemControlTowerConfig


class ControlTowerConfigService:
    def __init__(
        self,
        *,
        setting_key: str = CONTROL_TOWER_KEY,
        default_factory: Callable[[], SystemControlTowerConfig] = get_default_control_tower_config,
    ) -> None:
        self._setting_key = setting_key
        self._default_factory = default_factory

    @staticmethod
    def _enforce_mandatory_flow_flags(config: SystemControlTowerConfig) -> SystemControlTowerConfig:
        # Product requirement: keep neural reranker and GraphRAG always enabled.
        config.rag_flow.rag_reranker_enabled = True
        config.rag_flow.rag_graphrag_enabled = True
        return config

    def load(self, db: Session) -> SystemControlTowerConfig:
        row = db.execute(
            select(SystemSetting).where(SystemSetting.key == self._setting_key)
        ).scalar_one_or_none()
        if not row or not isinstance(row.value_json, dict):
            return self._enforce_mandatory_flow_flags(self._default_factory())
        try:
            parsed = SystemControlTowerConfig.model_validate(row.value_json)
            return self._enforce_mandatory_flow_flags(parsed)
        except Exception:
            return self._enforce_mandatory_flow_flags(self._default_factory())

    def save(self, db: Session, payload: SystemControlTowerConfig) -> SystemControlTowerConfig:
        payload = self._enforce_mandatory_flow_flags(payload)
        row = db.execute(
            select(SystemSetting).where(SystemSetting.key == self._setting_key)
        ).scalar_one_or_none()
        if not row:
            row = SystemSetting(key=self._setting_key)
        row.value_json = payload.model_dump(mode="json")
        row.value_text = ""
        db.add(row)
        db.commit()
        db.refresh(row)
        parsed = SystemControlTowerConfig.model_validate(row.value_json or {})
        return self._enforce_mandatory_flow_flags(parsed)


_CONTROL_TOWER_CONFIG_SERVICE = ControlTowerConfigService()


def get_control_tower_config_service() -> ControlTowerConfigService:
    return _CONTROL_TOWER_CONFIG_SERVICE
