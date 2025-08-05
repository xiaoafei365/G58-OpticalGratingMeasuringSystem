import configparser
import serial
import time
import threading
import struct
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis
from PyQt5.QtGui import QPainter
import numpy as np

@dataclass
class GratingConfig:
    slave_address: int
    reg_address: int
    reg_count: int

@dataclass
class ChannelConfig:
    left_grating: GratingConfig
    right_grating: GratingConfig
    x1_ymax_avg: float
    x1_ymin_avg: float
    x1_halarm_avg: float
    x1_lalarm_avg: float
    x1_base_avg: float
    x2_ymax_avg: float = 0.0
    x2_ymin_avg: float = 0.0
    t_ymax_avg: float = 0.0
    t_ymin_avg: float = 0.0

@dataclass
class CPKLimits:
    x1_max: float
    x1_min: float
    x2_max: float = 0.0
    x2_min: float = 0.0
    t_max: float = 0.0
    t_min: float = 0.0

class ConfigManager:
    def __init__(self, ini_path: str = "ProductSetup.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(ini_path, encoding='utf-8')
        
    def get_front_or_back(self) -> int:
        """获取前门/后门设置"""
        return self.config.getint('FrontOrBack', 'setVal', fallback=1)
        
    def get_com_settings(self) -> Dict:
        return {
            'port': self.config.getint('COM', 'Port'),
            'baud': self.config.getint('COM', 'Baud'),
            'debug': self.config.getboolean('COM', 'DEBUG'),
            'pre_send_delay': self.config.getint('COM', 'PreSendDelay'),
            'pre_receive_delay': self.config.getint('COM', 'PreReceiveDelay')
        }
    
    def get_round_display_settings(self) -> Dict:
        return {
            'round_time_interval': self.config.getint('RoundDisplay', 'RoundTimeInterval'),
            'residence_time': self.config.getint('RoundDisplay', 'ResidenceTimeAfterMeasurement'),
            'read_slave_interval': self.config.getint('RoundDisplay', 'ReadSlaveTimeInterval'),
            'grating_interval': self.config.getint('RoundDisplay', 'GratingSendAndRecvTimeInterval')
        }
    
    def get_channel_config(self, channel_num: int) -> ChannelConfig:
        left_section = f'Channel_{channel_num}LeftGrating'
        right_section = f'Channel_{channel_num}RightGrating'
        
        # 根据前门/后门选择不同的参数段
        front_or_back = self.get_front_or_back()
        if front_or_back == 1:
            param_section = f'G45_Channel_{channel_num}'
        else:
            param_section = f'G48_Channel_{channel_num}'
        
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
            x1_ymax_avg=self.config.getfloat(param_section, 'X1_YMAX_AVG'),
            x1_ymin_avg=self.config.getfloat(param_section, 'X1_YMIN_AVG'),
            x1_halarm_avg=self.config.getfloat(param_section, 'X1_Halarm_AVG'),
            x1_lalarm_avg=self.config.getfloat(param_section, 'X1_Lalarm_AVG'),
            x1_base_avg=self.config.getfloat(param_section, 'X1_Base_AVG'),
            x2_ymax_avg=self.config.getfloat(param_section, 'X2_YMAX_AVG', fallback=0.0),
            x2_ymin_avg=self.config.getfloat(param_section, 'X2_YMIN_AVG', fallback=0.0),
            t_ymax_avg=self.config.getfloat(param_section, 'T_YMAX_AVG', fallback=0.0),
            t_ymin_avg=self.config.getfloat(param_section, 'T_YMIN_AVG', fallback=0.0)
        )
    
    def get_cpk_limits(self, channel_num: int) -> CPKLimits:
        front_or_back = self.get_front_or_back()
        if front_or_back == 1:
            section = f'G45_Channel_{channel_num}CPK'
        else:
            section = f'G48_Channel_{channel_num}CPK'
            
        return CPKLimits(
            x1_max=self.config.getfloat(section, 'X1_MAX'),
            x1_min=self.config.getfloat(section, 'X1_MIN'),
            x2_max=self.config.getfloat(section, 'X2_MAX', fallback=0.0),
            x2_min=self.config.getfloat(section, 'X2_MIN', fallback=0.0),
            t_max=self.config.getfloat(section, 'T_MAX', fallback=0.0),
            t_min=self.config.getfloat(section, 'T_MIN', fallback=0.0)
        )

