import os
from typing import Optional

from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

DRAIN_STATE_PATH = "data/drain3_state.bin"

_miner: Optional[TemplateMiner] = None


def _build_config() -> TemplateMinerConfig:
    config = TemplateMinerConfig()
    config.masking_instructions = [
        MaskingInstruction(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", "timestamp"
        ),
        MaskingInstruction(
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "ip"
        ),
    ]
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    config.drain_max_children = 100
    config.profiling_enabled = False
    config.snapshot_interval_minutes = 5
    return config


def get_miner() -> TemplateMiner:
    global _miner
    if _miner is None:
        os.makedirs("data", exist_ok=True)
        persistence = FilePersistence(DRAIN_STATE_PATH)
        config = _build_config()
        _miner = TemplateMiner(
            persistence_handler=persistence, config=config
        )
    return _miner


def parse_log(raw_log: str) -> dict:
    result = get_miner().add_log_message(raw_log)
    return {
        "cluster_id": result["cluster_id"],
        "template": result["template_mined"],
        "change_type": result["change_type"],
    }


def extract_params(raw_log: str, template: str) -> list:
    try:
        params = get_miner().extract_parameters(template, raw_log)
        if params:
            return [{"value": p.value, "mask": p.mask_name} for p in params]
    except Exception:
        pass
    return []
