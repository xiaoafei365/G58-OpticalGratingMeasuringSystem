#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus TCP设备通讯模块
用于与C2000-A2-SDD8020-B83设备进行通讯
支持DI状态读取和DO控制
"""

import socket
import struct
import time
import logging
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModbusTCPDevice:
    """Modbus TCP设备通讯类"""
    
    def __init__(self, ip: str = "192.168.0.10", port: int = 502, timeout: int = 5):
        """
        初始化Modbus TCP设备
        
        Args:
            ip: 设备IP地址
            port: 设备端口号
            timeout: 连接超时时间(秒)
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.transaction_id = 0
        
        # 寄存器地址定义(根据文档)
        self.REGISTERS = {
            # 设备信息寄存器
            'MAC_ADDRESS': 40100,      # MAC地址 (3个寄存器)
            'DEVICE_ID': 40103,        # 设备型号
            'VERSION': 40104,          # 模块版本号
            'IP_ADDRESS': 40105,       # IP地址 (2个寄存器)
            'MODBUS_PORT': 40107,      # Modbus TCP端口
            'RESERVED': 40108,         # 保留
            'SUBNET_MASK': 40109,      # 子网掩码 (2个寄存器)
            
            # DI/DO寄存器
            'DO_STATUS': 100,          # DO1-DO2状态 (保持寄存器)
            'DO_CONTROL': 102,         # DO1-DO2控制 (保持寄存器)
            'DI_STATUS': 10200,        # DI1-DI8状态 (输入寄存器)
            'DI_FILTER': 40300,        # DI1-DI8滤波参数 (保持寄存器, 8个)
        }
    
    def connect(self) -> bool:
        """
        连接到Modbus TCP设备
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip, self.port))
            logger.info(f"成功连接到设备 {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.socket:
            try:
                self.socket.close()
                logger.info("已断开设备连接")
            except:
                pass
            finally:
                self.socket = None
    
    def _get_transaction_id(self) -> int:
        """获取事务ID"""
        self.transaction_id = (self.transaction_id + 1) % 65536
        return self.transaction_id
    
    def _build_modbus_frame(self, function_code: int, data: bytes) -> bytes:
        """
        构建Modbus TCP帧
        
        Args:
            function_code: 功能码
            data: 数据部分
            
        Returns:
            bytes: 完整的Modbus TCP帧
        """
        transaction_id = self._get_transaction_id()
        protocol_id = 0
        length = len(data) + 2  # 单元标识符 + 功能码 + 数据
        unit_id = 1
        
        # MBAP头部 (7字节) + PDU
        frame = struct.pack('>HHHBB', transaction_id, protocol_id, length, unit_id, function_code)
        frame += data
        
        return frame
    
    def _send_request(self, frame: bytes) -> Optional[bytes]:
        """
        发送Modbus请求并接收响应
        
        Args:
            frame: Modbus帧
            
        Returns:
            bytes: 响应数据，失败返回None
        """
        if not self.socket:
            logger.error("设备未连接")
            return None
        
        try:
            # 发送请求
            self.socket.send(frame)
            
            # 接收响应头部(7字节MBAP + 1字节功能码)
            response = self.socket.recv(8)
            if len(response) < 8:
                logger.error("响应数据不完整")
                return None
            
            # 解析MBAP头部
            trans_id, proto_id, length, unit_id, func_code = struct.unpack('>HHHBB', response)
            
            # 接收剩余数据
            remaining = length - 2  # 减去单元标识符和功能码
            if remaining > 0:
                data = self.socket.recv(remaining)
                response += data
            
            return response[7:]  # 返回PDU部分(功能码+数据)
            
        except Exception as e:
            logger.error(f"通讯错误: {e}")
            return None
    
    def read_holding_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """
        读取保持寄存器 (功能码0x03)
        
        Args:
            start_address: 起始地址
            count: 寄存器数量
            
        Returns:
            List[int]: 寄存器值列表，失败返回None
        """
        # 构建请求数据
        data = struct.pack('>HH', start_address, count)
        frame = self._build_modbus_frame(0x03, data)
        
        # 发送请求
        response = self._send_request(frame)
        if not response:
            return None
        
        # 解析响应
        if len(response) < 2:
            logger.error("响应数据长度不足")
            return None
        
        func_code, byte_count = struct.unpack('>BB', response[:2])
        
        if func_code & 0x80:  # 错误响应
            error_code = response[1]
            logger.error(f"Modbus错误: 功能码={func_code}, 错误码={error_code}")
            return None
        
        # 解析寄存器值
        values = []
        for i in range(count):
            offset = 2 + i * 2
            if offset + 1 < len(response):
                value = struct.unpack('>H', response[offset:offset+2])[0]
                values.append(value)
        
        return values
    
    def read_input_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """
        读取输入寄存器 (功能码0x04)
        
        Args:
            start_address: 起始地址
            count: 寄存器数量
            
        Returns:
            List[int]: 寄存器值列表，失败返回None
        """
        # 构建请求数据
        data = struct.pack('>HH', start_address, count)
        frame = self._build_modbus_frame(0x04, data)
        
        # 发送请求
        response = self._send_request(frame)
        if not response:
            return None
        
        # 解析响应
        if len(response) < 2:
            logger.error("响应数据长度不足")
            return None
        
        func_code, byte_count = struct.unpack('>BB', response[:2])
        
        if func_code & 0x80:  # 错误响应
            error_code = response[1]
            logger.error(f"Modbus错误: 功能码={func_code}, 错误码={error_code}")
            return None
        
        # 解析寄存器值
        values = []
        for i in range(count):
            offset = 2 + i * 2
            if offset + 1 < len(response):
                value = struct.unpack('>H', response[offset:offset+2])[0]
                values.append(value)
        
        return values
    
    def write_single_register(self, address: int, value: int) -> bool:
        """
        写单个保持寄存器 (功能码0x06)
        
        Args:
            address: 寄存器地址
            value: 要写入的值
            
        Returns:
            bool: 写入是否成功
        """
        # 构建请求数据
        data = struct.pack('>HH', address, value)
        frame = self._build_modbus_frame(0x06, data)
        
        # 发送请求
        response = self._send_request(frame)
        if not response:
            return False
        
        # 检查响应
        if len(response) < 5:
            logger.error("响应数据长度不足")
            return False
        
        func_code = response[0]
        if func_code & 0x80:  # 错误响应
            error_code = response[1]
            logger.error(f"Modbus错误: 功能码={func_code}, 错误码={error_code}")
            return False
        
        return True

    # ==================== DI/DO 操作方法 ====================

    def get_di_status(self) -> Optional[Dict[str, bool]]:
        """
        获取所有DI点的状态

        Returns:
            Dict[str, bool]: DI状态字典 {'DI1': True, 'DI2': False, ...}
        """
        # 读取DI状态寄存器 (地址10200, 8个DI需要1个寄存器)
        values = self.read_input_registers(self.REGISTERS['DI_STATUS'], 1)
        if values is None:
            logger.error("读取DI状态失败")
            return None

        # 解析DI状态 (每个bit代表一个DI)
        di_value = values[0]
        di_status = {}
        for i in range(8):
            di_status[f'DI{i+1}'] = bool(di_value & (1 << i))

        return di_status

    def get_do_status(self) -> Optional[Dict[str, bool]]:
        """
        获取所有DO点的状态

        Returns:
            Dict[str, bool]: DO状态字典 {'DO1': True, 'DO2': False}
        """
        # 读取DO状态寄存器 (地址100)
        values = self.read_holding_registers(self.REGISTERS['DO_STATUS'], 1)
        if values is None:
            logger.error("读取DO状态失败")
            return None

        # 解析DO状态 (bit0=DO1, bit1=DO2)
        do_value = values[0]
        do_status = {
            'DO1': bool(do_value & 0x01),
            'DO2': bool(do_value & 0x02)
        }

        return do_status

    def set_do_output(self, do_num: int, state: bool) -> bool:
        """
        设置单个DO输出状态

        Args:
            do_num: DO编号 (1或2)
            state: 输出状态 (True=高电平, False=低电平)

        Returns:
            bool: 设置是否成功
        """
        if do_num not in [1, 2]:
            logger.error("DO编号必须是1或2")
            return False

        # 先读取当前DO状态
        current_status = self.get_do_status()
        if current_status is None:
            return False

        # 计算新的DO值
        do_value = 0
        if current_status['DO1'] or (do_num == 1 and state):
            do_value |= 0x01
        if current_status['DO2'] or (do_num == 2 and state):
            do_value |= 0x02

        # 如果要关闭指定DO
        if do_num == 1 and not state:
            do_value &= ~0x01
        elif do_num == 2 and not state:
            do_value &= ~0x02

        # 写入DO控制寄存器
        success = self.write_single_register(self.REGISTERS['DO_CONTROL'], do_value)
        if success:
            logger.info(f"DO{do_num} 设置为 {'高电平' if state else '低电平'}")
        else:
            logger.error(f"设置DO{do_num}失败")

        return success

    def set_all_do_output(self, do1_state: bool, do2_state: bool) -> bool:
        """
        同时设置所有DO输出状态

        Args:
            do1_state: DO1状态
            do2_state: DO2状态

        Returns:
            bool: 设置是否成功
        """
        do_value = 0
        if do1_state:
            do_value |= 0x01
        if do2_state:
            do_value |= 0x02

        success = self.write_single_register(self.REGISTERS['DO_CONTROL'], do_value)
        if success:
            logger.info(f"DO1={'高' if do1_state else '低'}, DO2={'高' if do2_state else '低'}")
        else:
            logger.error("设置DO输出失败")

        return success

    # ==================== 设备信息读取方法 ====================

    def get_device_info(self) -> Optional[Dict]:
        """
        获取设备信息

        Returns:
            Dict: 设备信息字典
        """
        try:
            info = {}

            # 读取MAC地址 (3个寄存器)
            mac_values = self.read_holding_registers(self.REGISTERS['MAC_ADDRESS'], 3)
            if mac_values:
                mac_bytes = []
                for value in mac_values:
                    mac_bytes.extend([value >> 8, value & 0xFF])
                info['mac_address'] = ':'.join([f'{b:02X}' for b in mac_bytes])

            # 读取设备型号
            device_id = self.read_holding_registers(self.REGISTERS['DEVICE_ID'], 1)
            if device_id:
                info['device_id'] = device_id[0]

            # 读取版本号
            version = self.read_holding_registers(self.REGISTERS['VERSION'], 1)
            if version:
                info['version'] = f"{version[0] >> 8}.{version[0] & 0xFF}"

            # 读取IP地址 (2个寄存器)
            ip_values = self.read_holding_registers(self.REGISTERS['IP_ADDRESS'], 2)
            if ip_values:
                ip_bytes = []
                for value in ip_values:
                    ip_bytes.extend([value >> 8, value & 0xFF])
                info['ip_address'] = '.'.join([str(b) for b in ip_bytes])

            # 读取Modbus端口
            port = self.read_holding_registers(self.REGISTERS['MODBUS_PORT'], 1)
            if port:
                info['modbus_port'] = port[0]

            return info

        except Exception as e:
            logger.error(f"读取设备信息失败: {e}")
            return None

    # ==================== 上下文管理器支持 ====================

    def __enter__(self):
        """进入上下文管理器"""
        if self.connect():
            return self
        else:
            raise ConnectionError(f"无法连接到设备 {self.ip}:{self.port}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        self.disconnect()


# ==================== 使用示例 ====================

def main():
    """使用示例"""
    # 创建设备实例
    device = ModbusTCPDevice(ip="192.168.0.10", port=502)

    try:
        # 使用上下文管理器自动管理连接
        with device:
            print("=== 设备信息 ===")
            device_info = device.get_device_info()
            if device_info:
                for key, value in device_info.items():
                    print(f"{key}: {value}")

            print("\n=== DI状态监测 ===")
            # 读取DI状态
            di_status = device.get_di_status()
            if di_status:
                for di_name, state in di_status.items():
                    print(f"{di_name}: {'高电平' if state else '低电平'}")

            print("\n=== DO控制测试 ===")
            # 读取当前DO状态
            do_status = device.get_do_status()
            if do_status:
                print("当前DO状态:")
                for do_name, state in do_status.items():
                    print(f"{do_name}: {'高电平' if state else '低电平'}")

            # 控制DO输出
            print("\n控制DO1输出...")
            device.set_do_output(1, True)   # DO1输出高电平
            time.sleep(1)
            device.set_do_output(1, False)  # DO1输出低电平

            print("控制DO2输出...")
            device.set_do_output(2, True)   # DO2输出高电平
            time.sleep(1)
            device.set_do_output(2, False)  # DO2输出低电平

            # 同时控制所有DO
            print("同时控制所有DO...")
            device.set_all_do_output(True, True)   # 全部输出高电平
            time.sleep(1)
            device.set_all_do_output(False, False) # 全部输出低电平

    except Exception as e:
        logger.error(f"程序执行错误: {e}")


if __name__ == "__main__":
    main()
