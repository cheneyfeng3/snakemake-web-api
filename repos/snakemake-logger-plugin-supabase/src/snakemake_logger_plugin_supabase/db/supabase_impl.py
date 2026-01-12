# src/snakemake_logger_plugin_supabase/db/supabase_impl.py
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
from .db_interface import BaseDBInterface
import os
import asyncio
from contextlib import asynccontextmanager


class SupabaseDB(BaseDBInterface):
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

        self.table_name = os.environ.get("SUPABASE_TABLE_NAME", "snakemake_logs")
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

    async def close(self) -> None:
        """Supabase客户端无需显式关闭连接"""
        pass
