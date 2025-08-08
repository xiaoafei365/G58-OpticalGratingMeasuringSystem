#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试脚本
测试Modbus TCP设备与光栅测量系统的集成
"""

import requests
import json
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegrationTester:
    """集成测试类"""
    
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_system_startup(self):
        """测试系统启动"""
        logger.info("测试系统启动...")
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                logger.info("✓ 系统主页访问正常")
                return True
            else:
                logger.error(f"✗ 系统主页访问失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ 系统启动测试失败: {e}")
            return False
    
    def test_modbus_tcp_page(self):
        """测试Modbus TCP控制页面"""
        logger.info("测试Modbus TCP控制页面...")
        try:
            response = self.session.get(f"{self.base_url}/modbus_tcp")
            if response.status_code == 200:
                logger.info("✓ Modbus TCP控制页面访问正常")
                return True
            else:
                logger.error(f"✗ Modbus TCP控制页面访问失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ Modbus TCP页面测试失败: {e}")
            return False
    
    def test_device_list_api(self):
        """测试设备列表API"""
        logger.info("测试设备列表API...")
        try:
            response = self.session.get(f"{self.base_url}/api/modbus_tcp/devices")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ 设备列表API正常，返回 {data.get('count', 0)} 个设备")
                if data.get('devices'):
                    for device in data['devices']:
                        logger.info(f"  - 设备: {device.get('device_name', 'Unknown')} ({device.get('ip_address', 'Unknown')})")
                return True
            else:
                logger.error(f"✗ 设备列表API失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ 设备列表API测试失败: {e}")
            return False
    
    def test_device_status_api(self, device_id="tcp_device_1"):
        """测试设备状态API"""
        logger.info(f"测试设备 {device_id} 状态API...")
        
        # 测试DI状态
        try:
            response = self.session.get(f"{self.base_url}/api/modbus_tcp/device/{device_id}/di_status")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info("✓ DI状态API正常")
                    di_status = data.get('data', {}).get('status', {})
                    for di_name, state in di_status.items():
                        logger.info(f"  - {di_name}: {'高电平' if state else '低电平'}")
                else:
                    logger.warning(f"⚠ DI状态API返回错误: {data.get('message', 'Unknown')}")
            else:
                logger.error(f"✗ DI状态API失败: {response.status_code}")
        except Exception as e:
            logger.error(f"✗ DI状态API测试失败: {e}")
        
        # 测试DO状态
        try:
            response = self.session.get(f"{self.base_url}/api/modbus_tcp/device/{device_id}/do_status")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info("✓ DO状态API正常")
                    do_status = data.get('data', {}).get('status', {})
                    for do_name, state in do_status.items():
                        logger.info(f"  - {do_name}: {'高电平' if state else '低电平'}")
                else:
                    logger.warning(f"⚠ DO状态API返回错误: {data.get('message', 'Unknown')}")
            else:
                logger.error(f"✗ DO状态API失败: {response.status_code}")
        except Exception as e:
            logger.error(f"✗ DO状态API测试失败: {e}")
    
    def test_do_control_api(self, device_id="tcp_device_1"):
        """测试DO控制API"""
        logger.info(f"测试设备 {device_id} DO控制API...")
        
        # 测试单个DO控制
        try:
            # DO1开
            response = self.session.post(
                f"{self.base_url}/api/modbus_tcp/device/{device_id}/do_control",
                json={"do_num": 1, "state": True}
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ DO1控制测试: {data.get('message', 'Success')}")
            else:
                logger.error(f"✗ DO1控制失败: {response.status_code}")
            
            time.sleep(1)
            
            # DO1关
            response = self.session.post(
                f"{self.base_url}/api/modbus_tcp/device/{device_id}/do_control",
                json={"do_num": 1, "state": False}
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ DO1关闭测试: {data.get('message', 'Success')}")
            else:
                logger.error(f"✗ DO1关闭失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"✗ DO控制API测试失败: {e}")
    
    def test_device_info_api(self, device_id="tcp_device_1"):
        """测试设备信息API"""
        logger.info(f"测试设备 {device_id} 信息API...")
        try:
            response = self.session.get(f"{self.base_url}/api/modbus_tcp/device/{device_id}/info")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info("✓ 设备信息API正常")
                    device_info = data.get('data', {})
                    for key, value in device_info.items():
                        logger.info(f"  - {key}: {value}")
                else:
                    logger.warning(f"⚠ 设备信息API返回错误: {data.get('message', 'Unknown')}")
            else:
                logger.error(f"✗ 设备信息API失败: {response.status_code}")
        except Exception as e:
            logger.error(f"✗ 设备信息API测试失败: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始集成测试...")
        logger.info("="*60)
        
        tests = [
            self.test_system_startup,
            self.test_modbus_tcp_page,
            self.test_device_list_api,
            self.test_device_status_api,
            self.test_do_control_api,
            self.test_device_info_api
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
                logger.info("-" * 40)
            except Exception as e:
                logger.error(f"测试执行异常: {e}")
                logger.info("-" * 40)
        
        logger.info("="*60)
        logger.info(f"测试完成: {passed}/{total} 通过")
        
        if passed == total:
            logger.info("🎉 所有测试通过！集成成功！")
        else:
            logger.warning(f"⚠ {total - passed} 个测试失败，请检查系统配置")
        
        return passed == total


def main():
    """主函数"""
    print("Modbus TCP设备集成测试")
    print("="*60)
    print("请确保光栅测量系统正在运行 (http://localhost:5000)")
    print("如果系统运行在其他地址，请修改base_url参数")
    print("="*60)
    
    # 等待用户确认
    input("按回车键开始测试...")
    
    tester = IntegrationTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ 集成测试全部通过！")
        print("您现在可以：")
        print("1. 访问 http://localhost:5000 查看主系统")
        print("2. 访问 http://localhost:5000/modbus_tcp 控制Modbus TCP设备")
        print("3. 使用API接口进行设备控制和状态监控")
    else:
        print("\n❌ 部分测试失败，请检查：")
        print("1. 系统是否正常启动")
        print("2. Modbus TCP设备是否正确配置")
        print("3. 网络连接是否正常")


if __name__ == "__main__":
    main()
