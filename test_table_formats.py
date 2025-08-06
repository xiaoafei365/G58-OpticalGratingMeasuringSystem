#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试G45和G48的表名格式
"""

import requests
import json

def test_table_formats():
    """测试不同的表名格式"""
    base_url = "http://localhost:5000"
    
    print("=" * 80)
    print("🧪 测试G45和G48表名格式")
    print("=" * 80)
    
    # 测试G45不同格式
    print("\n🔍 测试G45表名格式:")
    g45_tests = [
        ("G45", 1, "x1", "avg", "L", "G45新格式或旧格式"),
        ("G45", 2, "x1", "avg", "L", "G45通道2"),
        ("G45", 3, "x1", "avg", "L", "G45通道3"),
    ]
    
    for version, channel, param, chart_type, side, description in g45_tests:
        print(f"\n   测试: {description}")
        url = f"{base_url}/api/get_chart_data/{version}/{channel}/{param}/{chart_type}/{side}"
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    source = data.get('source', 'unknown')
                    data_count = len(data.get('data', []))
                    print(f"      ✅ 成功: {source} | {data_count}个数据点")
                else:
                    print(f"      ❌ 失败: {data.get('message', '未知错误')}")
            else:
                print(f"      ❌ HTTP错误: {response.status_code}")
        except Exception as e:
            print(f"      ❌ 请求失败: {e}")
    
    # 测试G48格式
    print(f"\n🔍 测试G48表名格式:")
    g48_tests = [
        ("G48", 1, "x1", "avg", "L", "G48通道1"),
        ("G48", 2, "m13m9", "avg", "L", "G48通道2"),
        ("G48", 4, "p5t", "avg", "L", "G48通道4"),
    ]
    
    for version, channel, param, chart_type, side, description in g48_tests:
        print(f"\n   测试: {description}")
        url = f"{base_url}/api/get_chart_data/{version}/{channel}/{param}/{chart_type}/{side}"
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    source = data.get('source', 'unknown')
                    data_count = len(data.get('data', []))
                    print(f"      ✅ 成功: {source} | {data_count}个数据点")
                else:
                    print(f"      ❌ 失败: {data.get('message', '未知错误')}")
            else:
                print(f"      ❌ HTTP错误: {response.status_code}")
        except Exception as e:
            print(f"      ❌ 请求失败: {e}")
    
    print(f"\n✅ 测试完成")

if __name__ == "__main__":
    test_table_formats()
