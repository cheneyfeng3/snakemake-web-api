from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

class BaseDBInterface(ABC):
    """数据库操作抽象接口"""
    
    @abstractmethod
    async def connect(self) -> None:
        """异步建立数据库连接"""
        pass
    
    @abstractmethod
    async def insert_record(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """异步插入单条记录"""
        pass
    
    @abstractmethod
    async def batch_insert(self, data_list: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """异步批量插入记录"""
        pass
    
    @abstractmethod
    async def query_records(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """异步查询记录"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭连接（如果需要）"""
        pass