#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统状态检查工具
用于检查光学光栅测量系统的各项状态
"""

import os
import sys
import pickle
from datetime import datetime, timedelta
import json

def check_trial_status():
    """检查试用期状态"""
    print("=" * 50)
    print("试用期状态检查")
    print("=" * 50)
    
    trial_file = "trial_info.dat"
    
    if not os.path.exists(trial_file):
        print("❌ 试用期文件不存在")
        print("   系统将在首次运行时创建新的试用期")
        return
    
    try:
        with open(trial_file, 'rb') as f:
            data = pickle.load(f)
        
        start_time = data.get('start_time')
        used_codes = set(data.get('used_codes', []))
        is_unlimited = data.get('is_unlimited', False)
        
        print(f"✅ 试用期文件存在")
        print(f"   文件大小: {os.path.getsize(trial_file)} 字节")
        print(f"   开始时间: {start_time}")
        print(f"   已使用验证码数量: {len(used_codes)}")
        print(f"   系统解锁状态: {'已解锁' if is_unlimited else '未解锁'}")
        
        if used_codes:
            print(f"   已使用的验证码:")
            for i, code in enumerate(used_codes, 1):
                print(f"     {i}. {code}")
        
        if not is_unlimited and start_time:
            now = datetime.now()
            days_used = (now - start_time).days
            days_remaining = max(0, 30 - days_used)
            is_expired = days_remaining <= 0
            
            print(f"\n📅 试用期详情:")
            print(f"   已使用天数: {days_used}")
            print(f"   剩余天数: {days_remaining}")
            print(f"   是否过期: {'是' if is_expired else '否'}")
            print(f"   状态: {'🔒 已锁定' if is_expired else '✅ 可用'}")
            
            if is_expired:
                print(f"\n⚠️  系统已锁定，需要验证码解锁")
            elif days_remaining <= 7:
                print(f"\n⚠️  试用期即将到期，剩余 {days_remaining} 天")
        
    except Exception as e:
        print(f"❌ 读取试用期文件失败: {e}")

def check_config_files():
    """检查配置文件"""
    print("\n" + "=" * 50)
    print("配置文件检查")
    print("=" * 50)
    
    config_files = [
        "ProductSetup.ini",
        "optical_grating_web_system.py",
        "templates/index.html",
        "templates/trial_manager.html"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            size = os.path.getsize(config_file)
            mtime = datetime.fromtimestamp(os.path.getmtime(config_file))
            print(f"✅ {config_file}")
            print(f"   大小: {size:,} 字节")
            print(f"   修改时间: {mtime}")
        else:
            print(f"❌ {config_file} - 文件不存在")

def check_log_files():
    """检查日志文件"""
    print("\n" + "=" * 50)
    print("日志文件检查")
    print("=" * 50)
    
    log_files = [
        "optical_grating_web_system.log",
        "optical_grating_system.log"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
            print(f"✅ {log_file}")
            print(f"   大小: {size:,} 字节")
            print(f"   修改时间: {mtime}")
            
            # 显示最后几行日志
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"   最后一条日志: {lines[-1].strip()}")
            except:
                pass
        else:
            print(f"❌ {log_file} - 文件不存在")

def check_database_files():
    """检查数据库文件"""
    print("\n" + "=" * 50)
    print("数据库文件检查")
    print("=" * 50)
    
    db_files = [
        "guangshan.mdb"
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            size = os.path.getsize(db_file)
            mtime = datetime.fromtimestamp(os.path.getmtime(db_file))
            print(f"✅ {db_file}")
            print(f"   大小: {size:,} 字节")
            print(f"   修改时间: {mtime}")
        else:
            print(f"❌ {db_file} - 文件不存在 (将使用模拟数据)")

def check_system_dependencies():
    """检查系统依赖"""
    print("\n" + "=" * 50)
    print("系统依赖检查")
    print("=" * 50)
    
    required_modules = [
        ('flask', 'Flask Web框架'),
        ('flask_socketio', 'WebSocket支持'),
        ('numpy', '数值计算'),
        ('serial', '串口通信'),
        ('pyodbc', '数据库连接 (可选)'),
        ('configparser', '配置文件解析'),
        ('pickle', '数据序列化'),
        ('hashlib', '哈希计算'),
        ('secrets', '安全随机数')
    ]
    
    missing_modules = []
    
    for module_name, description in required_modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name} - {description}")
        except ImportError:
            print(f"❌ {module_name} - {description} (未安装)")
            missing_modules.append(module_name)
    
    if missing_modules:
        print(f"\n⚠️  缺少 {len(missing_modules)} 个依赖模块")
        print("安装命令:")
        print(f"pip install {' '.join(missing_modules)}")
    else:
        print(f"\n✅ 所有依赖模块都已安装")

def generate_system_report():
    """生成系统报告"""
    print("\n" + "=" * 50)
    print("生成系统报告")
    print("=" * 50)
    
    report = {
        "report_time": datetime.now().isoformat(),
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "current_directory": os.getcwd()
        },
        "files_status": {},
        "trial_status": {}
    }
    
    # 检查文件状态
    important_files = [
        "trial_info.dat",
        "ProductSetup.ini",
        "optical_grating_web_system.py",
        "guangshan.mdb"
    ]
    
    for file_path in important_files:
        if os.path.exists(file_path):
            report["files_status"][file_path] = {
                "exists": True,
                "size": os.path.getsize(file_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
        else:
            report["files_status"][file_path] = {
                "exists": False
            }
    
    # 检查试用期状态
    trial_file = "trial_info.dat"
    if os.path.exists(trial_file):
        try:
            with open(trial_file, 'rb') as f:
                data = pickle.load(f)
            
            start_time = data.get('start_time')
            used_codes = data.get('used_codes', [])
            is_unlimited = data.get('is_unlimited', False)
            
            if start_time and not is_unlimited:
                days_used = (datetime.now() - start_time).days
                days_remaining = max(0, 30 - days_used)
                is_expired = days_remaining <= 0
            else:
                days_used = 0
                days_remaining = -1 if is_unlimited else 30
                is_expired = False
            
            report["trial_status"] = {
                "start_time": start_time.isoformat() if start_time else None,
                "used_codes_count": len(used_codes),
                "is_unlimited": is_unlimited,
                "days_used": days_used,
                "days_remaining": days_remaining,
                "is_expired": is_expired
            }
        except:
            report["trial_status"] = {"error": "无法读取试用期信息"}
    
    # 保存报告
    report_file = f"system_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 系统报告已生成: {report_file}")
    return report_file

def main():
    """主函数"""
    print("光学光栅测量系统 - 状态检查工具")
    print("System Status Checker")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 执行各项检查
    check_trial_status()
    check_config_files()
    check_log_files()
    check_database_files()
    check_system_dependencies()
    
    # 询问是否生成报告
    print("\n" + "=" * 50)
    generate_report = input("是否生成详细的系统报告？(y/N): ").strip().lower()
    if generate_report in ['y', 'yes']:
        report_file = generate_system_report()
        print(f"报告文件: {report_file}")
    
    print("\n检查完成！")

if __name__ == "__main__":
    main()
