#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证码管理工具
用于生成和管理试用期验证码
"""

import secrets
import string
import hashlib
from datetime import datetime
import json

class VerificationCodeManager:
    """验证码管理器"""
    
    def __init__(self):
        self.extend_codes = [
            "EXTEND2025A1", "EXTEND2025B2", "EXTEND2025C3", "EXTEND2025D4", "EXTEND2025E5",
            "EXTEND2025F6", "EXTEND2025G7", "EXTEND2025H8", "EXTEND2025I9", "EXTEND2025J0"
        ]
        self.unlock_code = "UNLOCK2025FOREVER"
    
    def generate_extend_codes(self, count=10, prefix="EXTEND2025"):
        """生成延期验证码"""
        codes = []
        suffixes = ['A1', 'B2', 'C3', 'D4', 'E5', 'F6', 'G7', 'H8', 'I9', 'J0']
        
        for i in range(min(count, len(suffixes))):
            code = f"{prefix}{suffixes[i]}"
            codes.append(code)
        
        return codes
    
    def generate_unlock_code(self, prefix="UNLOCK2025"):
        """生成解锁验证码"""
        return f"{prefix}FOREVER"
    
    def generate_random_codes(self, count=10, length=12):
        """生成随机验证码"""
        codes = []
        chars = string.ascii_uppercase + string.digits
        
        for _ in range(count):
            code = ''.join(secrets.choice(chars) for _ in range(length))
            codes.append(code)
        
        return codes
    
    def validate_code_format(self, code):
        """验证验证码格式"""
        if not code or len(code) < 8:
            return False, "验证码长度不足"
        
        if not code.isupper():
            return False, "验证码应为大写字母和数字"
        
        return True, "格式正确"
    
    def get_code_hash(self, code):
        """获取验证码哈希值"""
        return hashlib.sha256(code.encode()).hexdigest()
    
    def export_codes_to_file(self, filename="verification_codes.json"):
        """导出验证码到文件"""
        data = {
            "generated_time": datetime.now().isoformat(),
            "extend_codes": self.extend_codes,
            "unlock_code": self.unlock_code,
            "code_info": {
                "extend_codes_count": len(self.extend_codes),
                "extend_code_usage": "每个验证码可延长试用期30天，只能使用一次",
                "unlock_code_usage": "永久解锁系统，无使用限制"
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"验证码已导出到: {filename}")
    
    def print_codes(self):
        """打印所有验证码"""
        print("=" * 60)
        print("光学光栅测量系统 - 验证码列表")
        print("=" * 60)
        
        print("\n📅 延期验证码 (每个可延长30天，只能使用一次):")
        print("-" * 40)
        for i, code in enumerate(self.extend_codes, 1):
            print(f"  {i:2d}. {code}")
        
        print(f"\n🔓 解锁验证码 (永久解锁系统):")
        print("-" * 40)
        print(f"      {self.unlock_code}")
        
        print("\n📋 使用说明:")
        print("-" * 40)
        print("1. 延期验证码：输入后可延长试用期30天")
        print("2. 每个延期验证码只能使用一次")
        print("3. 解锁验证码：输入后永久解锁系统")
        print("4. 验证码不区分大小写")
        print("5. 系统会自动保存验证状态")
        
        print("\n⚠️  注意事项:")
        print("-" * 40)
        print("• 请妥善保管验证码，避免泄露")
        print("• 已使用的验证码会被系统记录")
        print("• 重装系统会重置试用期状态")
        print("• 建议备份 trial_info.dat 文件")
        
        print("=" * 60)

def main():
    """主函数"""
    print("验证码管理工具")
    print("Verification Code Manager")
    print("-" * 30)
    
    manager = VerificationCodeManager()
    
    while True:
        print("\n请选择操作:")
        print("1. 显示当前验证码")
        print("2. 生成新的延期验证码")
        print("3. 生成新的解锁验证码")
        print("4. 生成随机验证码")
        print("5. 导出验证码到文件")
        print("6. 验证码格式检查")
        print("0. 退出")
        
        choice = input("\n请输入选择 (0-6): ").strip()
        
        if choice == "0":
            print("再见！")
            break
        elif choice == "1":
            manager.print_codes()
        elif choice == "2":
            count = input("输入要生成的延期验证码数量 (默认10): ").strip()
            count = int(count) if count.isdigit() else 10
            prefix = input("输入验证码前缀 (默认EXTEND2025): ").strip() or "EXTEND2025"
            
            new_codes = manager.generate_extend_codes(count, prefix)
            print(f"\n生成的延期验证码:")
            for i, code in enumerate(new_codes, 1):
                print(f"  {i:2d}. {code}")
        elif choice == "3":
            prefix = input("输入解锁验证码前缀 (默认UNLOCK2025): ").strip() or "UNLOCK2025"
            unlock_code = manager.generate_unlock_code(prefix)
            print(f"\n生成的解锁验证码: {unlock_code}")
        elif choice == "4":
            count = input("输入要生成的随机验证码数量 (默认5): ").strip()
            count = int(count) if count.isdigit() else 5
            length = input("输入验证码长度 (默认12): ").strip()
            length = int(length) if length.isdigit() else 12
            
            random_codes = manager.generate_random_codes(count, length)
            print(f"\n生成的随机验证码:")
            for i, code in enumerate(random_codes, 1):
                print(f"  {i:2d}. {code}")
        elif choice == "5":
            filename = input("输入文件名 (默认verification_codes.json): ").strip()
            filename = filename or "verification_codes.json"
            manager.export_codes_to_file(filename)
        elif choice == "6":
            code = input("输入要检查的验证码: ").strip().upper()
            is_valid, message = manager.validate_code_format(code)
            print(f"验证结果: {'✅ ' + message if is_valid else '❌ ' + message}")
            
            if is_valid:
                code_hash = manager.get_code_hash(code)
                print(f"验证码哈希: {code_hash[:16]}...")
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main()
