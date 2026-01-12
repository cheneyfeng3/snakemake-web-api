from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
import os
import asyncio
import requests

from snakemake_mcp_server.schemas import JobStatus

# 1. 配置 HTTP 客户端（包含 timeout/verify）
http_client = requests.Session()
# 设置超时时间（替代原 timeout 参数）
http_client.timeout = 30  # 单位：秒
# 设置 SSL 验证（替代原 verify 参数）
http_client.verify = True  # 或指定证书路径："/path/to/cert.pem"

class SupabaseDB():
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.table_name: Optional[str] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """从环境变量初始化Supabase连接"""
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
            )

        self.table_name = os.environ.get("SUPABASE_TABLE_NAME", "sciagi_mcp_snakemake_logger")
        async with self._lock:
            if self.supabase is None:
                self.supabase = create_client(supabase_url, supabase_key)

    async def insert_record(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.supabase:
            await self.connect()  # 自动重连

        try:
            async with self._lock:
                response = self.supabase.table(self.table_name).insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            # 重试一次
            await asyncio.sleep(0.5)
            async with self._lock:
                response = self.supabase.table(self.table_name).insert(data).execute()
            return response.data[0] if response.data else None

    async def batch_insert(
        self, data_list: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.supabase:
            await self.connect()  # 自动重连
        if not self.supabase or not self.table_name:
            raise RuntimeError("Supabase client not initialized")
        
        try:
            response = self.supabase.table(self.table_name).insert(data_list).execute()
            return response.data
        except Exception as e:
            # 重试一次
            await asyncio.sleep(0.5)
            response = self.supabase.table(self.table_name).insert(data_list).execute()
            return response.data

    async def query_records(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.supabase or not self.table_name:
            raise RuntimeError("Supabase client not initialized")

        query = self.supabase.from_(self.table_name)
        for key, value in filters.items():
            query = query.select("*").eq(key, value)

        response = query.execute()
        return response.data
    
    async def check_connection(self) -> bool:
        result = self.supabase.from_("workflows").select("*").limit(1).execute()
        print(result)
        return result

    async def update_record_by_id(
        self, id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not self.supabase:
            await self.connect()  # 自动重连

        try:
            async with self._lock:
                response = (
                    self.supabase.from_(self.table_name)
                    .update(data)
                    .eq("id", id)
                    .execute()
                )
            return response.data[0] if response.data else None
        except Exception as e:
            # 重试一次
            await asyncio.sleep(0.5)
            async with self._lock:
                response = (
                    self.supabase.from_(self.table_name)
                    .update(data)
                    .eq("id", id)
                    .execute()
                )
            return response.data[0] if response.data else None
    async def update_task_status_by_task_id(
        self, task_id: str, status: JobStatus
    ) -> Optional[Dict[str, Any]]:
        if not self.supabase:
            await self.connect()  # 自动重连
        data = {
            "updated_at" : datetime.now(timezone.utc).isoformat(),
            "status" : status.value
        }
        try:
            async with self._lock:
                response = (
                    self.supabase.from_(self.table_name)
                    .update(data)
                    .eq("task_id", task_id)
                    .execute()
                )
            return response.data[0] if response.data else None
        except Exception as e:
            # 重试一次
            await asyncio.sleep(0.5)
            async with self._lock:
                response = (
                    self.supabase.from_(self.table_name)
                    .update(data)
                    .eq("task_id", task_id)
                    .execute()
                )
            return response.data[0] if response.data else None
        
    async def close(self) -> None:
        """Supabase客户端无需显式关闭连接"""
        pass
