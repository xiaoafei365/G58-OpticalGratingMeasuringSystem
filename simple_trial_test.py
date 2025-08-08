#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的试用期功能测试
"""

import os
import pickle
from datetime import datetime, timedelta

# 模拟TrialManager类的核心功能
class SimpleTrialManager:
    def __init__(self, trial_file="trial_info.dat"):
        self.trial_file = trial_file
        self.trial_days = 30
        self.start_time = None
        self.used_codes = set()
        self.is_unlimited = False
        
        # 预生成的验证码
        self.extend_codes = [
            "EXTEND2025A1", "EXTEND2025B2", "EXTEND2025C3", "EXTEND2025D4", "EXTEND2025E5",
            "EXTEND2025F6", "EXTEND2025G7", "EXTEND2025H8", "EXTEND2025I9", "EXTEND2025J0"
        ]
        self.unlock_code = "UNLOCK2025FOREVER"
        
        self._load_trial_info()
    
    def _load_trial_info(self):
        try:
            if os.path.exists(self.trial_file):
                with open(self.trial_file, 'rb') as f:
                    data = pickle.load(f)
                    self.start_time = data.get('start_time')
                    self.used_codes = set(data.get('used_codes', []))
                    self.is_unlimited = data.get('is_unlimited', False)
                    print(f"试用期信息加载成功，开始时间: {self.start_time}")
            else:
                self.start_time = datetime.now()
                self._save_trial_info()
                print(f"首次运行，试用期开始: {self.start_time}")
        except Exception as e:
            print(f"加载试用期信息失败: {e}")
            self.start_time = datetime.now()
            self._save_trial_info()
    
    def _save_trial_info(self):
        try:
            data = {
                'start_time': self.start_time,
                'used_codes': list(self.used_codes),
                'is_unlimited': self.is_unlimited
            }
            with open(self.trial_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"保存试用期信息失败: {e}")
    
    def get_trial_status(self):
        if self.is_unlimited:
            return {
                'is_trial': False,
                'is_expired': False,
                'days_used': 0,
                'days_remaining': -1,
                'message': '系统已解锁，无使用限制'
            }
        
        if not self.start_time:
            return {
                'is_trial': True,
                'is_expired': True,
                'days_used': 0,
                'days_remaining': 0,
                'message': '试用期信息异常'
            }
        
        now = datetime.now()
        days_used = (now - self.start_time).days
        days_remaining = max(0, self.trial_days - days_used)
        is_expired = days_remaining <= 0
        
        return {
            'is_trial': True,
            'is_expired': is_expired,
            'days_used': days_used,
            'days_remaining': days_remaining,
            'message': f'试用期剩余 {days_remaining} 天' if not is_expired else '试用期已到期'
        }
    
    def is_system_locked(self):
        if self.is_unlimited:
            return False
        status = self.get_trial_status()
        return status['is_expired']
    
    def verify_code(self, code):
        code = code.strip().upper()
        
        if code == self.unlock_code:
            self.is_unlimited = True
            self._save_trial_info()
            print("系统已永久解锁")
            return {
                'success': True,
                'type': 'unlock',
                'message': '系统已永久解锁，无使用限制'
            }
        
        if code in self.extend_codes:
            if code in self.used_codes:
                return {
                    'success': False,
                    'type': 'extend',
                    'message': '此验证码已使用过，请使用新的验证码'
                }
            
            self.used_codes.add(code)
            if self.start_time:
                self.start_time = self.start_time - timedelta(days=30)
            else:
                self.start_time = datetime.now() - timedelta(days=30)
            
            self._save_trial_info()
            print(f"试用期已延长30天，验证码: {code}")
            
            status = self.get_trial_status()
            return {
                'success': True,
                'type': 'extend',
                'message': f'试用期已延长30天，剩余 {status["days_remaining"]} 天'
            }
        
        return {
            'success': False,
            'type': 'invalid',
            'message': '验证码无效，请检查后重新输入'
        }

def main():
    print("=" * 60)
    print("光学光栅测量系统 - 试用期功能测试")
    print("=" * 60)
    
    # 删除现有试用期文件进行全新测试
    if os.path.exists("trial_info.dat"):
        os.remove("trial_info.dat")
        print("已删除现有试用期文件，开始全新测试\n")
    
    # 创建试用期管理器
    trial_manager = SimpleTrialManager()
    
    # 测试1: 检查初始状态
    print("1. 初始试用期状态:")
    status = trial_manager.get_trial_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    print(f"   系统锁定状态: {trial_manager.is_system_locked()}")
    
    # 测试2: 显示可用验证码
    print("\n2. 可用验证码:")
    print("   延期验证码:")
    for i, code in enumerate(trial_manager.extend_codes[:3], 1):  # 只显示前3个
        print(f"     {i}. {code}")
    print(f"   解锁验证码: {trial_manager.unlock_code}")
    
    # 测试3: 测试延期验证码
    print("\n3. 测试延期验证码:")
    extend_code = trial_manager.extend_codes[0]
    result = trial_manager.verify_code(extend_code)
    print(f"   使用验证码: {extend_code}")
    print(f"   验证结果: {result}")
    
    # 检查延期后状态
    status = trial_manager.get_trial_status()
    print(f"   延期后剩余天数: {status['days_remaining']}")
    
    # 测试4: 重复使用验证码
    print("\n4. 测试重复使用验证码:")
    result = trial_manager.verify_code(extend_code)
    print(f"   重复验证结果: {result}")
    
    # 测试5: 测试无效验证码
    print("\n5. 测试无效验证码:")
    result = trial_manager.verify_code("INVALID123")
    print(f"   验证结果: {result}")
    
    # 测试6: 模拟过期情况
    print("\n6. 模拟试用期过期:")
    trial_manager.start_time = datetime.now() - timedelta(days=35)
    trial_manager._save_trial_info()
    status = trial_manager.get_trial_status()
    print(f"   过期状态: {status}")
    print(f"   系统锁定: {trial_manager.is_system_locked()}")
    
    # 测试7: 过期后延期
    print("\n7. 过期后使用延期码:")
    extend_code2 = trial_manager.extend_codes[1]
    result = trial_manager.verify_code(extend_code2)
    print(f"   使用验证码: {extend_code2}")
    print(f"   验证结果: {result}")
    
    status = trial_manager.get_trial_status()
    print(f"   延期后状态: {status}")
    
    # 测试8: 永久解锁
    print("\n8. 测试永久解锁:")
    result = trial_manager.verify_code(trial_manager.unlock_code)
    print(f"   解锁结果: {result}")
    
    status = trial_manager.get_trial_status()
    print(f"   解锁后状态: {status}")
    print(f"   系统锁定: {trial_manager.is_system_locked()}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
