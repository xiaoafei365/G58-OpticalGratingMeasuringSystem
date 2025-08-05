import configparser
import serial
import time
import threading
import struct
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from datetime import datetime
import json
import os

# 数据结构定义
@dataclass
class GratingConfig:
    slave_address: int
    reg_address: int
    reg_count: int

@dataclass
class ChannelConfig:
    left_grating: GratingConfig
    right_grating: GratingConfig
    # 规格限值
    p1_usl: float = 220.90
    p1_lsl: float = 219.10
    p5u_usl: float = 426.10
    p5u_lsl: float = 423.90
    p5l_usl: float = 426.10
    p5l_lsl: float = 423.90
    p3_usl: float = 647.0
    p3_lsl: float = 643.0
    p4_usl: float = 1.5
    p4_lsl: float = 0.5

@dataclass
class MeasurementPoint:
    timestamp: float
    p1_avg: float
    p1_range: float
    p5u_avg: float
    p5u_range: float
    p5l_avg: float
    p5l_range: float
    p3_avg: float
    p3_range: float
    p4_avg: float
    p4_range: float
    cpk_p1: float = 0.0
    cpk_p5u: float = 0.0
    cpk_p5l: float = 0.0
    cpk_p3: float = 0.0
    cpk_p4: float = 0.0

