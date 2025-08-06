#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试G48字段映射是否正确
"""

import requests
import json

def test_g48_field_mapping():
    """测试G48字段映射"""
    base_url = "http://localhost:5000"
    
    print("=" * 80)
    print("🧪 测试G48字段映射")
    print("=" * 80)
    
    # 测试用例 - 基于实际数据库字段结构
    test_cases = [
        # P1通道 (Channel 1) - G48_L_P1_25表
        ("G48", 1, "x1", "avg", "L", "P1 X-BAV", "X1平均值"),
        ("G48", 1, "x1", "rag", "L", "P1 X-BMN", "X1极差值"),
        ("G48", 1, "x2", "avg", "L", "P1 X-CAV", "X2平均值"),
        ("G48", 1, "x2", "rag", "L", "P1 X-CMN", "X2极差值"),
        ("G48", 1, "t", "avg", "L", "P1 totalAV", "T平均值"),
        ("G48", 1, "t", "rag", "L", "P1 totalMN", "T极差值"),
        
        # P5L通道 (Channel 2) - G48_L_P5L_25表
        ("G48", 2, "m13m9", "avg", "L", "M13-M9AV", "M13M9平均值"),
        ("G48", 2, "m13m9", "rag", "L", "M13-M9MN", "M13M9极差值"),
        ("G48", 2, "p3lt", "avg", "L", "P5L totalAV", "P3LT平均值"),
        ("G48", 2, "p3lt", "rag", "L", "P5L totalMN", "P3LT极差值"),
        
        # P5U通道 (Channel 3) - G48_L_P5U_25表
        ("G48", 3, "p3ut", "avg", "L", "P5U totalAV", "P3UT平均值"),
        ("G48", 3, "p3ut", "rag", "L", "P5U totalMN", "P3UT极差值"),
        
        # P3通道 (Channel 4) - G48_L_P3_25表
        ("G48", 4, "m6m8", "avg", "L", "M6-M8AV", "M6M8平均值"),
        ("G48", 4, "m6m8", "rag", "L", "M6-M8MN", "M6M8极差值"),
        ("G48", 4, "p5t", "avg", "L", "P3 totalAV", "P5T平均值"),
        ("G48", 4, "p5t", "rag", "L", "P3 totalMN", "P5T极差值"),
        
        # P4通道 (Channel 5) - G48_L_P4_25表
        ("G48", 5, "p4", "avg", "L", "P4AV", "P4平均值"),
        ("G48", 5, "p4", "rag", "L", "P4MN", "P4极差值"),
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for version, channel, param, chart_type, side, expected_field, description in test_cases:
        print(f"\n🔍 测试: {description}")
        url = f"{base_url}/api/get_chart_data/{version}/{channel}/{param}/{chart_type}/{side}"
        print(f"   URL: {url}")
        print(f"   期望字段: {expected_field}")
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    data_points = data.get('data', [])
                    source = data.get('source', 'unknown')
                    
                    if source == 'database' and len(data_points) > 0:
                        print(f"   ✅ 成功获取 {len(data_points)} 个数据点")
                        print(f"   📊 数据源: {source}")
                        
                        # 显示前3个数据点
                        values = [point['y'] for point in data_points[:3]]
                        print(f"   📈 前3个数据点: {[round(v, 2) for v in values]}")
                        success_count += 1
                        
                    elif source == 'simulation':
                        print(f"   ⚠️  使用模拟数据 (可能字段映射不正确)")
                        
                    else:
                        print(f"   ❌ 数据获取失败: {data.get('message', '未知错误')}")
                        
                else:
                    print(f"   ❌ API返回错误: {data.get('message', '未知错误')}")
                    
            else:
                print(f"   ❌ HTTP错误: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ 连接失败: 服务器未运行")
            break
        except requests.exceptions.Timeout:
            print(f"   ❌ 请求超时")
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
    
    print(f"\n" + "=" * 80)
    print(f"📊 测试结果统计")
    print(f"=" * 80)
    print(f"✅ 成功: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
    print(f"❌ 失败: {total_count-success_count}/{total_count}")
    
    if success_count == total_count:
        print(f"🎉 所有字段映射测试通过！")
    elif success_count > total_count * 0.8:
        print(f"👍 大部分字段映射正确，少数需要调整")
    else:
        print(f"⚠️  多个字段映射需要修正")

if __name__ == "__main__":
    test_g48_field_mapping()
