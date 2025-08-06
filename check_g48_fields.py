#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查G48数据库表的字段结构
"""

import os
import pyodbc
import logging

def check_g48_table_fields():
    """检查G48各个表的字段结构"""
    db_path = os.path.abspath("guangshan.mdb")
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    try:
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("🔍 G48数据库表字段结构分析")
        print("=" * 80)
        
        # G48相关的表
        g48_tables = [
            'G48_L_P1_25',
            'G48_L_P5L_25', 
            'G48_L_P5U_25',
            'G48_L_P3_25',
            'G48_L_P4_25'
        ]
        
        for table_name in g48_tables:
            print(f"\n📊 表: {table_name}")
            print("-" * 60)
            
            try:
                # 检查表是否存在
                tables = cursor.tables(tableType='TABLE')
                table_names = [table.table_name for table in tables]
                
                if table_name not in table_names:
                    print(f"   ⚠️  表不存在")
                    continue
                
                # 获取表结构
                cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
                
                if cursor.description:
                    fields = [desc[0] for desc in cursor.description]
                    print(f"   🔧 字段数量: {len(fields)}")
                    print(f"   📋 字段列表:")
                    
                    for i, field in enumerate(fields, 1):
                        print(f"      {i:2d}. '{field}'")
                    
                    # 获取一些示例数据
                    cursor.execute(f"SELECT TOP 3 * FROM [{table_name}]")
                    rows = cursor.fetchall()
                    
                    if rows:
                        print(f"   📈 示例数据 (前3行):")
                        for row_idx, row in enumerate(rows, 1):
                            print(f"      行{row_idx}: ", end="")
                            for field_idx, value in enumerate(row):
                                if field_idx < 5:  # 只显示前5个字段的值
                                    if isinstance(value, (int, float)):
                                        print(f"{fields[field_idx]}={value:.2f} ", end="")
                                    else:
                                        print(f"{fields[field_idx]}={value} ", end="")
                            print()
                else:
                    print(f"   ❌ 无法获取表结构")
                    
            except Exception as e:
                print(f"   ❌ 查询失败: {e}")
        
        # 生成字段映射建议
        print(f"\n" + "=" * 80)
        print("💡 建议的字段映射 (基于实际字段结构)")
        print("=" * 80)
        
        mapping_suggestions = {
            'G48_L_P1_25': {
                'description': 'P1通道 (Channel 1)',
                'params': {
                    'x1': "('x1', 'avg'): 'p1 x-bav', ('x1', 'rag'): 'p1 x-bmn'",
                    'x2': "('x2', 'avg'): 'p1 x-cav', ('x2', 'rag'): 'p1 x-cmn'", 
                    't': "('t', 'avg'): 'p1 totalav', ('t', 'rag'): 'p1 totalmn'"
                }
            },
            'G48_L_P5L_25': {
                'description': 'P5L通道 (Channel 2)',
                'params': {
                    'm13m9': "('m13m9', 'avg'): 'm13-m9av', ('m13m9', 'rag'): 'm13-m9mn'",
                    'p3lt': "('p3lt', 'avg'): 'p5l totalav', ('p3lt', 'rag'): 'p5l totalmn'"
                }
            }
        }
        
        for table, info in mapping_suggestions.items():
            print(f"\n# {info['description']} - {table}")
            for param, mapping in info['params'].items():
                print(f"# {param.upper()}: {mapping}")
        
        conn.close()
        print(f"\n✅ 字段结构检查完成")
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

if __name__ == "__main__":
    check_g48_table_fields()
