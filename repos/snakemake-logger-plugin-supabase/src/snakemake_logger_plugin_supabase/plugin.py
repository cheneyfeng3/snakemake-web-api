from typing import List, Optional
from logging import LogRecord
import json
from snakemake_interface_logger_plugins.base import LogHandlerBase
from snakemake_interface_logger_plugins.common import LogEvent
from .db.db_factory import DBFactory
from .db.db_interface import BaseDBInterface
from .settings import LogHandlerSettings
import asyncio

class LogHandler(LogHandlerBase):
    def __post_init__(self) -> None:
        super().__post_init__()
        # 通过工厂类获取数据库客户端
        self.db_client: BaseDBInterface = DBFactory.get_db_client()
        self.table_name = self.settings.table_name
        self.batch_buffer: List[dict] = []  # 批量缓冲区
        self.batch_size = self.settings.batch_size

    def emit(self, record: LogRecord) -> None:
        """将日志记录发送到数据库"""
        try:
            job_id = getattr(record, 'jobid', getattr(record, 'job_id', None))
            total = getattr(record, 'total', 0)
            
            log_data = {
                "event": getattr(record, "event", str(LogEvent.ERROR)),
                "data": self._extract_record_data(record),
                "job_id":job_id,
                "total":total,
            }
            # 异步插入记录
            self.batch_buffer.append(log_data)            
            # 达到批量大小则插入
            if len(self.batch_buffer) >= self.batch_size:
                self._batch_insert()
        except Exception as e:
            print(f"Failed to send log to database: {str(e)}")
            
    def close(self) -> None:
        """工作流结束时调用，确保剩余日志插入"""
        if self.batch_buffer:
            self._batch_insert()
        super().close()
        
    def _batch_insert(self) -> None:
        """批量插入日志到Supabase（无重试，避免重复）"""
        try:
            data = asyncio.run(self.db_client.batch_insert(self.batch_buffer)) 
            print(data)
            self.batch_buffer = []
        except Exception as e:
            print(f"批量插入失败: {str(e)}")
            
    def _extract_record_data(self, record: LogRecord) -> dict:
        """提取日志记录中的相关数据"""
        data = {
            "message": str(record.msg),
            "level": record.levelname,
            "timestamp": record.created,
            "module": record.module,
            "lineno": record.lineno
        }
        
        # 添加事件特定字段
        event_specific = {}
        for attr in dir(record):
            if not attr.startswith('_') and attr not in data:
                try:
                    value = getattr(record, attr)
                    json.dumps(value)  # 验证可序列化
                    event_specific[attr] = value
                except (TypeError, ValueError):
                    continue
                    
        data["event_data"] = event_specific
        return data

    @property
    def writes_to_stream(self) -> bool:
        return False

    @property
    def writes_to_file(self) -> bool:
        return False

    @property
    def has_filter(self) -> bool:
        return False

    @property
    def has_formatter(self) -> bool:
        return True

    @property
    def needs_rulegraph(self) -> bool:
        return False