class ModbusCommunication:
    def __init__(self, com_settings: Dict):
        self.port = com_settings['port']
        self.baud = com_settings['baud']
        self.debug = com_settings['debug']
        self.pre_send_delay = com_settings['pre_send_delay']
        self.pre_receive_delay = com_settings['pre_receive_delay']
        self.serial_conn: Optional[serial.Serial] = None
        
    def initialize_serial(self) -> bool:
        try:
            self.serial_conn = serial.Serial(
                port=f'COM{self.port}',
                baudrate=self.baud,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1.0
            )
            if self.debug:
                logging.info(f"Serial port COM{self.port} initialized at {self.baud} baud")
            return True
        except Exception as e:
            logging.error(f"Serial initialization failed: {e}")
            return False
    
    def read_holding_registers(self, slave_addr: int, reg_addr: int, reg_count: int) -> Optional[List[int]]:
        """读取保持寄存器 (Modbus功能码0x03)"""
        if not self.serial_conn:
            return None
            
        # 构建Modbus RTU命令
        command = bytearray([
            slave_addr,  # 从机地址
            0x03,        # 功能码：读保持寄存器
            (reg_addr >> 8) & 0xFF,  # 起始地址高字节
            reg_addr & 0xFF,         # 起始地址低字节
            (reg_count >> 8) & 0xFF, # 寄存器数量高字节
            reg_count & 0xFF         # 寄存器数量低字节
        ])
        
        # 计算并添加CRC
        crc = self._calculate_crc16(command)
        command.extend(crc.to_bytes(2, 'little'))
        
        try:
            # 发送前延时
            if self.pre_send_delay > 0:
                time.sleep(self.pre_send_delay / 1000.0)
                
            self.serial_conn.write(command)
            
            if self.debug:
                logging.debug(f"Sent: {' '.join(f'{b:02X}' for b in command)}")
            
            # 接收前延时
            if self.pre_receive_delay > 0:
                time.sleep(self.pre_receive_delay / 1000.0)
            
            # 读取响应
            response = self.serial_conn.read(5 + reg_count * 2)  # 头部5字节 + 数据 + CRC2字节
            
            if len(response) < 5:
                return None
                
            if self.debug:
                logging.debug(f"Received: {' '.join(f'{b:02X}' for b in response)}")
            
            # 解析响应
            if response[0] == slave_addr and response[1] == 0x03:
                byte_count = response[2]
                if len(response) >= 5 + byte_count:
                    # 提取寄存器值
                    registers = []
                    for i in range(0, byte_count, 2):
                        reg_value = (response[3 + i] << 8) | response[3 + i + 1]
                        registers.append(reg_value)
                    return registers
                    
        except Exception as e:
            logging.error(f"Modbus communication error: {e}")
            
        return None
    
    def _calculate_crc16(self, data: bytearray) -> int:
        """计算Modbus CRC16"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

class GratingChannel:
    def __init__(self, channel_num: int, config: ChannelConfig, comm: ModbusCommunication):
        self.channel_num = channel_num
        self.config = config
        self.comm = comm
        self.measurements = []
        self.max_measurements = 1000
        
    def read_grating_data(self) -> Optional[Tuple[float, float, float]]:
        """读取光栅数据，返回 (X1, X2, T) 测量值"""
        # 读取左光栅
        left_data = self.comm.read_holding_registers(
            self.config.left_grating.slave_address,
            self.config.left_grating.reg_address,
            self.config.left_grating.reg_count
        )
        
        # 读取右光栅
        right_data = self.comm.read_holding_registers(
            self.config.right_grating.slave_address,
            self.config.right_grating.reg_address,
            self.config.right_grating.reg_count
        )
        
        if left_data and right_data and len(left_data) >= 2 and len(right_data) >= 2:
            # 根据原程序逻辑处理数据
            x1_value = self._process_measurement_data(left_data[0], right_data[0])
            x2_value = self._process_measurement_data(left_data[1], right_data[1]) if len(left_data) > 1 else 0.0
            t_value = x1_value + x2_value  # 总厚度
            
            measurement = (x1_value, x2_value, t_value)
            
            # 保存测量数据
            self.measurements.append(measurement)
            if len(self.measurements) > self.max_measurements:
                self.measurements.pop(0)
                
            return measurement
            
        return None
    
    def _process_measurement_data(self, left_raw: int, right_raw: int) -> float:
        """处理原始光栅数据，转换为实际测量值"""
        # 这里需要根据实际的光栅测量原理进行计算
        # 简化处理：假设原始数据需要进行线性转换
        left_value = left_raw * 0.001  # 转换系数
        right_value = right_raw * 0.001
        
        # 计算差值或其他处理逻辑
        measurement = abs(left_value - right_value) + self.config.x1_base_avg
        return measurement
    
    def check_alarms(self, measurement: Tuple[float, float, float]) -> List[str]:
        """检查报警条件"""
        alarms = []
        x1, x2, t = measurement
        
        if x1 > self.config.x1_halarm_avg:
            alarms.append(f"Channel {self.channel_num} X1 High Alarm: {x1:.2f} > {self.config.x1_halarm_avg:.2f}")
        elif x1 < self.config.x1_lalarm_avg:
            alarms.append(f"Channel {self.channel_num} X1 Low Alarm: {x1:.2f} < {self.config.x1_lalarm_avg:.2f}")
            
        return alarms
    
    def calculate_cpk(self, cpk_limits: CPKLimits) -> Dict[str, float]:
        """计算CPK值"""
        if len(self.measurements) < 10:  # 需要足够的数据点
            return {}
            
        # 提取最近的测量数据
        recent_data = self.measurements[-100:]  # 最近100个数据点
        x1_values = [m[0] for m in recent_data]
        
        # 计算统计参数
        mean = np.mean(x1_values)
        std = np.std(x1_values, ddof=1)
        
        if std == 0:
            return {}
            
        # 计算CPK
        usl = cpk_limits.x1_max  # 上规格限
        lsl = cpk_limits.x1_min  # 下规格限
        
        cpu = (usl - mean) / (3 * std)  # 上CPK
        cpl = (mean - lsl) / (3 * std)  # 下CPK
        cpk = min(cpu, cpl)  # 总CPK
        
        return {
            'mean': mean,
            'std': std,
            'cpu': cpu,
            'cpl': cpl,
            'cpk': cpk
        }

class OpticalGratingSystem(QObject):
    measurement_updated = pyqtSignal(int, tuple)  # channel_num, (x1, x2, t)
    alarm_triggered = pyqtSignal(str)  # alarm message
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.comm = ModbusCommunication(self.config_manager.get_com_settings())
        self.channels: Dict[int, GratingChannel] = {}
        self.cpk_limits: Dict[int, CPKLimits] = {}
        self.running = False
        self.measurement_timer = QTimer()
        self.measurement_timer.timeout.connect(self._measurement_cycle)
        
    def initialize(self) -> bool:
        """初始化系统"""
        # 初始化通信
        if not self.comm.initialize_serial():
            return False
            
        # 加载通道配置
        for i in range(1, 6):  # 5个通道
            try:
                channel_config = self.config_manager.get_channel_config(i)
                self.channels[i] = GratingChannel(i, channel_config, self.comm)
                self.cpk_limits[i] = self.config_manager.get_cpk_limits(i)
                logging.info(f"Channel {i} initialized")
            except Exception as e:
                logging.warning(f"Failed to load channel {i} config: {e}")
                
        return True
    
    def start_measurement(self):
        """开始测量"""
        if not self.running:
            self.running = True
            # 根据配置设置测量间隔
            display_settings = self.config_manager.get_round_display_settings()
            interval = display_settings['read_slave_interval']
            self.measurement_timer.start(interval)  # 毫秒
            logging.info("Measurement started")
    
    def stop_measurement(self):
        """停止测量"""
        self.running = False
        self.measurement_timer.stop()
        logging.info("Measurement stopped")
    
    def _measurement_cycle(self):
        """测量循环"""
        for channel_num, channel in self.channels.items():
            measurement = channel.read_grating_data()
            if measurement:
                # 发送测量更新信号
                self.measurement_updated.emit(channel_num, measurement)
                
                # 检查报警
                alarms = channel.check_alarms(measurement)
                for alarm in alarms:
                    self.alarm_triggered.emit(alarm)
                    logging.warning(alarm)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.system = OpticalGratingSystem()
        self.charts = {}
        self.series = {}
        self.init_ui()
        self.connect_signals()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("光栅测量系统 - Optical Grating Measuring System")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始测量")
        self.stop_button = QPushButton("停止测量")
        self.start_button.clicked.connect(self.start_measurement)
        self.stop_button.clicked.connect(self.stop_measurement)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)
        
        # 创建图表
        for i in range(1, 6):
            chart = QChart()
            chart.setTitle(f"通道 {i} 测量数据")
            
            series = QLineSeries()
            series.setName(f"Channel {i}")
            chart.addSeries(series)
            
            # 设置坐标轴
            axis_x = QValueAxis()
            axis_x.setTitleText("时间")
            axis_y = QValueAxis()
            axis_y.setTitleText("测量值")
            
            # 修复：使用正确的Qt常量
            chart.addAxis(axis_x, Qt.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignLeft)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)
            
            chart_view = QChartView(chart)
            chart_view.setRenderHint(QPainter.Antialiasing)
            
            self.charts[i] = chart
            self.series[i] = series
            layout.addWidget(chart_view)
    
    def connect_signals(self):
        """连接信号"""
        self.system.measurement_updated.connect(self.update_chart)
        self.system.alarm_triggered.connect(self.show_alarm)
    
    def start_measurement(self):
        """开始测量"""
        if self.system.initialize():
            self.system.start_measurement()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            logging.error("System initialization failed")
    
    def stop_measurement(self):
        """停止测量"""
        self.system.stop_measurement()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def update_chart(self, channel_num: int, measurement: tuple):
        """更新图表"""
        if channel_num in self.series:
            series = self.series[channel_num]
            x1, x2, t = measurement
            
            # 添加数据点（使用当前时间作为X轴）
            current_time = time.time()
            series.append(current_time, x1)
            
            # 限制数据点数量
            if series.count() > 100:
                series.remove(0)
    
    def show_alarm(self, message: str):
        """显示报警"""
        logging.warning(f"ALARM: {message}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    app = QApplication([])
    window = MainWindow()
    window.show()
    
    app.exec_()
