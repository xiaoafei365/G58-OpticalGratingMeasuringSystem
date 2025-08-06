#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试表名构建逻辑
"""

def test_table_name_construction():
    """测试表名构建逻辑"""
    print("=" * 50)
    print("🧪 测试表名构建逻辑")
    print("=" * 50)
    
    test_cases = [
        # (version, channel, side, expected_table_name)
        ('G45', 1, 'L', 'G45_Channel_1_25'),
        ('G45', 2, 'L', 'G45_Channel_2_25'),
        ('G48', 1, 'L', 'G48_L_P1_25'),
        ('G48', 2, 'L', 'G48_L_P5L_25'),
        ('G48', 3, 'L', 'G48_L_P5U_25'),
        ('G48', 4, 'L', 'G48_L_P3_25'),
        ('G48', 5, 'L', 'G48_L_P4_25'),
    ]
    
    for version, channel, side, expected in test_cases:
        # 模拟表名构建逻辑
        if version == 'G48':
            channel_names = {1: 'P1', 2: 'P5L', 3: 'P5U', 4: 'P3', 5: 'P4'}
            channel_name = channel_names.get(channel, f'P{channel}')
            actual = f"{version}_{side}_{channel_name}_25"
        else:
            actual = f"{version}_Channel_{channel}_25"
        
        match = actual == expected
        status = "✅" if match else "❌"
        print(f"{status} {version} 通道{channel}: {actual} {'✓' if match else f'(期望: {expected})'}")

def test_field_name_mapping():
    """测试字段名映射"""
    print(f"\n🔍 测试字段名映射:")
    
    # G48版本的字段映射
    field_mapping = {
        # P1通道 (Channel 1)
        ('x1', 'avg'): 'P1 X1AV',
        ('x1', 'rag'): 'P1 X1AR', 
        ('x2', 'avg'): 'P1 X-CAV',
        ('x2', 'rag'): 'P1 X-CAR',
        ('t', 'avg'): 'P1 totalAV',
        ('t', 'rag'): 'P1 totalAR',
        
        # P3通道 (Channel 4)
        ('p5t', 'avg'): 'P3 P5TAV',
        ('p5t', 'rag'): 'P3 P5TAR',
    }
    
    test_cases = [
        ('G48', 'x2', 'avg', 'P1 X-CAV'),
        ('G48', 't', 'avg', 'P1 totalAV'),
        ('G48', 'p5t', 'avg', 'P3 P5TAV'),
        ('G48', 'p5t', 'rag', 'P3 P5TAR'),
        ('G45', 'x1', 'avg', 'x1_avg'),
        ('G45', 'p5t', 'avg', 'p5t_avg'),
    ]
    
    for version, param, chart_type, expected in test_cases:
        if version == 'G48':
            actual = field_mapping.get((param.lower(), chart_type), f"{param}_{chart_type}")
        else:
            actual = f"{param.lower()}_{chart_type}"
        
        match = actual == expected
        status = "✅" if match else "❌"
        print(f"   {status} {version} {param}-{chart_type}: {actual} {'✓' if match else f'(期望: {expected})'}")

if __name__ == "__main__":
    test_table_name_construction()
    test_field_name_mapping()
    print(f"\n✅ 测试完成")
