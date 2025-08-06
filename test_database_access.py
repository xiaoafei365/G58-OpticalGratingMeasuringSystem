#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库访问功能
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from optical_grating_web_system import DatabaseManager

def test_database_access():
    """测试数据库访问功能"""
    print("=" * 50)
    print("测试数据库访问功能")
    print("=" * 50)
    
    # 创建数据库管理器
    db_manager = DatabaseManager()
    
    print(f"数据库路径: {db_manager.db_path}")
    print(f"数据库可用: {db_manager.available}")
    
    if not db_manager.available:
        print("❌ 数据库不可用，可能的原因:")
        print("1. 数据库文件不存在")
        print("2. 缺少pyodbc模块")
        print("3. 缺少Microsoft Access驱动")
        return
    
    print("✅ 数据库连接成功!")
    
    # 获取可用表列表
    print("\n获取数据库表列表...")
    tables = db_manager.get_available_tables()
    
    if tables:
        print(f"找到 {len(tables)} 个图表数据表:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table}")
    else:
        print("❌ 没有找到以_25结尾的表")
        return
    
    # 测试获取图表数据
    print("\n测试获取图表数据...")
    test_cases = [
        ('G45', 1, 'x1', 'avg', 'L'),
        ('G45', 1, 'x1', 'rag', 'L'),
        ('G45', 1, 'x2', 'avg', 'L'),
        ('G45', 1, 't', 'avg', 'L'),
        ('G45', 2, 'm13m9', 'avg', 'L'),
        ('G45', 2, 'p3lt', 'avg', 'L'),
    ]

    for version, channel, param, chart_type, side in test_cases:
        print(f"\n测试 {version}_Channel_{channel}_{param}_{chart_type}:")
        data = db_manager.get_chart_data(version, channel, param, chart_type, side)

        if data:
            print(f"  ✅ 获取到 {len(data)} 个数据点")
            print(f"  📊 数据范围: {min(data):.2f} ~ {max(data):.2f}")
            print(f"  📈 前5个数据点: {[round(x, 2) for x in data[:5]]}")
        else:
            print(f"  ❌ 获取数据失败")

if __name__ == "__main__":
    test_database_access()
