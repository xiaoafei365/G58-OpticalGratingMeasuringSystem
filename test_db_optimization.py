#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库连接优化效果
"""

import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import json

def test_single_request(url, request_id):
    """测试单个请求"""
    try:
        start_time = time.time()
        response = requests.get(url, timeout=10)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            return {
                'request_id': request_id,
                'success': True,
                'response_time': end_time - start_time,
                'status': data.get('status'),
                'source': data.get('source', 'unknown'),
                'data_points': len(data.get('data', [])) if data.get('data') else 0
            }
        else:
            return {
                'request_id': request_id,
                'success': False,
                'response_time': end_time - start_time,
                'error': f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            'request_id': request_id,
            'success': False,
            'response_time': 0,
            'error': str(e)
        }

def test_concurrent_requests():
    """测试并发请求"""
    print("=" * 60)
    print("🧪 测试数据库连接优化效果")
    print("=" * 60)
    
    base_url = "http://localhost:5000"
    
    # 测试用例 - 模拟前端同时请求多个图表数据
    test_urls = [
        f"{base_url}/api/get_chart_data/G48/1/x1/avg/L",
        f"{base_url}/api/get_chart_data/G48/1/x1/rag/L", 
        f"{base_url}/api/get_chart_data/G48/1/x2/avg/L",
        f"{base_url}/api/get_chart_data/G48/1/x2/rag/L",
        f"{base_url}/api/get_chart_data/G48/1/t/avg/L",
        f"{base_url}/api/get_chart_data/G48/1/t/rag/L",
        f"{base_url}/api/get_chart_data/G48/4/p5t/avg/L",
        f"{base_url}/api/get_chart_data/G48/4/p5t/rag/L",
    ]
    
    print(f"📊 准备发送 {len(test_urls)} 个并发请求...")
    print("🔄 请求列表:")
    for i, url in enumerate(test_urls, 1):
        print(f"   {i}. {url.split('/')[-5:]}")
    
    # 并发测试
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for i, url in enumerate(test_urls):
            future = executor.submit(test_single_request, url, i+1)
            futures.append(future)
        
        results = []
        for future in futures:
            result = future.result()
            results.append(result)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 分析结果
    print(f"\n📈 测试结果分析:")
    print(f"   ⏱️  总耗时: {total_time:.2f} 秒")
    
    successful_requests = [r for r in results if r['success']]
    failed_requests = [r for r in results if not r['success']]
    
    print(f"   ✅ 成功请求: {len(successful_requests)}/{len(results)}")
    print(f"   ❌ 失败请求: {len(failed_requests)}/{len(results)}")
    
    if successful_requests:
        avg_response_time = sum(r['response_time'] for r in successful_requests) / len(successful_requests)
        print(f"   📊 平均响应时间: {avg_response_time:.3f} 秒")
        
        # 统计数据源
        database_requests = [r for r in successful_requests if r.get('source') == 'database']
        cache_requests = [r for r in successful_requests if r.get('source') == 'cache']
        simulation_requests = [r for r in successful_requests if r.get('source') == 'simulation']
        
        print(f"   🗄️  数据库数据: {len(database_requests)} 个请求")
        print(f"   💾 缓存数据: {len(cache_requests)} 个请求") 
        print(f"   🎲 模拟数据: {len(simulation_requests)} 个请求")
    
    if failed_requests:
        print(f"\n❌ 失败请求详情:")
        for req in failed_requests:
            print(f"   请求 {req['request_id']}: {req['error']}")
    
    # 详细结果
    print(f"\n📋 详细结果:")
    for result in results:
        status_icon = "✅" if result['success'] else "❌"
        if result['success']:
            source = result.get('source', 'unknown')
            data_points = result.get('data_points', 0)
            print(f"   {status_icon} 请求{result['request_id']}: {result['response_time']:.3f}s | {source} | {data_points}点")
        else:
            print(f"   {status_icon} 请求{result['request_id']}: {result['error']}")

def test_cache_effectiveness():
    """测试缓存效果"""
    print(f"\n🔄 测试缓存效果...")
    
    url = "http://localhost:5000/api/get_chart_data/G48/1/x2/avg/L"
    
    # 第一次请求
    print("   第一次请求 (应该查询数据库)...")
    result1 = test_single_request(url, 1)
    
    # 立即第二次请求
    print("   第二次请求 (应该使用缓存)...")
    result2 = test_single_request(url, 2)
    
    if result1['success'] and result2['success']:
        print(f"   第一次: {result1['response_time']:.3f}s | {result1.get('source', 'unknown')}")
        print(f"   第二次: {result2['response_time']:.3f}s | {result2.get('source', 'unknown')}")
        
        if result2['response_time'] < result1['response_time']:
            print("   ✅ 缓存生效，第二次请求更快")
        else:
            print("   ⚠️  缓存可能未生效")
    else:
        print("   ❌ 请求失败，无法测试缓存")

if __name__ == "__main__":
    try:
        test_concurrent_requests()
        test_cache_effectiveness()
        print(f"\n✅ 测试完成")
    except KeyboardInterrupt:
        print(f"\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