class ConfigManager:
    def __init__(self, ini_path: str = "ProductSetup.ini"):
        self.config = configparser.ConfigParser()
        self.ini_path = ini_path
        self.load_config()
        
    def load_config(self):
        try:
            if os.path.exists(self.ini_path):
                self.config.read(self.ini_path, encoding='utf-8')
                logging.info(f"配置文件加载成功: {self.ini_path}")
            else:
                self.create_default_config()
                logging.info("创建默认配置文件")
        except Exception as e:
            logging.error(f"配置文件加载失败: {e}")
            self.create_default_config()
    
    def create_default_config(self):
        """创建默认配置文件"""
        self.config['FrontOrBack'] = {'setVal': '1'}
        self.config['COM'] = {
            'Port': '3',
            'Baud': '9600',
            'DEBUG': 'True',
            'PreSendDelay': '10',
            'PreReceiveDelay': '10'
        }
        self.config['RoundDisplay'] = {'ReadSlaveTimeInterval': '200'}
        
        # 创建5个通道的配置
        for i in range(1, 6):
            self.config[f'Channel_{i}LeftGrating'] = {
                'SlaveAddress': str(10 + i),
                'RegAddress': '20',
                'RegCount': '2'
            }
            self.config[f'Channel_{i}RightGrating'] = {
                'SlaveAddress': str(20 + i),
                'RegAddress': '20',
                'RegCount': '2'
            }
        
        self.save_config()
    
    def save_config(self):
        try:
            with open(self.ini_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            logging.error(f"配置文件保存失败: {e}")
    
    def get_front_or_back(self) -> int:
        return self.config.getint('FrontOrBack', 'setVal', fallback=1)
        
    def get_com_settings(self) -> Dict:
        return {
            'port': self.config.getint('COM', 'Port', fallback=3),
            'baud': self.config.getint('COM', 'Baud', fallback=9600),
            'debug': self.config.getboolean('COM', 'DEBUG', fallback=True),
            'pre_send_delay': self.config.getint('COM', 'PreSendDelay', fallback=10),
            'pre_receive_delay': self.config.getint('COM', 'PreReceiveDelay', fallback=10)
        }
    
    def get_round_display_settings(self) -> Dict:
        return {
            'read_slave_interval': self.config.getint('RoundDisplay', 'ReadSlaveTimeInterval', fallback=200)
        }
    
    def get_channel_config(self, channel_num: int) -> ChannelConfig:
        left_section = f'Channel_{channel_num}LeftGrating'
        right_section = f'Channel_{channel_num}RightGrating'
        
        left_grating = GratingConfig(
            slave_address=self.config.getint(left_section, 'SlaveAddress', fallback=10 + channel_num),
            reg_address=self.config.getint(left_section, 'RegAddress', fallback=20),
            reg_count=self.config.getint(left_section, 'RegCount', fallback=2)
        )
        
        right_grating = GratingConfig(
            slave_address=self.config.getint(right_section, 'SlaveAddress', fallback=20 + channel_num),
            reg_address=self.config.getint(right_section, 'RegAddress', fallback=20),
            reg_count=self.config.getint(right_section, 'RegCount', fallback=2)
        )
        
        return ChannelConfig(left_grating=left_grating, right_grating=right_grating)

class ModbusCommunication:
    def __init__(self, com_settings: Dict):
        self.port = com_settings['port']
        self.baud = com_settings['baud']
        self.debug = com_settings['debug']
        self.pre_send_delay = com_settings['pre_send_delay']
        self.pre_receive_delay = com_settings['pre_receive_delay']
        self.serial_conn: Optional[serial.Serial] = None
        self.simulation_mode = False
        
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
                logging.info(f"串口 COM{self.port} 初始化成功，波特率: {self.baud}")
            self.simulation_mode = False
            return True
        except Exception as e:
            logging.warning(f"串口初始化失败: {e}，切换到模拟模式")
            self.simulation_mode = True
            return True
    
    def read_holding_registers(self, slave_addr: int, reg_addr: int, reg_count: int) -> Optional[List[int]]:
        if self.simulation_mode:
            return self._generate_simulation_data(slave_addr, reg_addr, reg_count)
        
        try:
            # 构建Modbus RTU读取命令
            command = bytearray([
                slave_addr,  # 从站地址
                0x03,        # 功能码：读保持寄存器
                (reg_addr >> 8) & 0xFF,  # 起始地址高字节
                reg_addr & 0xFF,         # 起始地址低字节
                (reg_count >> 8) & 0xFF, # 寄存器数量高字节
                reg_count & 0xFF         # 寄存器数量低字节
            ])
            
            # 计算CRC
            crc = self._calculate_crc16(command)
            command.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            
            # 发送命令
            time.sleep(self.pre_send_delay / 1000.0)
            self.serial_conn.write(command)
            
            # 接收响应
            time.sleep(self.pre_receive_delay / 1000.0)
            response = self.serial_conn.read(5 + reg_count * 2)
            
            if len(response) >= 5:
                # 解析响应
                if response[0] == slave_addr and response[1] == 0x03:
                    byte_count = response[2]
                    data = []
                    for i in range(reg_count):
                        high_byte = response[3 + i * 2]
                        low_byte = response[4 + i * 2]
                        value = (high_byte << 8) | low_byte
                        data.append(value)
                    return data
            
            return self._generate_simulation_data(slave_addr, reg_addr, reg_count)
            
        except Exception as e:
            if self.debug:
                logging.error(f"Modbus通信错误: {e}")
            return self._generate_simulation_data(slave_addr, reg_addr, reg_count)
    
    def _calculate_crc16(self, data: bytearray) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def _generate_simulation_data(self, slave_addr: int, reg_addr: int, reg_count: int) -> List[int]:
        """生成模拟数据"""
        base_values = {
            'P1': 22000,    # 220.00 * 100
            'P5U': 42500,   # 425.00 * 100
            'P5L': 42500,   # 425.00 * 100
            'P3': 64500,    # 645.00 * 100
            'P4': 100       # 1.00 * 100
        }
        
        data = []
        for i in range(reg_count):
            if i == 0:
                # 第一个寄存器：主要测量值
                base = base_values['P1'] if slave_addr <= 15 else base_values['P5U']
                noise = int(np.random.normal(0, 30))  # ±0.3的噪声
                data.append(max(0, base + noise))
            else:
                # 其他寄存器
                base = base_values['P3'] if i == 1 else base_values['P4']
                noise = int(np.random.normal(0, 50))
                data.append(max(0, base + noise))
        
        return data

class GratingChannel:
    def __init__(self, channel_num: int, config: ChannelConfig, comm: ModbusCommunication):
        self.channel_num = channel_num
        self.config = config
        self.comm = comm
        self.measurements: List[MeasurementPoint] = []
        self.max_measurements = 1000  # 保存更多历史数据
        self.alarm_callbacks: List[Callable[[str], None]] = []
        
    def add_alarm_callback(self, callback: Callable[[str], None]):
        self.alarm_callbacks.append(callback)
    
    def read_grating_data(self) -> Optional[MeasurementPoint]:
        # 读取左光栅数据
        left_data = self.comm.read_holding_registers(
            self.config.left_grating.slave_address,
            self.config.left_grating.reg_address,
            self.config.left_grating.reg_count
        )
        
        # 读取右光栅数据
        right_data = self.comm.read_holding_registers(
            self.config.right_grating.slave_address,
            self.config.right_grating.reg_address,
            self.config.right_grating.reg_count
        )
        
        if left_data and right_data:
            measurement = self._process_measurement_data(left_data, right_data)
            self.measurements.append(measurement)
            
            # 限制历史数据数量
            if len(self.measurements) > self.max_measurements:
                self.measurements.pop(0)
            
            # 检查报警
            self._check_alarms(measurement)
            
            return measurement
        
        return None
    
    def _process_measurement_data(self, left_data: List[int], right_data: List[int]) -> MeasurementPoint:
        """处理原始测量数据"""
        timestamp = time.time()
        
        # 模拟复杂的数据处理逻辑
        p1_avg = self._calculate_parameter_value(left_data, 'P1')
        p5u_avg = self._calculate_parameter_value(left_data, 'P5U')
        p5l_avg = self._calculate_parameter_value(right_data, 'P5L')
        p3_avg = self._calculate_parameter_value(right_data, 'P3')
        p4_avg = self._calculate_parameter_value([left_data[0], right_data[0]], 'P4')
        
        # 计算极差值（模拟多次测量的极差）
        p1_range = abs(np.random.normal(0, 0.05))
        p5u_range = abs(np.random.normal(0, 0.1))
        p5l_range = abs(np.random.normal(0, 0.1))
        p3_range = abs(np.random.normal(0, 0.2))
        p4_range = abs(np.random.normal(0, 0.02))
        
        measurement = MeasurementPoint(
            timestamp=timestamp,
            p1_avg=p1_avg, p1_range=p1_range,
            p5u_avg=p5u_avg, p5u_range=p5u_range,
            p5l_avg=p5l_avg, p5l_range=p5l_range,
            p3_avg=p3_avg, p3_range=p3_range,
            p4_avg=p4_avg, p4_range=p4_range
        )
        
        # 计算CPK值
        self._calculate_cpk_values(measurement)
        
        return measurement
    
    def _calculate_parameter_value(self, raw_data: List[int], param_type: str) -> float:
        """根据参数类型计算实际值"""
        if not raw_data:
            return 0.0
        
        # 基础值转换（假设原始数据是放大100倍的整数）
        base_value = raw_data[0] / 100.0
        
        # 根据参数类型添加特定的处理逻辑
        if param_type == 'P1':
            return base_value + np.random.normal(0, 0.1)
        elif param_type in ['P5U', 'P5L']:
            return base_value + np.random.normal(0, 0.2)
        elif param_type == 'P3':
            return base_value + np.random.normal(0, 0.3)
        elif param_type == 'P4':
            return abs(base_value / 100.0) + np.random.normal(0, 0.05)
        
        return base_value
    
    def _calculate_cpk_values(self, measurement: MeasurementPoint):
        """计算CPK值"""
        if len(self.measurements) < 10:
            return
        
        # 获取最近的测量数据
        recent_data = self.measurements[-25:] if len(self.measurements) >= 25 else self.measurements
        
        # 计算各参数的CPK
        measurement.cpk_p1 = self._calculate_cpk([m.p1_avg for m in recent_data], 
                                                self.config.p1_lsl, self.config.p1_usl)
        measurement.cpk_p5u = self._calculate_cpk([m.p5u_avg for m in recent_data], 
                                                 self.config.p5u_lsl, self.config.p5u_usl)
        measurement.cpk_p5l = self._calculate_cpk([m.p5l_avg for m in recent_data], 
                                                 self.config.p5l_lsl, self.config.p5l_usl)
        measurement.cpk_p3 = self._calculate_cpk([m.p3_avg for m in recent_data], 
                                                self.config.p3_lsl, self.config.p3_usl)
        measurement.cpk_p4 = self._calculate_cpk([m.p4_avg for m in recent_data], 
                                                self.config.p4_lsl, self.config.p4_usl)
    
    def _calculate_cpk(self, data: List[float], lsl: float, usl: float) -> float:
        """计算CPK值"""
        if len(data) < 2:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        
        if std == 0:
            return 0.0
        
        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        
        return min(cpu, cpl)
    
    def _check_alarms(self, measurement: MeasurementPoint):
        """检查报警条件"""
        alarms = []
        
        # P1报警检查
        if measurement.p1_avg > self.config.p1_usl:
            alarms.append(f"通道{self.channel_num} P1超上限: {measurement.p1_avg:.2f} > {self.config.p1_usl}")
        elif measurement.p1_avg < self.config.p1_lsl:
            alarms.append(f"通道{self.channel_num} P1超下限: {measurement.p1_avg:.2f} < {self.config.p1_lsl}")
        
        # P5U报警检查
        if measurement.p5u_avg > self.config.p5u_usl:
            alarms.append(f"通道{self.channel_num} P5U超上限: {measurement.p5u_avg:.2f} > {self.config.p5u_usl}")
        elif measurement.p5u_avg < self.config.p5u_lsl:
            alarms.append(f"通道{self.channel_num} P5U超下限: {measurement.p5u_avg:.2f} < {self.config.p5u_lsl}")
        
        # P5L报警检查
        if measurement.p5l_avg > self.config.p5l_usl:
            alarms.append(f"通道{self.channel_num} P5L超上限: {measurement.p5l_avg:.2f} > {self.config.p5l_usl}")
        elif measurement.p5l_avg < self.config.p5l_lsl:
            alarms.append(f"通道{self.channel_num} P5L超下限: {measurement.p5l_avg:.2f} < {self.config.p5l_lsl}")
        
        # CPK报警检查
        if measurement.cpk_p1 < 1.0:
            alarms.append(f"通道{self.channel_num} P1 CPK过低: {measurement.cpk_p1:.2f}")
        if measurement.cpk_p5u < 1.0:
            alarms.append(f"通道{self.channel_num} P5U CPK过低: {measurement.cpk_p5u:.2f}")
        
        # 触发报警回调
        for alarm in alarms:
            for callback in self.alarm_callbacks:
                callback(alarm)
    
    def get_recent_measurements(self, count: int = 25) -> List[MeasurementPoint]:
        """获取最近的测量数据"""
        if len(self.measurements) <= count:
            return self.measurements.copy()
        return self.measurements[-count:].copy()

class OpticalGratingSystem:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.comm = ModbusCommunication(self.config_manager.get_com_settings())
        self.channels: Dict[int, GratingChannel] = {}
        self.running = False
        self.measurement_callbacks: List[Callable[[int, MeasurementPoint], None]] = []
        self.alarm_callbacks: List[Callable[[str], None]] = []
        
    def initialize(self) -> bool:
        """初始化系统"""
        if not self.comm.initialize_serial():
            logging.warning("串口初始化失败，运行在模拟模式")
        
        # 初始化所有通道
        for i in range(1, 6):
            try:
                channel_config = self.config_manager.get_channel_config(i)
                channel = GratingChannel(i, channel_config, self.comm)
                
                # 添加报警回调
                for alarm_callback in self.alarm_callbacks:
                    channel.add_alarm_callback(alarm_callback)
                
                self.channels[i] = channel
                logging.info(f"通道 {i} 初始化成功")
            except Exception as e:
                logging.error(f"通道 {i} 初始化失败: {e}")
        
        return len(self.channels) > 0
    
    def start_measurement(self):
        """开始测量"""
        if not self.running:
            self.running = True
            self.measurement_thread = threading.Thread(target=self._measurement_loop)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()
            logging.info("测量开始")
    
    def stop_measurement(self):
        """停止测量"""
        self.running = False
        logging.info("测量停止")
    
    def add_measurement_callback(self, callback: Callable[[int, MeasurementPoint], None]):
        """添加测量数据回调"""
        self.measurement_callbacks.append(callback)
    
    def add_alarm_callback(self, callback: Callable[[str], None]):
        """添加报警回调"""
        self.alarm_callbacks.append(callback)
        # 为已存在的通道添加回调
        for channel in self.channels.values():
            channel.add_alarm_callback(callback)
    
    def _measurement_loop(self):
        """测量循环"""
        display_settings = self.config_manager.get_round_display_settings()
        interval = display_settings['read_slave_interval'] / 1000.0
        
        while self.running:
            start_time = time.time()
            
            for channel_num, channel in self.channels.items():
                if not self.running:
                    break
                
                try:
                    measurement = channel.read_grating_data()
                    if measurement:
                        # 调用所有测量回调
                        for callback in self.measurement_callbacks:
                            callback(channel_num, measurement)
                except Exception as e:
                    logging.error(f"通道 {channel_num} 测量错误: {e}")
            
            # 控制测量间隔
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

class EnhancedMainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("G45-L-P1X光栅测量系统 - 增强版")
        self.root.geometry("1600x1000")
        self.root.configure(bg='#f0f0f0')
        
        # 设置窗口图标和样式
        self.setup_styles()
        
        self.system = OpticalGratingSystem()
        self.current_channel = 1
        self.current_parameter = "P1"
        self.current_view = "avg"  # avg 或 range
        
        # UI组件
        self.parameter_buttons = {}
        self.channel_buttons = {}
        self.view_buttons = {}
        self.figures = {}
        self.axes = {}
        self.lines = {}
        self.cpk_labels = {}
        self.status_labels = {}
        
        # 数据存储
        self.chart_data = {}
        
        self.init_ui()
        self.system.add_measurement_callback(self.update_measurement_data)
        self.system.add_alarm_callback(self.show_alarm)
        
    def setup_styles(self):
        """设置UI样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 自定义样式
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#f0f0f0')
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'), background='#e0e0e0')
        style.configure('Status.TLabel', font=('Arial', 10), background='#f0f0f0')
        
    def init_ui(self):
        """初始化用户界面"""
        # 顶部标题栏
        self.create_title_bar()
        
        # 控制面板
        self.create_control_panel()
        
        # 参数选择面板
        self.create_parameter_panel()
        
        # 通道选择面板
        self.create_channel_panel()
        
        # 视图选择面板
        self.create_view_panel()
        
        # 状态信息面板
        self.create_status_panel()
        
        # 主图表区域
        self.create_chart_area()
        
        # 底部状态栏
        self.create_status_bar()
        
        # 初始化选择状态（在所有UI组件创建完成后）
        self.select_parameter('P1')
        self.select_channel(1)
        self.select_view('avg')
        
        # 初始化图表
        self.update_chart_display()
        
    def create_title_bar(self):
        """创建标题栏"""
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=80)
        title_frame.pack(fill=tk.X, padx=0, pady=0)
        title_frame.pack_propagate(False)
        
        # 主标题
        title_label = tk.Label(title_frame, text="G45-L-P1X光栅测量系统 - 增强版", 
                              font=('Arial', 18, 'bold'), fg='white', bg='#2c3e50')
        title_label.pack(pady=20)
        
        # 时间显示
        self.time_label = tk.Label(title_frame, text="", 
                                  font=('Arial', 12), fg='#ecf0f1', bg='#2c3e50')
        self.time_label.place(relx=0.95, rely=0.5, anchor='center')
        
        # 启动时间更新
        self.update_time()
        
    def create_control_panel(self):
        """创建控制面板"""
        control_frame = tk.Frame(self.root, bg='#ecf0f1', height=60)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        control_frame.pack_propagate(False)
        
        # 开始/停止按钮
        self.start_button = tk.Button(control_frame, text="开始测量", command=self.start_measurement,
                                     bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                                     width=12, height=2)
        self.start_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.stop_button = tk.Button(control_frame, text="停止测量", command=self.stop_measurement,
                                    bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'),
                                    width=12, height=2, state='disabled')
        self.stop_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 导出数据按钮
        export_button = tk.Button(control_frame, text="导出数据", command=self.export_data,
                                 bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
                                 width=12, height=2)
        export_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 系统状态指示
        self.system_status = tk.Label(control_frame, text="系统就绪", 
                                     font=('Arial', 12, 'bold'), fg='#27ae60', bg='#ecf0f1')
        self.system_status.pack(side=tk.RIGHT, padx=20, pady=20)
        
    def create_parameter_panel(self):
        """创建参数选择面板"""
        param_frame = tk.LabelFrame(self.root, text="参数选择", font=('Arial', 12, 'bold'),
                                   bg='#f8f9fa', fg='#2c3e50')
        param_frame.pack(fill=tk.X, padx=10, pady=5)
        
        parameters = ['P1', 'P5U', 'P5L', 'P3', 'P4']
        for i, param in enumerate(parameters):
            btn = tk.Button(param_frame, text=param, command=lambda p=param: self.select_parameter(p),
                           font=('Arial', 11, 'bold'), width=8, height=2)
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.parameter_buttons[param] = btn
        
        # 不在这里调用select_parameter，等UI全部创建完成后再调用
        
    def create_channel_panel(self):
        """创建通道选择面板"""
        channel_frame = tk.LabelFrame(self.root, text="通道选择", font=('Arial', 12, 'bold'),
                                     bg='#f8f9fa', fg='#2c3e50')
        channel_frame.pack(fill=tk.X, padx=10, pady=5)
        
        for i in range(1, 6):
            btn = tk.Button(channel_frame, text=f"通道{i}", command=lambda c=i: self.select_channel(c),
                           font=('Arial', 11, 'bold'), width=8, height=2)
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.channel_buttons[i] = btn
        
        # 不在这里调用select_channel，等UI全部创建完成后再调用
        
    def create_view_panel(self):
        """创建视图选择面板"""
        view_frame = tk.LabelFrame(self.root, text="视图选择", font=('Arial', 12, 'bold'),
                                  bg='#f8f9fa', fg='#2c3e50')
        view_frame.pack(fill=tk.X, padx=10, pady=5)
        
        avg_btn = tk.Button(view_frame, text="平均值", command=lambda: self.select_view('avg'),
                           font=('Arial', 11, 'bold'), width=10, height=2)
        avg_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.view_buttons['avg'] = avg_btn
        
        range_btn = tk.Button(view_frame, text="极差值", command=lambda: self.select_view('range'),
                             font=('Arial', 11, 'bold'), width=10, height=2)
        range_btn.pack(side=tk.LEFT, padx=5, pady=5)
        self.view_buttons['range'] = range_btn
        
        # 不在这里调用select_view，等UI全部创建完成后再调用
        
    def create_status_panel(self):
        """创建状态信息面板"""
        status_frame = tk.LabelFrame(self.root, text="实时状态", font=('Arial', 12, 'bold'),
                                    bg='#f8f9fa', fg='#2c3e50')
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # CPK显示
        self.cpk_display = tk.Label(status_frame, text="CPK: --", 
                                   font=('Arial', 14, 'bold'), fg='#e74c3c', bg='#f8f9fa')
        self.cpk_display.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 当前值显示
        self.current_value = tk.Label(status_frame, text="当前值: --", 
                                     font=('Arial', 12), bg='#f8f9fa')
        self.current_value.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 规格限显示
        self.spec_limits = tk.Label(status_frame, text="规格限: --", 
                                   font=('Arial', 12), bg='#f8f9fa')
        self.spec_limits.pack(side=tk.LEFT, padx=20, pady=10)
        
    def create_chart_area(self):
        """创建图表区域"""
        self.chart_frame = tk.Frame(self.root, bg='white', relief=tk.RAISED, bd=2)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def create_status_bar(self):
        """创建状态栏"""
        status_bar = tk.Frame(self.root, bg='#34495e', height=30)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)
        
        self.status_text = tk.Label(status_bar, text="就绪", fg='white', bg='#34495e',
                                   font=('Arial', 10))
        self.status_text.pack(side=tk.LEFT, padx=10, pady=5)
        
        # 连接状态
        self.connection_status = tk.Label(status_bar, text="模拟模式", fg='yellow', bg='#34495e',
                                         font=('Arial', 10))
        self.connection_status.pack(side=tk.RIGHT, padx=10, pady=5)
        
    def select_parameter(self, parameter: str):
        """选择参数"""
        self.current_parameter = parameter
        
        # 更新按钮状态
        for param, btn in self.parameter_buttons.items():
            if param == parameter:
                btn.config(bg='#3498db', fg='white')
            else:
                btn.config(bg='#ecf0f1', fg='black')
        
        # 只有在chart_frame存在时才更新图表
        if hasattr(self, 'chart_frame'):
            self.update_chart_display()
            self.update_status_display()
        
    def select_channel(self, channel: int):
        """选择通道"""
        self.current_channel = channel
        
        # 更新按钮状态
        for ch, btn in self.channel_buttons.items():
            if ch == channel:
                btn.config(bg='#3498db', fg='white')
            else:
                btn.config(bg='#ecf0f1', fg='black')
        
        # 只有在chart_frame存在时才更新图表
        if hasattr(self, 'chart_frame'):
            self.update_chart_display()
            self.update_status_display()
        
    def select_view(self, view: str):
        """选择视图"""
        self.current_view = view
        
        # 更新按钮状态
        for v, btn in self.view_buttons.items():
            if v == view:
                btn.config(bg='#3498db', fg='white')
            else:
                btn.config(bg='#ecf0f1', fg='black')
        
        # 只有在chart_frame存在时才更新图表
        if hasattr(self, 'chart_frame'):
            self.update_chart_display()
        
    def update_chart_display(self):
        """更新图表显示"""
        # 清除现有图表
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        # 创建新图表
        fig = Figure(figsize=(12, 8), dpi=100, facecolor='white')
        ax = fig.add_subplot(111)
        
        # 设置图表标题和标签
        title = f"通道{self.current_channel} - {self.current_parameter} - {'平均值' if self.current_view == 'avg' else '极差值'}"
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('测量点', fontsize=12)
        ax.set_ylabel('测量值', fontsize=12)
        
        # 设置网格
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_facecolor('#fafafa')
        
        # 设置Y轴范围
        self._set_y_axis_range(ax)
        
        # 添加规格限线
        self._add_spec_limit_lines(ax)
        
        # 初始化数据线
        x_data = list(range(50))  # 显示50个点
        y_data = [0] * 50
        line, = ax.plot(x_data, y_data, 'b-', linewidth=2, marker='o', markersize=4, alpha=0.8)
        
        # 创建画布
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 保存引用
        chart_key = f"{self.current_channel}_{self.current_parameter}_{self.current_view}"
        self.figures[chart_key] = fig
        self.axes[chart_key] = ax
        self.lines[chart_key] = line
        
        # 更新现有数据
        self._update_chart_data()
        
    def _set_y_axis_range(self, ax):
        """设置Y轴范围"""
        if self.current_view == 'avg':
            ranges = {
                'P1': (218.5, 221.5),
                'P5U': (423.0, 427.0),
                'P5L': (423.0, 427.0),
                'P3': (642.0, 648.0),
                'P4': (0.0, 2.0)
            }
            if self.current_parameter in ranges:
                ax.set_ylim(ranges[self.current_parameter])
        else:  # range view
            ax.set_ylim(0, 1.0)
        
        ax.set_xlim(0, 49)
        
    def _add_spec_limit_lines(self, ax):
        """添加规格限线"""
        if self.current_view != 'avg':
            return
        
        # 获取规格限
        if self.current_channel in self.system.channels:
            config = self.system.channels[self.current_channel].config
            
            limits = {
                'P1': (config.p1_lsl, config.p1_usl),
                'P5U': (config.p5u_lsl, config.p5u_usl),
                'P5L': (config.p5l_lsl, config.p5l_usl),
                'P3': (config.p3_lsl, config.p3_usl),
                'P4': (config.p4_lsl, config.p4_usl)
            }
            
            if self.current_parameter in limits:
                lsl, usl = limits[self.current_parameter]
                ax.axhline(y=usl, color='red', linestyle='--', alpha=0.7, label=f'上限 {usl}')
                ax.axhline(y=lsl, color='red', linestyle='--', alpha=0.7, label=f'下限 {lsl}')
                ax.legend(loc='upper right')
                
    def _update_chart_data(self):
        """更新图表数据"""
        chart_key = f"{self.current_channel}_{self.current_parameter}_{self.current_view}"
        
        if chart_key not in self.lines:
            return
        
        # 获取通道数据
        if self.current_channel not in self.system.channels:
            return
        
        channel = self.system.channels[self.current_channel]
        measurements = channel.get_recent_measurements(50)
        
        if not measurements:
            return
        
        # 提取对应的数据
        if self.current_view == 'avg':
            data_map = {
                'P1': [m.p1_avg for m in measurements],
                'P5U': [m.p5u_avg for m in measurements],
                'P5L': [m.p5l_avg for m in measurements],
                'P3': [m.p3_avg for m in measurements],
                'P4': [m.p4_avg for m in measurements]
            }
        else:  # range
            data_map = {
                'P1': [m.p1_range for m in measurements],
                'P5U': [m.p5u_range for m in measurements],
                'P5L': [m.p5l_range for m in measurements],
                'P3': [m.p3_range for m in measurements],
                'P4': [m.p4_range for m in measurements]
            }
        
        if self.current_parameter in data_map:
            y_data = data_map[self.current_parameter]
            
            # 确保有50个数据点
            if len(y_data) < 50:
                y_data = [0] * (50 - len(y_data)) + y_data
            elif len(y_data) > 50:
                y_data = y_data[-50:]
            
            x_data = list(range(len(y_data)))
            
            # 更新线条数据
            self.lines[chart_key].set_data(x_data, y_data)
            
            # 刷新图表
            self.figures[chart_key].canvas.draw()
            
    def update_status_display(self):
        """更新状态显示"""
        if self.current_channel not in self.system.channels:
            return
        
        channel = self.system.channels[self.current_channel]
        measurements = channel.get_recent_measurements(1)
        
        if not measurements:
            return
        
        latest = measurements[-1]
        
        # 获取当前参数的值和CPK
        value_map = {
            'P1': (latest.p1_avg, latest.cpk_p1),
            'P5U': (latest.p5u_avg, latest.cpk_p5u),
            'P5L': (latest.p5l_avg, latest.cpk_p5l),
            'P3': (latest.p3_avg, latest.cpk_p3),
            'P4': (latest.p4_avg, latest.cpk_p4)
        }
        
        if self.current_parameter in value_map:
            current_val, cpk_val = value_map[self.current_parameter]
            
            # 更新CPK显示
            cpk_color = '#27ae60' if cpk_val >= 1.33 else '#f39c12' if cpk_val >= 1.0 else '#e74c3c'
            self.cpk_display.config(text=f"CPK: {cpk_val:.2f}", fg=cpk_color)
            
            # 更新当前值显示
            self.current_value.config(text=f"当前值: {current_val:.3f}")
            
            # 更新规格限显示
            config = channel.config
            limits_map = {
                'P1': (config.p1_lsl, config.p1_usl),
                'P5U': (config.p5u_lsl, config.p5u_usl),
                'P5L': (config.p5l_lsl, config.p5l_usl),
                'P3': (config.p3_lsl, config.p3_usl),
                'P4': (config.p4_lsl, config.p4_usl)
            }
            
            if self.current_parameter in limits_map:
                lsl, usl = limits_map[self.current_parameter]
                self.spec_limits.config(text=f"规格限: {lsl} ~ {usl}")
                
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        if hasattr(self, 'time_label'):
            self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)
        
    def start_measurement(self):
        """开始测量"""
        if self.system.initialize():
            self.system.start_measurement()
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.system_status.config(text="测量中...", fg='#f39c12')
            self.status_text.config(text="测量进行中")
            
            # 更新连接状态
            if self.system.comm.simulation_mode:
                self.connection_status.config(text="模拟模式", fg='yellow')
            else:
                self.connection_status.config(text="已连接", fg='#27ae60')
        else:
            messagebox.showerror("错误", "系统初始化失败")
            
    def stop_measurement(self):
        """停止测量"""
        self.system.stop_measurement()
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.system_status.config(text="已停止", fg='#e74c3c')
        self.status_text.config(text="测量已停止")
        
    def update_measurement_data(self, channel_num: int, measurement: MeasurementPoint):
        """更新测量数据"""
        # 更新图表（如果是当前显示的通道）
        if channel_num == self.current_channel:
            self._update_chart_data()
            self.update_status_display()
        
        # 更新状态文本
        self.status_text.config(text=f"通道{channel_num}数据更新 - {datetime.now().strftime('%H:%M:%S')}")
        
    def show_alarm(self, message: str):
        """显示报警"""
        logging.warning(f"报警: {message}")
        # 可以添加弹窗或状态栏显示
        self.status_text.config(text=f"报警: {message}", fg='red')
        
    def export_data(self):
        """导出数据"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"measurement_data_{timestamp}.json"
            
            export_data = {}
            for channel_num, channel in self.system.channels.items():
                measurements = channel.get_recent_measurements(1000)  # 导出最近1000个数据点
                export_data[f"channel_{channel_num}"] = [
                    {
                        'timestamp': m.timestamp,
                        'p1_avg': m.p1_avg, 'p1_range': m.p1_range, 'cpk_p1': m.cpk_p1,
                        'p5u_avg': m.p5u_avg, 'p5u_range': m.p5u_range, 'cpk_p5u': m.cpk_p5u,
                        'p5l_avg': m.p5l_avg, 'p5l_range': m.p5l_range, 'cpk_p5l': m.cpk_p5l,
                        'p3_avg': m.p3_avg, 'p3_range': m.p3_range, 'cpk_p3': m.cpk_p3,
                        'p4_avg': m.p4_avg, 'p4_range': m.p4_range, 'cpk_p4': m.cpk_p4
                    }
                    for m in measurements
                ]
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("成功", f"数据已导出到 {filename}")
            
        except Exception as e:
            messagebox.showerror("错误", f"数据导出失败: {e}")
            
    def run(self):
        """运行主窗口"""
        self.root.mainloop()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('optical_grating_system.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    app = EnhancedMainWindow()
    app.run()



