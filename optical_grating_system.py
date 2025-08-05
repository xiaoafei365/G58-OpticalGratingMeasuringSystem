import configparser
import serial
import time
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

@dataclass
class GratingConfig:
    slave_address: int
    reg_address: int
    reg_count: int

@dataclass
class ChannelConfig:
    left_grating: GratingConfig
    right_grating: GratingConfig
    ymax_avg: float
    ymin_avg: float
    halarm_avg: float
    lalarm_avg: float
    base_avg: float

class ConfigManager:
    def __init__(self, ini_path: str = "ProductSetup.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(ini_path, encoding='utf-8')
        
    def get_com_settings(self) -> Dict:
        return {
            'port': self.config.getint('COM', 'Port'),
            'baud': self.config.getint('COM', 'Baud'),
            'debug': self.config.getboolean('COM', 'DEBUG'),
            'pre_send_delay': self.config.getint('COM', 'PreSendDelay'),
            'pre_receive_delay': self.config.getint('COM', 'PreReceiveDelay')
        }
    
    def get_channel_config(self, channel_num: int) -> ChannelConfig:
        left_section = f'Channel_{channel_num}LeftGrating'
        right_section = f'Channel_{channel_num}RightGrating'
        param_section = f'G45_Channel_{channel_num}'
        
        left_grating = GratingConfig(
            slave_address=self.config.getint(left_section, 'SlaveAddress'),
            reg_address=self.config.getint(left_section, 'RegAddress'),
            reg_count=self.config.getint(left_section, 'RegCount')
        )
        
        right_grating = GratingConfig(
            slave_address=self.config.getint(right_section, 'SlaveAddress'),
            reg_address=self.config.getint(right_section, 'RegAddress'),
            reg_count=self.config.getint(right_section, 'RegCount')
        )
        
        return ChannelConfig(
            left_grating=left_grating,
            right_grating=right_grating,
            ymax_avg=self.config.getfloat(param_section, 'X1_YMAX_AVG'),
            ymin_avg=self.config.getfloat(param_section, 'X1_YMIN_AVG'),
            halarm_avg=self.config.getfloat(param_section, 'X1_Halarm_AVG'),
            lalarm_avg=self.config.getfloat(param_section, 'X1_Lalarm_AVG'),
            base_avg=self.config.getfloat(param_section, 'X1_Base_AVG')
        )

class CommunicationManager:
    def __init__(self, com_settings: Dict):
        self.port = com_settings['port']
        self.baud = com_settings['baud']
        self.debug = com_settings['debug']
        self.serial_conn: Optional[serial.Serial] = None
        
    def initialize_serial(self) -> bool:
        try:
            self.serial_conn = serial.Serial(
                port=f'COM{self.port}',
                baudrate=self.baud,
                timeout=1.0
            )
            return True
        except Exception as e:
            logging.error(f"Serial initialization failed: {e}")
            return False
    
    def send_modbus_command(self, slave_addr: int, reg_addr: int, reg_count: int) -> Optional[bytes]:
        if not self.serial_conn:
            return None
            
        # 构建Modbus RTU读取命令
        command = bytearray([
            slave_addr,  # 从机地址
            0x03,        # 功能码：读保持寄存器
            (reg_addr >> 8) & 0xFF,  # 起始地址高字节
            reg_addr & 0xFF,         # 起始地址低字节
            (reg_count >> 8) & 0xFF, # 寄存器数量高字节
            reg_count & 0xFF         # 寄存器数量低字节
        ])
        
        # 计算CRC
        crc = self._calculate_crc(command)
        command.extend(crc.to_bytes(2, 'little'))
        
        try:
            self.serial_conn.write(command)
            time.sleep(0.01)  # 等待响应
            response = self.serial_conn.read(64)
            return response
        except Exception as e:
            logging.error(f"Modbus communication error: {e}")
            return None
    
    def _calculate_crc(self, data: bytearray) -> int:
        # 简化的CRC计算
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

class OpticalGratingSystem:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.comm_manager = CommunicationManager(
            self.config_manager.get_com_settings()
        )
        self.channels: Dict[int, ChannelConfig] = {}
        self.running = False
        
    def initialize(self) -> bool:
        # 初始化通信
        if not self.comm_manager.initialize_serial():
            return False
            
        # 加载通道配置
        for i in range(1, 6):  # 5个通道
            try:
                self.channels[i] = self.config_manager.get_channel_config(i)
            except Exception as e:
                logging.warning(f"Failed to load channel {i} config: {e}")
                
        return True
    
    def start_measurement(self):
        self.running = True
        measurement_thread = threading.Thread(target=self._measurement_loop)
        measurement_thread.start()
    
    def _measurement_loop(self):
        while self.running:
            for channel_num, config in self.channels.items():
                # 读取左光栅
                left_data = self.comm_manager.send_modbus_command(
                    config.left_grating.slave_address,
                    config.left_grating.reg_address,
                    config.left_grating.reg_count
                )
                
                # 读取右光栅
                right_data = self.comm_manager.send_modbus_command(
                    config.right_grating.slave_address,
                    config.right_grating.reg_address,
                    config.right_grating.reg_count
                )
                
                if left_data and right_data:
                    measurement = self._process_measurement(left_data, right_data, config)
                    self._check_alarms(measurement, config)
                    
            time.sleep(0.2)  # 200ms间隔
    
    def _process_measurement(self, left_data: bytes, right_data: bytes, config: ChannelConfig) -> float:
        # 简化的测量处理逻辑
        # 实际实现需要根据具体的数据格式进行解析
        return 220.0  # 示例值
    
    def _check_alarms(self, measurement: float, config: ChannelConfig):
        if measurement > config.halarm_avg:
            logging.warning(f"High alarm: {measurement} > {config.halarm_avg}")
        elif measurement < config.lalarm_avg:
            logging.warning(f"Low alarm: {measurement} < {config.lalarm_avg}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    system = OpticalGratingSystem()
    if system.initialize():
        print("光栅测量系统启动成功")
        system.start_measurement()
    else:
        print("系统初始化失败")