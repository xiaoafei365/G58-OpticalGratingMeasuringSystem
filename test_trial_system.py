#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
试用期系统测试脚本
用于测试试用期管理功能
"""

import os
import sys
import time
from datetime import datetime, timedelta

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from optical_grating_web_system import TrialManager

def test_trial_manager():
    """测试试用期管理器"""
    print("=" * 50)
    print("试用期管理系统测试")
    print("=" * 50)
    
    # 删除现有的试用期文件（用于测试）
    trial_file = "trial_info.dat"
    if os.path.exists(trial_file):
        os.remove(trial_file)
        print("已删除现有试用期文件，开始全新测试")
    
    # 创建试用期管理器
    trial_manager = TrialManager()
    
    # 测试1: 检查初始状态
    print("\n1. 检查初始试用期状态:")
    status = trial_manager.get_trial_status()
    print(f"   是否试用版: {status['is_trial']}")
    print(f"   是否过期: {status['is_expired']}")
    print(f"   已使用天数: {status['days_used']}")
    print(f"   剩余天数: {status['days_remaining']}")
    print(f"   状态消息: {status['message']}")
    print(f"   系统是否锁定: {trial_manager.is_system_locked()}")
    
    # 测试2: 测试延期验证码
    print("\n2. 测试延期验证码:")
    extend_code = "EXTEND2025A1"
    result = trial_manager.verify_code(extend_code)
    print(f"   验证码: {extend_code}")
    print(f"   验证结果: {result}")
    
    # 再次检查状态
    status = trial_manager.get_trial_status()
    print(f"   延期后剩余天数: {status['days_remaining']}")
    
    # 测试3: 重复使用相同验证码
    print("\n3. 测试重复使用相同验证码:")
    result = trial_manager.verify_code(extend_code)
    print(f"   重复验证结果: {result}")
    
    # 测试4: 测试无效验证码
    print("\n4. 测试无效验证码:")
    invalid_code = "INVALID123"
    result = trial_manager.verify_code(invalid_code)
    print(f"   无效验证码: {invalid_code}")
    print(f"   验证结果: {result}")
    
    # 测试5: 测试解锁验证码
    print("\n5. 测试解锁验证码:")
    unlock_code = "UNLOCK2025FOREVER"
    result = trial_manager.verify_code(unlock_code)
    print(f"   解锁验证码: {unlock_code}")
    print(f"   验证结果: {result}")
    
    # 最终状态检查
    status = trial_manager.get_trial_status()
    print(f"   解锁后状态: {status}")
    print(f"   系统是否锁定: {trial_manager.is_system_locked()}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

def simulate_expired_trial():
    """模拟试用期过期的情况"""
    print("\n" + "=" * 50)
    print("模拟试用期过期测试")
    print("=" * 50)
    
    # 删除现有的试用期文件
    trial_file = "trial_info.dat"
    if os.path.exists(trial_file):
        os.remove(trial_file)
    
    # 创建试用期管理器并手动设置过期时间
    trial_manager = TrialManager()
    
    # 手动设置开始时间为35天前（超过30天试用期）
    trial_manager.start_time = datetime.now() - timedelta(days=35)
    trial_manager._save_trial_info()
    
    print("已设置试用期开始时间为35天前")
    
    # 检查状态
    status = trial_manager.get_trial_status()
    print(f"试用期状态: {status}")
    print(f"系统是否锁定: {trial_manager.is_system_locked()}")
    
    # 测试延期功能
    print("\n测试延期功能:")
    extend_code = "EXTEND2025B2"
    result = trial_manager.verify_code(extend_code)
    print(f"延期验证结果: {result}")
    
    # 检查延期后状态
    status = trial_manager.get_trial_status()
    print(f"延期后状态: {status}")
    print(f"系统是否锁定: {trial_manager.is_system_locked()}")

def show_verification_codes():
    """显示所有可用的验证码"""
    print("\n" + "=" * 50)
    print("可用验证码列表")
    print("=" * 50)
    
    trial_manager = TrialManager()
    
    print("延期验证码（每个可延长30天，只能使用一次）:")
    for i, code in enumerate(trial_manager.extend_codes, 1):
        print(f"  {i:2d}. {code}")
    
    print(f"\n解锁验证码（永久解锁系统）:")
    print(f"      {trial_manager.unlock_code}")
    
    print("\n注意事项:")
    print("- 延期验证码使用后会被标记为已使用，不能重复使用")
    print("- 解锁验证码使用后系统将永久解锁")
    print("- 验证码不区分大小写")

if __name__ == "__main__":
    print("光学光栅测量系统 - 试用期功能测试")
    print("请选择测试项目:")
    print("1. 完整功能测试")
    print("2. 模拟过期测试")
    print("3. 显示验证码")
    print("4. 全部测试")
    
    choice = input("\n请输入选择 (1-4): ").strip()
    
    if choice == "1":
        test_trial_manager()
    elif choice == "2":
        simulate_expired_trial()
    elif choice == "3":
        show_verification_codes()
    elif choice == "4":
        show_verification_codes()
        test_trial_manager()
        simulate_expired_trial()
    else:
        print("无效选择")
        
    input("\n按回车键退出...")
