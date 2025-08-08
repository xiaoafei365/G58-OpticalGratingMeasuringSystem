#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RS485通讯功能测试脚本
用于测试和验证RS485-MODBUS通讯功能是否正常
根据通讯地址文档进行测试
"""

import sys
import time
import logging
import configparser
from typing import Dict, List, Optional

# 尝试导入主程序模块
try:
    from optical_grating_web_system import ModbusCommunication, ConfigManager
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保 optical_grating_web_system.py 文件存在且可访问")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rs485_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class RS485Tester:
    """RS485通讯测试类"""
    
    def __init__(self, config_path: str = "ProductSetup.ini"):
        """初始化测试器"""
        self.config_manager = ConfigManager(config_path)
        self.modbus_comm = None
        
        # 测试用的寄存器地址 (根据文档)
        self.test_registers = {
            '当前值': {'address': 0x1000, 'count': 2, 'description': '当前值寄存器 (RAH:高位, RAL:低位)'},
            '比例系数': {'address': 0x1002, 'count': 2, 'description': '比例系数寄存器 (范围: 1~29999)'},
            '包络直径': {'address': 0x1004, 'count': 2, 'description': '包络直径寄存器 (范围: 1~40000mm)'},
            '多段补偿值': {'address': 0x1006, 'count': 2, 'description': '多段补偿值寄存器 (范围: 0~9000mm)'},
            '测量方向': {'address': 0x2000, 'count': 1, 'description': '测量方向寄存器 (范围: 0~1)'},
            '自校正': {'address': 0x2001, 'count': 1, 'description': '自校正寄存器'}
        }
        
        # 测试用的从机地址
        self.test_slaves = [1, 2, 3, 11, 12, 21, 22]
        
    def initialize_communication(self, force_simulation: bool = False) -> bool:
        """初始化通讯"""
        try:
            com_settings = self.config_manager.get_com_settings()
            logger.info(f"通讯设置: {com_settings}")

            self.modbus_comm = ModbusCommunication(com_settings)

            if force_simulation:
                # 强制使用模拟模式进行测试
                self.modbus_comm.simulation_mode = True
                logger.info("强制启用模拟模式进行测试")
                success = True
            else:
                success = self.modbus_comm.initialize_serial()

            if success:
                logger.info("RS485通讯初始化成功")
                if self.modbus_comm.simulation_mode:
                    logger.warning("当前运行在模拟模式")
                else:
                    logger.info("当前运行在实际通讯模式")
            else:
                logger.error("RS485通讯初始化失败")

            return success

        except Exception as e:
            logger.error(f"初始化通讯失败: {e}")
            return False
    
    def test_single_register_read(self, slave_addr: int, reg_name: str, reg_info: Dict) -> bool:
        """测试单个寄存器读取"""
        try:
            logger.info(f"测试读取从机{slave_addr} - {reg_name} (地址: 0x{reg_info['address']:04X})")
            
            result = self.modbus_comm.read_holding_registers(
                slave_addr=slave_addr,
                reg_addr=reg_info['address'],
                reg_count=reg_info['count']
            )
            
            if result is not None:
                logger.info(f"读取成功: {result} - {reg_info['description']}")
                return True
            else:
                logger.error(f"读取失败: 从机{slave_addr}, {reg_name}")
                return False
                
        except Exception as e:
            logger.error(f"读取异常: 从机{slave_addr}, {reg_name} - {e}")
            return False
    
    def test_register_write(self, slave_addr: int) -> bool:
        """测试寄存器写入功能"""
        try:
            # 测试写入测量方向寄存器 (地址0x2000)
            test_value = 1
            logger.info(f"测试写入从机{slave_addr} - 测量方向寄存器 (地址: 0x2000), 值: {test_value}")
            
            success = self.modbus_comm.write_single_register(
                slave_addr=slave_addr,
                reg_addr=0x2000,
                value=test_value
            )
            
            if success:
                logger.info(f"写入成功: 从机{slave_addr}, 值{test_value}")
                
                # 读取验证
                time.sleep(0.1)  # 短暂延时
                result = self.modbus_comm.read_holding_registers(
                    slave_addr=slave_addr,
                    reg_addr=0x2000,
                    reg_count=1
                )
                
                if result and len(result) > 0:
                    if result[0] == test_value:
                        logger.info(f"写入验证成功: 读取值{result[0]}与写入值{test_value}一致")
                        return True
                    else:
                        logger.warning(f"写入验证失败: 读取值{result[0]}与写入值{test_value}不一致")
                        return False
                else:
                    logger.error("写入后读取验证失败")
                    return False
            else:
                logger.error(f"写入失败: 从机{slave_addr}")
                return False
                
        except Exception as e:
            logger.error(f"写入测试异常: 从机{slave_addr} - {e}")
            return False
    
    def test_all_slaves_and_registers(self) -> Dict[str, Dict]:
        """测试所有从机和寄存器"""
        results = {}
        
        logger.info("开始全面测试所有从机和寄存器...")
        
        for slave_addr in self.test_slaves:
            logger.info(f"\n{'='*50}")
            logger.info(f"测试从机地址: {slave_addr}")
            logger.info(f"{'='*50}")
            
            slave_results = {}
            
            # 测试读取所有寄存器
            for reg_name, reg_info in self.test_registers.items():
                success = self.test_single_register_read(slave_addr, reg_name, reg_info)
                slave_results[f"read_{reg_name}"] = success
                time.sleep(0.1)  # 短暂延时避免通讯冲突
            
            # 测试写入功能 (仅对部分从机测试)
            if slave_addr in [1, 11, 21]:  # 选择性测试写入功能
                success = self.test_register_write(slave_addr)
                slave_results["write_test"] = success
                time.sleep(0.1)
            
            results[f"slave_{slave_addr}"] = slave_results
            
            # 统计该从机的测试结果
            passed = sum(1 for v in slave_results.values() if v)
            total = len(slave_results)
            logger.info(f"从机{slave_addr}测试完成: {passed}/{total} 通过")
        
        return results
    
    def generate_test_report(self, results: Dict[str, Dict]) -> str:
        """生成测试报告"""
        report = []
        report.append("RS485通讯功能测试报告")
        report.append("=" * 50)
        report.append(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"通讯模式: {'模拟模式' if self.modbus_comm.simulation_mode else '实际通讯模式'}")
        report.append("")
        
        total_tests = 0
        passed_tests = 0
        
        for slave_key, slave_results in results.items():
            slave_addr = slave_key.replace('slave_', '')
            report.append(f"从机地址 {slave_addr}:")
            report.append("-" * 30)
            
            for test_name, success in slave_results.items():
                status = "✓ 通过" if success else "✗ 失败"
                report.append(f"  {test_name}: {status}")
                total_tests += 1
                if success:
                    passed_tests += 1
            
            report.append("")
        
        # 总结
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        report.append("测试总结:")
        report.append("-" * 30)
        report.append(f"总测试数: {total_tests}")
        report.append(f"通过数: {passed_tests}")
        report.append(f"失败数: {total_tests - passed_tests}")
        report.append(f"成功率: {success_rate:.1f}%")
        
        if success_rate >= 80:
            report.append("✓ RS485通讯功能基本正常")
        elif success_rate >= 50:
            report.append("⚠ RS485通讯功能部分正常，建议检查配置")
        else:
            report.append("✗ RS485通讯功能存在问题，需要排查")
        
        return "\n".join(report)
    
    def run_comprehensive_test(self, simulation_mode: bool = False) -> bool:
        """运行综合测试"""
        logger.info("开始RS485通讯综合测试...")

        # 初始化通讯
        if not self.initialize_communication(force_simulation=simulation_mode):
            logger.error("通讯初始化失败，测试终止")
            return False
        
        try:
            # 执行全面测试
            results = self.test_all_slaves_and_registers()
            
            # 生成并显示报告
            report = self.generate_test_report(results)
            print("\n" + report)
            
            # 保存报告到文件
            with open('rs485_test_report.txt', 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info("测试报告已保存到 rs485_test_report.txt")
            
            # 判断测试是否成功
            total_tests = sum(len(slave_results) for slave_results in results.values())
            passed_tests = sum(sum(1 for v in slave_results.values() if v) 
                             for slave_results in results.values())
            success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
            
            return success_rate >= 80
            
        except Exception as e:
            logger.error(f"测试过程中发生异常: {e}")
            return False
        
        finally:
            # 清理资源
            if self.modbus_comm and self.modbus_comm.serial_conn:
                try:
                    self.modbus_comm.serial_conn.close()
                    logger.info("串口连接已关闭")
                except:
                    pass


def main():
    """主函数"""
    print("RS485通讯功能测试工具")
    print("=" * 50)

    # 检查命令行参数
    config_file = "ProductSetup.ini"
    simulation_mode = False

    for arg in sys.argv[1:]:
        if arg.endswith('.ini'):
            config_file = arg
        elif arg == '--simulation' or arg == '-s':
            simulation_mode = True

    print(f"使用配置文件: {config_file}")
    if simulation_mode:
        print("运行模式: 模拟模式")
    else:
        print("运行模式: 实际通讯模式")

    # 创建测试器并运行测试
    tester = RS485Tester(config_file)
    success = tester.run_comprehensive_test(simulation_mode=simulation_mode)

    if success:
        print("\n✓ RS485通讯功能测试通过")
        sys.exit(0)
    else:
        print("\n✗ RS485通讯功能测试失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
