#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动光栅测量系统
"""

import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('optical_grating_web_system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def main():
    """主函数"""
    print("=" * 60)
    print("🔬 光栅测量系统 - Web版")
    print("=" * 60)
    
    try:
        from optical_grating_web_system import OpticalGratingWebSystem
        
        # 创建系统实例
        system = OpticalGratingWebSystem()

        # 显示试用期状态
        trial_status = system.trial_manager.get_trial_status()
        print(f"\n📅 试用期状态:")
        if trial_status['is_trial']:
            if trial_status['is_expired']:
                print(f"   ❌ 试用期已到期 (已使用 {trial_status['days_used']} 天)")
                print(f"   🔒 系统已锁定，需要验证码解锁")
            else:
                print(f"   ⏰ 剩余 {trial_status['days_remaining']} 天 (已使用 {trial_status['days_used']} 天)")
                if trial_status['days_remaining'] <= 7:
                    print(f"   ⚠️  试用期即将到期")
        else:
            print(f"   ✅ 系统已解锁，无使用限制")

        # 检查数据库状态
        if system.db_manager.available:
            tables = system.db_manager.get_available_tables()
            print(f"\n✅ 数据库连接成功，找到 {len(tables)} 个图表数据表")
            for table in tables[:5]:  # 只显示前5个表
                print(f"   📊 {table}")
            if len(tables) > 5:
                print(f"   ... 还有 {len(tables) - 5} 个表")
        else:
            print("\n⚠️  数据库不可用，将使用模拟数据")
        
        print("\n🌐 启动Web服务器...")
        print("📍 访问地址: http://localhost:5000")
        print("🔧 配置页面: http://localhost:5000/config")
        print("🔍 调试页面: http://localhost:5000/debug")
        print("📊 数据库信息: http://localhost:5000/api/get_database_info")
        print("🔑 试用期管理: http://localhost:5000/trial")
        print("🧪 试用期测试: http://localhost:5000/test_trial")
        print("\n按 Ctrl+C 停止服务器")
        print("-" * 60)
        
        # 启动系统
        system.run(host='0.0.0.0', port=5000, debug=True)
        
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保安装了所需的依赖包:")
        print("pip install flask flask-socketio pyserial numpy configparser")
        print("pip install pyodbc  # 用于数据库访问")
        
    except Exception as e:
        print(f"❌ 系统启动失败: {e}")
        logging.error(f"系统启动失败: {e}")

if __name__ == "__main__":
    main()
