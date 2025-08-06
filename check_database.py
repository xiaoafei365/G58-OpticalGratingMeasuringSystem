#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查guangshan.mdb数据库结构
"""

import os

def check_database():
    db_path = os.path.abspath("guangshan.mdb")
    print(f"数据库路径: {db_path}")

    if not os.path.exists(db_path):
        print("数据库文件不存在!")
        return

    # 检查文件大小
    file_size = os.path.getsize(db_path)
    print(f"数据库文件大小: {file_size} 字节")

    try:
        import pyodbc
        # 尝试连接Access数据库
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print("✅ 成功连接到数据库!")

        # 获取所有表名
        tables = cursor.tables(tableType='TABLE')
        table_names = [table.table_name for table in tables]

        print(f"\n数据库中共有 {len(table_names)} 个表:")
        print("-" * 50)

        # 显示所有表名，特别标注以_25结尾的表
        chart_tables = []
        for table_name in sorted(table_names):
            if table_name.endswith('_25'):
                print(f"📊 {table_name} (图表数据表)")
                chart_tables.append(table_name)
            else:
                print(f"📋 {table_name}")

        print(f"\n找到 {len(chart_tables)} 个图表数据表 (以_25结尾):")

        # 详细检查以_25结尾的表
        for table_name in chart_tables:
            print(f"\n🔍 检查表: {table_name}")
            try:
                # 获取表结构
                cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
                columns = [desc[0] for desc in cursor.description]
                print(f"   列名: {', '.join(columns)}")

                # 获取记录数
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                count = cursor.fetchone()[0]
                print(f"   记录数: {count}")

                # 显示前几条记录
                if count > 0:
                    cursor.execute(f"SELECT TOP 3 * FROM [{table_name}]")
                    rows = cursor.fetchall()
                    print("   示例数据:")
                    for i, row in enumerate(rows, 1):
                        print(f"     记录{i}: {dict(zip(columns, row))}")

            except Exception as e:
                print(f"   ❌ 检查表失败: {e}")

        conn.close()
        return chart_tables

    except ImportError:
        print("❌ 缺少pyodbc模块，无法连接数据库")
        print("请运行: pip install pyodbc")
        return None
    except Exception as e:
        print(f"❌ 连接数据库失败: {e}")
        print("可能的原因:")
        print("1. 没有安装Microsoft Access驱动")
        print("2. 数据库文件被锁定")
        print("3. 权限不足")
        return None

if __name__ == "__main__":
    check_database()
