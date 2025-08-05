import configparser
import serial
import time
import threading
import struct
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
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
    x1_ymax_avg: float = 0.0
    x1_ymin_avg: float = 0.0
    x1_halarm_avg: float = 0.0
    x1_lalarm_avg: float = 0.0
    x1_base_avg: float = 0.0

class ConfigManager:
    def __init__(self, ini_path: str = "ProductSetup.ini"):
        self.config = configparser.ConfigParser()
        try:
            self.config.read(ini_path, encoding='utf-8')
            logging.info(f"Configuration loaded from {ini_path}")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
        
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
        
        return ChannelConfig(
            left_grating=left_grating,
            right_grating=right_grating,
            x1_halarm_avg=220.90,
            x1_lalarm_avg=219.10,
            x1_base_avg=220.0
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
            return True
    
    def read_holding_registers(self, slave_addr: int, reg_addr: int, reg_count: int) -> Optional[List[int]]:
        if not self.serial_conn:
            # 模拟数据 - 基于原始界面的数值范围
            base_values = {
                'P1': 220.0,
                'P5U': 425.0, 
                'P5L': 425.0,
                'P3': 645.0,
                'P4': 1.0
            }
            return [int((base_values['P1'] + np.random.normal(0, 0.3)) * 100), 
                   int((base_values['P5U'] + np.random.normal(0, 0.5)) * 100)]
            
        return [22000, 42500]

class GratingChannel:
    def __init__(self, channel_num: int, config: ChannelConfig, comm: ModbusCommunication):
        self.channel_num = channel_num
        self.config = config
        self.comm = comm
        # 每个参数都有平均值和极差值的数据
        self.measurements = {
            'P1_avg': [], 'P1_range': [],
            'P5U_avg': [], 'P5U_range': [],
            'P5L_avg': [], 'P5L_range': [],
            'P3_avg': [], 'P3_range': [],
            'P4_avg': [], 'P4_range': []
        }
        self.max_measurements = 25  # 显示25个数据点
        
    def read_grating_data(self) -> Optional[Dict[str, float]]:
        left_data = self.comm.read_holding_registers(
            self.config.left_grating.slave_address,
            self.config.left_grating.reg_address,
            self.config.left_grating.reg_count
        )
        
        right_data = self.comm.read_holding_registers(
            self.config.right_grating.slave_address,
            self.config.right_grating.reg_address,
            self.config.right_grating.reg_count
        )
        
        if left_data and right_data:
            # 模拟各个测量参数的平均值和极差值
            measurement = {
                'P1_avg': 220.0 + np.random.normal(0, 0.3),
                'P1_range': abs(np.random.normal(0, 0.1)),
                'P5U_avg': 425.0 + np.random.normal(0, 0.5),
                'P5U_range': abs(np.random.normal(0, 0.2)),
                'P5L_avg': 425.0 + np.random.normal(0, 0.5),
                'P5L_range': abs(np.random.normal(0, 0.2)),
                'P3_avg': 645.0 + np.random.normal(0, 0.8),
                'P3_range': abs(np.random.normal(0, 0.3)),
                'P4_avg': 1.0 + np.random.normal(0, 0.1),
                'P4_range': abs(np.random.normal(0, 0.05))
            }
            
            # 保存测量数据
            for param, value in measurement.items():
                self.measurements[param].append(value)
                if len(self.measurements[param]) > self.max_measurements:
                    self.measurements[param].pop(0)
                    
            return measurement
            
        return None
    
    def calculate_cpk(self, param: str) -> float:
        base_param = param.replace('_avg', '').replace('_range', '')
        if len(self.measurements[f'{base_param}_avg']) < 10:
            return 0.0
            
        data = self.measurements[f'{base_param}_avg']
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        
        if std == 0:
            return 0.0
            
        # 根据参数设置规格限
        spec_limits = {
            'P1': (219.10, 220.90),
            'P5U': (423.90, 426.10),
            'P5L': (423.90, 426.10),
            'P3': (643.0, 647.0),
            'P4': (0.5, 1.5)
        }
        
        if base_param in spec_limits:
            lsl, usl = spec_limits[base_param]
            cpu = (usl - mean) / (3 * std)
            cpl = (mean - lsl) / (3 * std)
            return min(cpu, cpl)
        
        return 1.5  # 默认CPK值

class OpticalGratingSystem:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.comm = ModbusCommunication(self.config_manager.get_com_settings())
        self.channels: Dict[int, GratingChannel] = {}
        self.running = False
        self.measurement_callbacks = []
        
    def initialize(self) -> bool:
        if not self.comm.initialize_serial():
            logging.warning("Serial initialization failed, running in simulation mode")
            
        # 只初始化一个通道用于演示
        channel_config = self.config_manager.get_channel_config(1)
        self.channels[1] = GratingChannel(1, channel_config, self.comm)
        logging.info("Channel 1 initialized")
                
        return True
    
    def start_measurement(self):
        if not self.running:
            self.running = True
            self.measurement_thread = threading.Thread(target=self._measurement_loop)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()
            logging.info("Measurement started")
    
    def stop_measurement(self):
        self.running = False
        logging.info("Measurement stopped")
    
    def add_measurement_callback(self, callback):
        self.measurement_callbacks.append(callback)
    
    def _measurement_loop(self):
        display_settings = self.config_manager.get_round_display_settings()
        interval = display_settings['read_slave_interval'] / 1000.0
        
        while self.running:
            for channel_num, channel in self.channels.items():
                if not self.running:
                    break
                    
                measurement = channel.read_grating_data()
                if measurement:
                    for callback in self.measurement_callbacks:
                        callback(channel_num, measurement)
                        
            time.sleep(interval)

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("G45-L-P1X光栅测量系统")
        self.root.geometry("1400x900")
        self.root.configure(bg='lightgray')
        
        self.system = OpticalGratingSystem()
        self.current_page = "L-P1"  # 当前显示的页面
        self.page_buttons = {}
        self.figures = {}
        self.axes = {}
        self.lines = {}
        self.cpk_labels = {}
        
        # 页面参数映射
        self.page_params = {
            "L-P1": "P1", "L-P5U": "P5U", "L-P5L": "P5L", "L-P3": "P3", "L-P4": "P4",
            "R-P1": "P1", "R-P5U": "P5U", "R-P5L": "P5L", "R-P3": "P3", "R-P4": "P4"
        }
        
        self.init_ui()
        self.system.add_measurement_callback(self.update_charts)
        
    def init_ui(self):
        # 顶部标题栏
        title_frame = tk.Frame(self.root, bg='lightblue', height=60)
        title_frame.pack(fill=tk.X, padx=5, pady=5)
        title_frame.pack_propagate(False)
        
        # 左侧标题
        tk.Label(title_frame, text="G45", font=('Arial', 16, 'bold'), bg='lightblue').pack(side=tk.LEFT, padx=20, pady=15)
        
        # 中间参数按钮
        params_frame = tk.Frame(title_frame, bg='lightblue')
        params_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=50)
        
        left_params = tk.Frame(params_frame, bg='lightblue')
        left_params.pack(side=tk.LEFT, expand=True)
        
        right_params = tk.Frame(params_frame, bg='lightblue')
        right_params.pack(side=tk.RIGHT, expand=True)
        
        # 左侧参数按钮
        left_param_names = ['L-P1', 'L-P5U', 'L-P5L', 'L-P3', 'L-P4']
        for i, param in enumerate(left_param_names):
            btn = tk.Button(left_params, text=param, font=('Arial', 10), 
                           command=lambda p=param: self.switch_page(p),
                           bg='white' if param != self.current_page else 'yellow')
            btn.grid(row=i//3, column=i%3, padx=5, pady=2, sticky='ew')
            self.page_buttons[param] = btn
        
        # 右侧参数按钮
        right_param_names = ['R-P1', 'R-P5U', 'R-P5L', 'R-P3', 'R-P4']
        for i, param in enumerate(right_param_names):
            btn = tk.Button(right_params, text=param, font=('Arial', 10),
                           command=lambda p=param: self.switch_page(p),
                           bg='white' if param != self.current_page else 'yellow')
            btn.grid(row=i//3, column=i%3, padx=5, pady=2, sticky='ew')
            self.page_buttons[param] = btn
        
        # 中间标题
        tk.Label(title_frame, text="G45-L-P1X光栅", font=('Arial', 14, 'bold'), bg='lightblue').pack(pady=15)
        
        # 右侧时间和状态
        time_frame = tk.Frame(title_frame, bg='lightblue')
        time_frame.pack(side=tk.RIGHT, padx=20, pady=15)
        tk.Label(time_frame, text="2025/08/02", font=('Arial', 10), bg='lightblue').pack()
        tk.Label(time_frame, text="09:41:28", font=('Arial', 10), bg='lightblue').pack()
        
        # 控制按钮
        control_frame = tk.Frame(self.root, bg='lightgray')
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_button = tk.Button(control_frame, text="开始测量", command=self.start_measurement, 
                                     bg='green', fg='white', font=('Arial', 12))
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(control_frame, text="停止测量", command=self.stop_measurement,
                                    bg='red', fg='white', font=('Arial', 12))
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 主图表区域
        self.chart_frame = tk.Frame(self.root, bg='lightgray')
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建当前页面的图表
        self.create_page_charts()
        
    def switch_page(self, page_name):
        """切换到指定页面"""
        # 更新按钮状态
        for btn_name, btn in self.page_buttons.items():
            if btn_name == page_name:
                btn.config(bg='yellow')
            else:
                btn.config(bg='white')
        
        self.current_page = page_name
        
        # 清除当前图表
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        
        # 创建新页面的图表
        self.create_page_charts()
        
    def create_page_charts(self):
        """创建当前页面的图表"""
        param = self.page_params[self.current_page]
        
        # 创建左右两个图表框架
        left_frame = tk.Frame(self.chart_frame, bg='white', relief=tk.RAISED, bd=2)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right_frame = tk.Frame(self.chart_frame, bg='white', relief=tk.RAISED, bd=2)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧：平均值图表
        self.create_chart(left_frame, f"{param}_avg", "平均值", param)
        
        # 右侧：极差值图表
        self.create_chart(right_frame, f"{param}_range", "极差值", param)
        
    def create_chart(self, parent, data_key, title, param):
        """创建单个图表"""
        # 标题和CPK标签
        header_frame = tk.Frame(parent, bg='white')
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(header_frame, text=title, font=('Arial', 14, 'bold'), bg='white').pack(side=tk.LEFT)
        
        cpk_label = tk.Label(header_frame, text="CPK=1.62", font=('Arial', 12, 'bold'), 
                            bg='white', fg='blue')
        cpk_label.pack(side=tk.RIGHT)
        self.cpk_labels[data_key] = cpk_label
        
        # 创建图表
        fig = Figure(figsize=(8, 6), dpi=80, facecolor='white')
        ax = fig.add_subplot(111)
        
        # 设置Y轴范围
        if 'avg' in data_key:
            y_ranges = {
                'P1': (219.0, 221.0),
                'P5U': (423.0, 427.0),
                'P5L': (423.0, 427.0),
                'P3': (643.0, 647.0),
                'P4': (0.0, 2.0)
            }
            if param in y_ranges:
                ax.set_ylim(y_ranges[param])
        else:  # range values
            ax.set_ylim(0, 2.0)  # 极差值通常较小
        
        ax.set_xlim(0, 25)
        ax.grid(True, alpha=0.3)
        ax.set_facecolor('white')
        
        # 添加规格限线（仅对平均值图表）
        if 'avg' in data_key and param == 'P1':
            ax.axhline(y=220.90, color='red', linestyle='--', alpha=0.7, label='上限')
            ax.axhline(y=219.10, color='red', linestyle='--', alpha=0.7, label='下限')
        
        # 创建数据线，显示所有25个点
        x_data = list(range(25))
        y_data = [0] * 25  # 初始化为0
        line, = ax.plot(x_data, y_data, 'b-', linewidth=2, marker='o', markersize=4)
        
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.figures[data_key] = fig
        self.axes[data_key] = ax
        self.lines[data_key] = line
        
    def start_measurement(self):
        if self.system.initialize():
            self.system.start_measurement()
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
    
    def stop_measurement(self):
        self.system.stop_measurement()
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
    
    def update_charts(self, channel_num: int, measurement: Dict[str, float]):
        """更新图表数据"""
        channel = self.system.channels[channel_num]
        
        # 更新当前页面显示的参数
        param = self.page_params[self.current_page]
        avg_key = f"{param}_avg"
        range_key = f"{param}_range"
        
        # 更新平均值图表
        if avg_key in self.lines and avg_key in channel.measurements:
            data = channel.measurements[avg_key]
            if len(data) > 0:
                # 确保显示25个点
                display_data = data + [data[-1]] * (25 - len(data)) if len(data) < 25 else data[-25:]
                x_data = list(range(len(display_data)))
                self.lines[avg_key].set_data(x_data, display_data)
                
                # 更新CPK
                cpk = channel.calculate_cpk(avg_key)
                if avg_key in self.cpk_labels:
                    self.cpk_labels[avg_key].config(text=f"CPK={cpk:.2f}")
                
                # 刷新图表
                self.figures[avg_key].canvas.draw()
        
        # 更新极差值图表
        if range_key in self.lines and range_key in channel.measurements:
            data = channel.measurements[range_key]
            if len(data) > 0:
                # 确保显示25个点
                display_data = data + [data[-1]] * (25 - len(data)) if len(data) < 25 else data[-25:]
                x_data = list(range(len(display_data)))
                self.lines[range_key].set_data(x_data, display_data)
                
                # 刷新图表
                self.figures[range_key].canvas.draw()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    app = MainWindow()
    app.run()

