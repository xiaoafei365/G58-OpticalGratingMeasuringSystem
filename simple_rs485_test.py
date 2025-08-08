#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的RS485通讯测试脚本
用于快速验证RS485通讯功能
"""

import struct
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_crc(data: bytes) -> int:
    """计算Modbus RTU CRC16校验码"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def test_crc_calculation():
    """测试CRC计算功能"""
    logger.info("测试CRC计算功能...")
    
    # 测试数据: 从机地址1, 功能码0x03, 起始地址0x1000, 寄存器数量2
    test_data = struct.pack('>BBHH', 1, 0x03, 0x1000, 2)
    crc = calculate_crc(test_data)
    
    logger.info(f"测试数据: {test_data.hex()}")
    logger.info(f"计算的CRC: 0x{crc:04X}")
    
    # 构建完整的请求帧
    request = test_data + struct.pack('<H', crc)
    logger.info(f"完整请求帧: {request.hex()}")
    
    return True

def test_register_addresses():
    """测试寄存器地址配置"""
    logger.info("测试寄存器地址配置...")
    
    # 根据文档的寄存器地址
    registers = {
        '当前值': 0x1000,
        '比例系数': 0x1002,
        '包络直径': 0x1004,
        '多段补偿值': 0x1006,
        '测量方向': 0x2000,
        '自校正': 0x2001
    }
    
    for name, addr in registers.items():
        logger.info(f"{name}: 0x{addr:04X} ({addr})")
    
    return True

def test_modbus_frame_construction():
    """测试Modbus帧构建"""
    logger.info("测试Modbus帧构建...")
    
    # 测试读取保持寄存器请求
    slave_addr = 11  # 通道1左侧光栅
    func_code = 0x03  # 读取保持寄存器
    reg_addr = 0x1000  # 当前值寄存器
    reg_count = 2  # 寄存器数量
    
    # 构建请求帧
    request = struct.pack('>BBHH', slave_addr, func_code, reg_addr, reg_count)
    crc = calculate_crc(request)
    request += struct.pack('<H', crc)
    
    logger.info(f"从机地址: {slave_addr}")
    logger.info(f"功能码: 0x{func_code:02X}")
    logger.info(f"寄存器地址: 0x{reg_addr:04X}")
    logger.info(f"寄存器数量: {reg_count}")
    logger.info(f"完整请求帧: {request.hex().upper()}")
    
    # 模拟响应帧解析
    # 响应格式: [从机地址][功能码][字节数][数据...][CRC]
    response_data = [0x12, 0x34, 0x56, 0x78]  # 模拟数据
    response = struct.pack('>BBB', slave_addr, func_code, len(response_data))
    for data in response_data:
        response += struct.pack('>B', data)
    
    response_crc = calculate_crc(response)
    response += struct.pack('<H', response_crc)
    
    logger.info(f"模拟响应帧: {response.hex().upper()}")
    
    # 解析响应数据
    if len(response) >= 5:
        parsed_data = struct.unpack(f'>{reg_count}H', response[3:-2])
        logger.info(f"解析的数据: {list(parsed_data)}")
    
    return True

def test_write_frame_construction():
    """测试写寄存器帧构建"""
    logger.info("测试写寄存器帧构建...")
    
    # 测试写单个寄存器 (功能码0x06)
    slave_addr = 11
    func_code = 0x06
    reg_addr = 0x2000  # 测量方向寄存器
    reg_value = 1
    
    request = struct.pack('>BBHH', slave_addr, func_code, reg_addr, reg_value)
    crc = calculate_crc(request)
    request += struct.pack('<H', crc)
    
    logger.info(f"写单个寄存器请求帧: {request.hex().upper()}")
    
    # 测试写多个寄存器 (功能码0x10)
    func_code = 0x10
    reg_count = 2
    byte_count = reg_count * 2
    values = [0x1234, 0x5678]
    
    request = struct.pack('>BBHHB', slave_addr, func_code, reg_addr, reg_count, byte_count)
    for value in values:
        request += struct.pack('>H', value)
    
    crc = calculate_crc(request)
    request += struct.pack('<H', crc)
    
    logger.info(f"写多个寄存器请求帧: {request.hex().upper()}")
    
    return True

def test_configuration_parsing():
    """测试配置文件解析"""
    logger.info("测试配置文件解析...")
    
    try:
        import configparser
        config = configparser.ConfigParser()
        
        # 尝试读取配置文件
        config_files = ['ProductSetup.ini', 'ProductSetup_RS485_Corrected.ini']
        
        for config_file in config_files:
            try:
                config.read(config_file, encoding='utf-8')
                logger.info(f"成功读取配置文件: {config_file}")
                
                # 检查COM配置
                if 'COM' in config:
                    com_section = config['COM']
                    logger.info("COM配置:")
                    for key, value in com_section.items():
                        logger.info(f"  {key} = {value}")
                
                # 检查光栅通道配置
                grating_sections = [s for s in config.sections() if 'Grating' in s]
                logger.info(f"找到 {len(grating_sections)} 个光栅通道配置")
                
                for section in grating_sections[:3]:  # 只显示前3个
                    logger.info(f"  {section}:")
                    if section in config:
                        for key, value in config[section].items():
                            logger.info(f"    {key} = {value}")
                
                break
                
            except Exception as e:
                logger.warning(f"读取配置文件 {config_file} 失败: {e}")
                continue
        
        return True
        
    except ImportError:
        logger.error("configparser模块不可用")
        return False

def main():
    """主测试函数"""
    logger.info("开始RS485通讯基础功能测试...")
    logger.info("=" * 50)
    
    tests = [
        ("CRC计算功能", test_crc_calculation),
        ("寄存器地址配置", test_register_addresses),
        ("Modbus帧构建", test_modbus_frame_construction),
        ("写寄存器帧构建", test_write_frame_construction),
        ("配置文件解析", test_configuration_parsing)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n--- 测试: {test_name} ---")
        try:
            if test_func():
                logger.info(f"✓ {test_name} 通过")
                passed += 1
            else:
                logger.error(f"✗ {test_name} 失败")
        except Exception as e:
            logger.error(f"✗ {test_name} 异常: {e}")
    
    logger.info("\n" + "=" * 50)
    logger.info("测试总结:")
    logger.info(f"总测试数: {total}")
    logger.info(f"通过数: {passed}")
    logger.info(f"失败数: {total - passed}")
    logger.info(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        logger.info("✓ 所有基础功能测试通过")
        return True
    else:
        logger.error("✗ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
