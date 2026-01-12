from dataclasses import dataclass
from snakemake_interface_logger_plugins.settings import LogHandlerSettingsBase

@dataclass
class LogHandlerSettings(LogHandlerSettingsBase):
    table_name: str = "sciagi_mcp_snakemake_logger"  # 可外部传入的表名
    batch_size: int = 5  # 批量插入大小（默认5条）
    
    def __post_init__(self):
        # 为每个字段添加帮助字符串（如果需要）
        pass