#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查G45数据库表的结构，验证是否与G48使用相同的表名格式
"""

import os
import pyodbc

def check_g45_tables():
    """检查G45表结构"""
    db_path = os.path.abspath("guangshan.mdb")
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    try:
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🔍 G45数据库表结构验证")
        print("=" * 80)
        
        # 获取所有表名
        tables = cursor.tables(tableType='TABLE')
        all_tables = [table.table_name for table in tables]
        
        # 查找G45相关的表
        g45_tables = [t for t in all_tables if 'G45' in t]
        
        print(f"📊 找到 {len(g45_tables)} 个G45相关的表:")
        for table in g45_tables:
            print(f"   📋 {table}")
        
        # 检查是否存在新格式的G45表 (G45_L_P1_25 等)
        expected_g45_tables = [
            'G45_L_P1_25',
            'G45_L_P5L_25', 
            'G45_L_P5U_25',
            'G45_L_P3_25',
            'G45_L_P4_25'
        ]
        
        print(f"\n🔍 检查新格式的G45表:")
        new_format_exists = False
        for table_name in expected_g45_tables:
            exists = table_name in all_tables
            status = "✅" if exists else "❌"
            print(f"   {status} {table_name} {'(存在)' if exists else '(不存在)'}")
            if exists:
                new_format_exists = True
        
        # 检查旧格式的G45表 (G45_Channel_1_25 等)
        old_format_tables = [
            'G45_Channel_1_25',
            'G45_Channel_2_25',
            'G45_Channel_3_25',
            'G45_Channel_4_25',
            'G45_Channel_5_25'
        ]
        
        print(f"\n🔍 检查旧格式的G45表:")
        old_format_exists = False
        for table_name in old_format_tables:
            exists = table_name in all_tables
            status = "✅" if exists else "❌"
            print(f"   {status} {table_name} {'(存在)' if exists else '(不存在)'}")
            if exists:
                old_format_exists = True
        
        # 分析结果
        print(f"\n" + "=" * 80)
        print("📊 分析结果:")
        print("=" * 80)
        
        if new_format_exists and old_format_exists:
            print("⚠️  同时存在新旧两种格式的G45表")
            print("   建议: 确认使用哪种格式，并相应调整代码")
        elif new_format_exists:
            print("✅ G45使用新格式表名 (G45_L_P1_25)")
            print("   代码已正确配置为统一格式")
        elif old_format_exists:
            print("⚠️  G45使用旧格式表名 (G45_Channel_1_25)")
            print("   需要在代码中为G45版本保留特殊处理")
        else:
            print("❌ 未找到G45表，可能表名格式不同")
        
        # 如果存在新格式的G45表，检查其字段结构
        if new_format_exists:
            print(f"\n🔍 检查G45表字段结构:")
            for table_name in expected_g45_tables:
                if table_name in all_tables:
                    print(f"\n📊 表: {table_name}")
                    print("-" * 40)
                    
                    try:
                        cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
                        if cursor.description:
                            fields = [desc[0] for desc in cursor.description]
                            print(f"   字段: {fields}")
                    except Exception as e:
                        print(f"   ❌ 查询失败: {e}")
        
        conn.close()
        print(f"\n✅ 检查完成")
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

if __name__ == "__main__":
    check_g45_tables()
