#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试表名和字段名映射
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from optical_grating_web_system import DatabaseManager

def test_table_mapping():
    """测试表名和字段名映射"""
    print("=" * 60)
    print("🧪 测试表名和字段名映射")
    print("=" * 60)
    
    # 创建数据库管理器
    db_manager = DatabaseManager()
    
    if not db_manager.available:
        print("❌ 数据库不可用")
        return
    
    print("✅ 数据库连接成功!")
    
    # 获取所有表
    tables = db_manager.get_available_tables()
    print(f"\n📊 找到 {len(tables)} 个数据表:")
    for table in tables:
        print(f"   📋 {table}")
    
    # 测试表名构建
    print(f"\n🔍 测试表名构建:")
    
    test_cases = [
        # G45版本
        ('G45', 1, 'L', 'G45_Channel_1_25'),
        ('G45', 2, 'L', 'G45_Channel_2_25'),
        
        # G48版本
        ('G48', 1, 'L', 'G48_L_P1_25'),
        ('G48', 2, 'L', 'G48_L_P5L_25'),
        ('G48', 3, 'L', 'G48_L_P5U_25'),
        ('G48', 4, 'L', 'G48_L_P3_25'),
        ('G48', 5, 'L', 'G48_L_P4_25'),
    ]
    
    for version, channel, side, expected_table in test_cases:
        # 模拟表名构建逻辑
        if version == 'G48':
            channel_names = {1: 'P1', 2: 'P5L', 3: 'P5U', 4: 'P3', 5: 'P4'}
            channel_name = channel_names.get(channel, f'P{channel}')
            actual_table = f"{version}_{side}_{channel_name}_25"
        else:
            actual_table = f"{version}_Channel_{channel}_25"
        
        exists = actual_table in tables
        status = "✅" if exists else "❌"
        print(f"   {status} {version} 通道{channel}: {actual_table} {'(存在)' if exists else '(不存在)'}")
    
    # 测试字段名映射
    print(f"\n🔍 测试字段名映射:")
    
    field_test_cases = [
        # G48版本字段映射
        ('G48', 'x2', 'avg', 'P1 X-CAV'),
        ('G48', 't', 'avg', 'P1 totalAV'),
        ('G48', 'p5t', 'avg', 'P3 P5TAV'),
        ('G48', 'p5t', 'rag', 'P3 P5TAR'),
        
        # G45版本字段映射
        ('G45', 'x1', 'avg', 'x1_avg'),
        ('G45', 'p5t', 'avg', 'p5t_avg'),
    ]
    
    for version, param, chart_type, expected_field in field_test_cases:
        actual_field = db_manager._get_field_name(version, param, chart_type)
        match = actual_field == expected_field
        status = "✅" if match else "❌"
        print(f"   {status} {version} {param}-{chart_type}: {actual_field} {'✓' if match else f'(期望: {expected_field})'}")
    
    # 测试实际数据获取
    print(f"\n🔍 测试实际数据获取:")
    
    data_test_cases = [
        ('G48', 1, 'x2', 'avg', 'L'),
        ('G48', 1, 't', 'avg', 'L'),
        ('G48', 4, 'p5t', 'avg', 'L'),
    ]
    
    for version, channel, param, chart_type, side in data_test_cases:
        print(f"\n   测试: {version} 通道{channel} {param}-{chart_type}")
        data = db_manager.get_chart_data(version, channel, param, chart_type, side)
        
        if data:
            print(f"      ✅ 获取到 {len(data)} 个数据点")
            print(f"      📊 数据范围: {min(data):.2f} ~ {max(data):.2f}")
            print(f"      📈 前3个数据点: {[round(x, 2) for x in data[:3]]}")
        else:
            print(f"      ❌ 获取数据失败")
    
    print(f"\n✅ 测试完成")

if __name__ == "__main__":
    test_table_mapping()
