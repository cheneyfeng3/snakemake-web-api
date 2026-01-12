import os
import asyncio
import pytest
from snakemake_logger_plugin_supabase.db.supabase_impl import SupabaseDB
import sys
from pathlib import Path
# 添加项目src目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

# 测试前设置环境变量
@pytest.fixture(autouse=True)
def set_env_vars():
    os.environ["SUPABASE_URL"] = "http://10.3.200.31:8000"
    # os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE"
    os.environ["SUPABASE_KEY"] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q'
    os.environ["SUPABASE_TABLE_NAME"] = "sciagi_mcp_snakemake_logger"

@pytest.mark.asyncio
async def test_supabase_db_operations():
    # 初始化客户端
    db = SupabaseDB()
    await db.connect()
    
    try:
        # 测试插入单条记录
        test_data = {
            "event": "test_event",
            "data": {"message": "test message", "level": "INFO"}
        }
        # inserted = await db.insert_record(test_data)
        print(f'###########################################')
        result = await db.check_connection()
        assert len(result) >= 1
        # assert inserted is not None
        # assert inserted["event"] == test_data["event"]
        
        # # 测试查询记录
        # filters = {"event": "test_event"}
        # results = await db.query_records(filters)
        # assert len(results) >= 1
        # assert results[0]["data"]["message"] == "test message"
        
        # # 测试批量插入
        # batch_data = [
        #     {"event": "batch_event", "data": {"index": 1}},
        #     {"event": "batch_event", "data": {"index": 2}}
        # ]
        # batch_inserted = await db.batch_insert(batch_data)
        # assert len(batch_inserted) == 2
        
        # # 验证批量插入结果
        # batch_results = await db.query_records({"event": "batch_event"})
        # assert len(batch_results) >= 2
        
    finally:
        # 清理测试数据 - 修复清理部分的代码
        # try:
        #     if db.supabase and db.table_name:
        #         # 使用正确的API调用方式清理数据
        #         delete_response1 = db.supabase.from_(db.table_name).delete().eq("event", "test_event").execute()
        #         delete_response2 = db.supabase.from_(db.table_name).delete().eq("event", "batch_event").execute()
        # except Exception as e:
        #     print(f"清理测试数据时发生错误: {str(e)}")
        # finally:
            await db.close()