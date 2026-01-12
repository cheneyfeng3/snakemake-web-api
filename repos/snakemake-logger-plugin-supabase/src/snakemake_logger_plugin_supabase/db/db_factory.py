# src/snakemake_logger_plugin_supabase/db/db_factory.py
import os
from typing import Type
from .db_interface import BaseDBInterface
from .supabase_impl import SupabaseDB

class DBFactory:
    @staticmethod
    def get_db_client() -> BaseDBInterface:
        """根据环境变量选择数据库实现类"""
        db_type = os.environ.get("DB_TYPE", "supabase").lower()
        
        if db_type == "supabase":
            return SupabaseDB()
        # 可在此处添加其他数据库类型的判断
        # elif db_type == "postgres":
        #     return PostgresDB()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")