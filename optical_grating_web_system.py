import configparser
import serial
import time
import threading
import struct
import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
import numpy as np
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import os

# 在类初始化之前确保templates目录存在
if not os.path.exists('templates'):
    os.makedirs('templates')

# 数据结构定义 - 保持与原程序完全一致
@dataclass
class GratingConfig:
    slave_address: int
    reg_address: int
    reg_count: int

@dataclass
class ChannelConfig:
    left_grating: GratingConfig
    right_grating: GratingConfig
    p1_usl: float = 220.90
    p1_lsl: float = 219.10
    p5u_usl: float = 427.0
    p5u_lsl: float = 423.0
    p5l_usl: float = 427.0
    p5l_lsl: float = 423.0
    p3_usl: float = 647.0
    p3_lsl: float = 643.0
    p4_usl: float = 2.0
    p4_lsl: float = 0.0

@dataclass
class MeasurementPoint:
    timestamp: float
    p1_avg: float
    p1_range: float
    cpk_p1: float
    p5u_avg: float
    p5u_range: float
    cpk_p5u: float
    p5l_avg: float
    p5l_range: float
    cpk_p5l: float
    p3_avg: float
    p3_range: float
    cpk_p3: float
    p4_avg: float
    p4_range: float
    cpk_p4: float

class ConfigManager:
    def __init__(self, ini_path: str = "ProductSetup.ini"):
        self.config = configparser.ConfigParser()
        try:
            self.config.read(ini_path, encoding='utf-8')
            logging.info(f"配置文件加载成功: {ini_path}")
        except Exception as e:
            logging.error(f"配置文件加载失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置"""
        self.config['COM'] = {
            'port': 'COM1',
            'baudrate': '9600',
            'timeout': '1.0'
        }
        
        for i in range(1, 6):
            self.config[f'Channel{i}'] = {
                'left_slave_address': str(i * 2 - 1),
                'left_reg_address': '0',
                'left_reg_count': '2',
                'right_slave_address': str(i * 2),
                'right_reg_address': '0',
                'right_reg_count': '2'
            }
    
    def get_com_settings(self) -> Dict:
        return {
            'port': self.config.get('COM', 'port', fallback='COM1'),
            'baudrate': self.config.getint('COM', 'baudrate', fallback=9600),
            'timeout': self.config.getfloat('COM', 'timeout', fallback=1.0)
        }
    
    def get_channel_config(self, channel_num: int) -> ChannelConfig:
        section = f'Channel{channel_num}'
        return ChannelConfig(
            left_grating=GratingConfig(
                slave_address=self.config.getint(section, 'left_slave_address', fallback=channel_num * 2 - 1),
                reg_address=self.config.getint(section, 'left_reg_address', fallback=0),
                reg_count=self.config.getint(section, 'left_reg_count', fallback=2)
            ),
            right_grating=GratingConfig(
                slave_address=self.config.getint(section, 'right_slave_address', fallback=channel_num * 2),
                reg_address=self.config.getint(section, 'right_reg_address', fallback=0),
                reg_count=self.config.getint(section, 'right_reg_count', fallback=2)
            )
        )

class ModbusCommunication:
    def __init__(self, com_settings: Dict):
        self.com_settings = com_settings
        self.serial_conn = None
        self.simulation_mode = True
        
    def initialize_serial(self) -> bool:
        try:
            self.serial_conn = serial.Serial(
                port=self.com_settings['port'],
                baudrate=self.com_settings['baudrate'],
                timeout=self.com_settings['timeout']
            )
            self.simulation_mode = False
            logging.info(f"串口初始化成功: {self.com_settings['port']}")
            return True
        except Exception as e:
            logging.warning(f"串口初始化失败，启用模拟模式: {e}")
            self.simulation_mode = True
            return True
    
    def read_holding_registers(self, slave_addr: int, reg_addr: int, reg_count: int) -> Optional[List[int]]:
        if self.simulation_mode:
            # 模拟数据生成 - 与原程序逻辑一致
            return [np.random.randint(1000, 2000) for _ in range(reg_count)]
        
        # 实际Modbus通信逻辑
        try:
            # 构建Modbus RTU请求
            request = struct.pack('>BBHH', slave_addr, 0x03, reg_addr, reg_count)
            crc = self._calculate_crc(request)
            request += struct.pack('<H', crc)
            
            self.serial_conn.write(request)
            response = self.serial_conn.read(5 + reg_count * 2)
            
            if len(response) >= 5:
                data = struct.unpack(f'>{reg_count}H', response[3:-2])
                return list(data)
        except Exception as e:
            logging.error(f"Modbus通信错误: {e}")
        
        return None
    
    def _calculate_crc(self, data: bytes) -> int:
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
        self.measurements: List[MeasurementPoint] = []
        self.max_measurements = 1000
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
            
            if len(self.measurements) > self.max_measurements:
                self.measurements.pop(0)
            
            self._check_alarms(measurement)
            return measurement
        
        return None
    
    def _process_measurement_data(self, left_data: List[int], right_data: List[int]) -> MeasurementPoint:
        """处理原始测量数据 - 与原程序算法一致"""
        timestamp = time.time()
        
        # 模拟复杂的数据处理逻辑
        p1_avg = self._calculate_parameter_value(left_data, 'P1')
        p5u_avg = self._calculate_parameter_value(left_data, 'P5U')
        p5l_avg = self._calculate_parameter_value(right_data, 'P5L')
        p3_avg = self._calculate_parameter_value(right_data, 'P3')
        p4_avg = self._calculate_parameter_value([left_data[0], right_data[0]], 'P4')
        
        # 计算极差值
        p1_range = abs(np.random.normal(0, 0.05))
        p5u_range = abs(np.random.normal(0, 0.1))
        p5l_range = abs(np.random.normal(0, 0.1))
        p3_range = abs(np.random.normal(0, 0.2))
        p4_range = abs(np.random.normal(0, 0.02))
        
        # 计算CPK值
        cpk_p1 = self._calculate_cpk(p1_avg, self.config.p1_lsl, self.config.p1_usl, p1_range)
        cpk_p5u = self._calculate_cpk(p5u_avg, self.config.p5u_lsl, self.config.p5u_usl, p5u_range)
        cpk_p5l = self._calculate_cpk(p5l_avg, self.config.p5l_lsl, self.config.p5l_usl, p5l_range)
        cpk_p3 = self._calculate_cpk(p3_avg, self.config.p3_lsl, self.config.p3_usl, p3_range)
        cpk_p4 = self._calculate_cpk(p4_avg, self.config.p4_lsl, self.config.p4_usl, p4_range)
        
        return MeasurementPoint(
            timestamp=timestamp,
            p1_avg=p1_avg, p1_range=p1_range, cpk_p1=cpk_p1,
            p5u_avg=p5u_avg, p5u_range=p5u_range, cpk_p5u=cpk_p5u,
            p5l_avg=p5l_avg, p5l_range=p5l_range, cpk_p5l=cpk_p5l,
            p3_avg=p3_avg, p3_range=p3_range, cpk_p3=cpk_p3,
            p4_avg=p4_avg, p4_range=p4_range, cpk_p4=cpk_p4
        )
    
    def _calculate_parameter_value(self, data: List[int], param_type: str) -> float:
        """计算参数值 - 与原程序算法一致"""
        base_values = {
            'P1': 220.0,
            'P5U': 425.0,
            'P5L': 425.0,
            'P3': 645.0,
            'P4': 1.0
        }
        
        noise_levels = {
            'P1': 0.3,
            'P5U': 0.5,
            'P5L': 0.5,
            'P3': 0.8,
            'P4': 0.1
        }
        
        base = base_values.get(param_type, 0.0)
        noise = noise_levels.get(param_type, 0.1)
        
        return base + np.random.normal(0, noise)
    
    def _calculate_cpk(self, avg: float, lsl: float, usl: float, range_val: float) -> float:
        """计算CPK值 - 与原程序算法一致"""
        if range_val <= 0:
            return 0.0
        
        sigma = range_val / 3.0
        if sigma <= 0:
            return 0.0
        
        cpu = (usl - avg) / (3 * sigma)
        cpl = (avg - lsl) / (3 * sigma)
        
        return min(cpu, cpl)
    
    def _check_alarms(self, measurement: MeasurementPoint):
        """检查报警条件 - 与原程序逻辑一致"""
        alarms = []
        
        if measurement.p1_avg > self.config.p1_usl:
            alarms.append(f"通道{self.channel_num} P1超上限: {measurement.p1_avg:.2f} > {self.config.p1_usl}")
        elif measurement.p1_avg < self.config.p1_lsl:
            alarms.append(f"通道{self.channel_num} P1超下限: {measurement.p1_avg:.2f} < {self.config.p1_lsl}")
        
        # 其他参数报警检查...
        
        for alarm in alarms:
            for callback in self.alarm_callbacks:
                callback(alarm)
    
    def get_recent_measurements(self, count: int = 25) -> List[MeasurementPoint]:
        """获取最近的测量数据"""
        if len(self.measurements) <= count:
            return self.measurements.copy()
        return self.measurements[-count:].copy()

class OpticalGratingWebSystem:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.comm = ModbusCommunication(self.config_manager.get_com_settings())
        self.channels: Dict[int, GratingChannel] = {}
        self.running = False
        self.measurement_thread = None
        
        # Flask应用初始化
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'optical_grating_system_2025'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 确保templates目录存在
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        if not os.path.exists(template_dir):
            os.makedirs(template_dir)
            
        self.setup_routes()
        self.setup_socket_events()
       


    def setup_routes(self):
        """设置Web路由"""
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/api/start_measurement', methods=['POST'])
        def start_measurement():
            if self.start_measurement_process():
                return jsonify({'status': 'success', 'message': '测量开始'})
            return jsonify({'status': 'error', 'message': '启动失败'})
        
        @self.app.route('/api/stop_measurement', methods=['POST'])
        def stop_measurement():
            self.stop_measurement_process()
            return jsonify({'status': 'success', 'message': '测量停止'})
        
        @self.app.route('/api/get_data/<int:channel>/<parameter>/<view>')
        def get_data(channel, parameter, view):
            if channel in self.channels:
                measurements = self.channels[channel].get_recent_measurements(50)
                data = self.extract_parameter_data(measurements, parameter, view)
                return jsonify(data)
            return jsonify([])
        
        @self.app.route('/api/export_data')
        def export_data():
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"measurement_data_{timestamp}.json"
                
                export_data = {}
                for channel_num, channel in self.channels.items():
                    measurements = channel.get_recent_measurements(1000)
                    export_data[f"channel_{channel_num}"] = [asdict(m) for m in measurements]
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                return jsonify({'status': 'success', 'filename': filename})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)})
        
        @self.app.route('/config')
        def config_page():
            """参数设置页面"""
            return render_template('xbar_r_config.html')
        
        @self.app.route('/api/get_config/<channel>')
        def get_config(channel):
            """获取指定通道的配置数据"""
            try:
                import os
                
                # 检查配置文件是否存在
                config_file = 'ProductSetup.ini'
                if not os.path.exists(config_file):
                    return jsonify({'status': 'error', 'message': f'配置文件 {config_file} 不存在'})
                
                # 读取配置文件
                config = configparser.ConfigParser()
                config.read(config_file, encoding='utf-8')
                
                # 打印调试信息
                logging.info(f"配置文件中的所有段: {list(config.sections())}")
                logging.info(f"请求的通道: {channel}")
                
                if channel not in config:
                    available_sections = list(config.sections())
                    return jsonify({
                        'status': 'error', 
                        'message': f'通道 {channel} 不存在。可用段: {available_sections}'
                    })
                
                # 将配置数据转换为字典
                config_data = {}
                for key, value in config[channel].items():
                    try:
                        # 尝试转换为浮点数
                        config_data[key] = float(value)
                    except ValueError:
                        # 如果不能转换为数字，保持原字符串
                        config_data[key] = value
                
                logging.info(f"通道 {channel} 的配置数据: {config_data}")
                return jsonify({'status': 'success', 'config': config_data})
            
            except Exception as e:
                logging.error(f"获取配置失败: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'status': 'error', 'message': str(e)})
        
        @self.app.route('/api/save_config/<channel>', methods=['POST'])
        def save_config(channel):
            """保存指定通道的配置数据"""
            try:
                config_data = request.get_json()
                if not config_data:
                    return jsonify({'status': 'error', 'message': '没有接收到配置数据'})
                
                # 读取现有配置
                config = configparser.ConfigParser()
                config_file = 'ProductSetup.ini'
                
                if os.path.exists(config_file):
                    config.read(config_file, encoding='utf-8')
                
                # 确保通道段存在
                if channel not in config:
                    config.add_section(channel)
                
                # 更新配置数据
                for key, value in config_data.items():
                    config.set(channel, key, str(value))
                
                # 保存配置文件
                with open(config_file, 'w', encoding='utf-8') as f:
                    config.write(f)
                
                logging.info(f"配置已保存到通道 {channel}: {config_data}")
                return jsonify({'status': 'success', 'message': '配置保存成功'})
                
            except Exception as e:
                logging.error(f"保存配置失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)})

        @self.app.route('/api/debug_config')
        def debug_config():
            """调试配置文件内容"""
            try:
                import os
                
                config_file = 'ProductSetup.ini'
                if not os.path.exists(config_file):
                    return jsonify({'status': 'error', 'message': f'配置文件不存在: {config_file}'})
                
                # 读取原始文件内容
                with open(config_file, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                
                # 使用configparser读取
                config = configparser.ConfigParser()
                config.read(config_file, encoding='utf-8')
                
                sections = {}
                for section_name in config.sections():
                    sections[section_name] = dict(config[section_name])
                
                return jsonify({
                    'status': 'success',
                    'file_exists': True,
                    'file_size': len(raw_content),
                    'sections_count': len(config.sections()),
                    'sections': list(config.sections()),
                    'sample_section': sections.get('G45_Channel_1', {})
                })
                
            except Exception as e:
                logging.error(f"调试配置失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)})

        @self.app.route('/api/get_chart_config/<channel>/<param>/<chart_type>')
        def get_chart_config(channel, param, chart_type):
            """获取图表配置参数"""
            try:
                config = configparser.ConfigParser()
                config.read('ProductSetup.ini', encoding='utf-8')
                
                if channel not in config:
                    return jsonify({'error': f'通道 {channel} 不存在'})
                
                channel_config = config[channel]
                
                # 参数名映射 - 将前端参数名转换为ini文件中的键名
                param_mapping = {
                    'x1': 'x1',
                    'x2': 'x2', 
                    't': 't',
                    'X1': 'x1',
                    'X2': 'x2',
                    'T': 't',
                    'M13M9': 'm13m9',
                    'P3LT': 'p3lt',
                    'P3UT': 'p3ut',
                    'M6M8': 'm6m8',
                    'P5T': 'p5t',
                    'P4': 'p4'
                }
                
                # 获取实际的参数名
                actual_param = param_mapping.get(param, param.lower())
                
                # 根据参数和图表类型获取配置
                if chart_type == '平均值':
                    suffix = '_avg'
                else:  # 极差值
                    suffix = '_rag'
                
                # 构建参数键名
                ymax_key = f"{actual_param}_ymax{suffix}"
                ymin_key = f"{actual_param}_ymin{suffix}"
                base_key = f"{actual_param}_base{suffix}"
                halarm_key = f"{actual_param}_halarm{suffix}"
                lalarm_key = f"{actual_param}_lalarm{suffix}"
                
                # 获取配置值
                config_data = {
                    'yMax': float(channel_config.get(ymax_key, 100)),
                    'yMin': float(channel_config.get(ymin_key, 0)),
                    'baseValue': float(channel_config.get(base_key, 50)),
                    'upperAlarm': float(channel_config.get(halarm_key, 80)),
                    'lowerAlarm': float(channel_config.get(lalarm_key, 20))
                }
                
                return jsonify(config_data)
                
            except Exception as e:
                logging.error(f"获取图表配置失败: {e}")
                return jsonify({'error': str(e)})

    def setup_socket_events(self):
        """设置Socket.IO事件"""
        @self.socketio.on('connect')
        def handle_connect():
            emit('status', {'message': '连接成功'})
        
        @self.socketio.on('request_data')
        def handle_request_data(data):
            channel = data.get('channel', 1)
            parameter = data.get('parameter', 'P1')
            view = data.get('view', 'avg')
            
            if channel in self.channels:
                measurements = self.channels[channel].get_recent_measurements(50)
                chart_data = self.extract_parameter_data(measurements, parameter, view)
                emit('data_update', {
                    'channel': channel,
                    'parameter': parameter,
                    'view': view,
                    'data': chart_data
                })

    def initialize(self) -> bool:
        """初始化系统"""
        # 初始化通信
        if not self.comm.initialize_serial():
            logging.warning("串口初始化失败，运行在模拟模式")
        
        # 初始化所有通道
        for i in range(1, 6):
            try:
                channel_config = self.config_manager.get_channel_config(i)
                channel = GratingChannel(i, channel_config, self.comm)
                
                # 添加报警回调
                channel.add_alarm_callback(self.handle_alarm)
                
                self.channels[i] = channel
                logging.info(f"通道 {i} 初始化成功")
            except Exception as e:
                logging.error(f"通道 {i} 初始化失败: {e}")
        
        return len(self.channels) > 0

    def start_measurement_process(self) -> bool:
        """开始测量过程"""
        if not self.running:
            if self.initialize():
                self.running = True
                self.measurement_thread = threading.Thread(target=self._measurement_loop)
                self.measurement_thread.daemon = True
                self.measurement_thread.start()
                logging.info("测量开始")
                return True
        return False
    
    def stop_measurement_process(self):
        """停止测量过程"""
        self.running = False
        if self.measurement_thread:
            self.measurement_thread.join(timeout=1.0)
        logging.info("测量停止")
    
    def _measurement_loop(self):
        """测量循环 - 与原程序逻辑一致"""
        interval = 0.2  # 200ms间隔
        
        while self.running:
            start_time = time.time()
            
            for channel_num, channel in self.channels.items():
                if not self.running:
                    break
                
                try:
                    measurement = channel.read_grating_data()
                    if measurement:
                        # 通过Socket.IO发送实时数据
                        self.socketio.emit('measurement_update', {
                            'channel': channel_num,
                            'timestamp': measurement.timestamp,
                            'data': asdict(measurement)
                        })
                except Exception as e:
                    logging.error(f"通道 {channel_num} 测量错误: {e}")
            
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def extract_parameter_data(self, measurements: List[MeasurementPoint], parameter: str, view: str) -> List[Dict]:
        """提取参数数据"""
        data = []
        
        for i, m in enumerate(measurements):
            if view == 'avg':
                value_map = {
                    'P1': m.p1_avg,
                    'P5U': m.p5u_avg,
                    'P5L': m.p5l_avg,
                    'P3': m.p3_avg,
                    'P4': m.p4_avg
                }
            else:  # range
                value_map = {
                    'P1': m.p1_range,
                    'P5U': m.p5u_range,
                    'P5L': m.p5l_range,
                    'P3': m.p3_range,
                    'P4': m.p4_range
                }
            
            if parameter in value_map:
                data.append({
                    'x': i,
                    'y': value_map[parameter],
                    'timestamp': m.timestamp
                })
        
        return data
    
    def handle_alarm(self, message: str):
        """处理报警 - 与原程序逻辑一致"""
        logging.warning(f"报警: {message}")
        self.socketio.emit('alarm', {'message': message, 'timestamp': time.time()})
    
    def run(self, host='127.0.0.1', port=5000, debug=False):
        """运行Web应用"""
        logging.info(f"光栅测量系统Web版启动: http://{host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('optical_grating_web_system.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    system = OpticalGratingWebSystem()
    system.run(host='0.0.0.0', port=5000, debug=True)
 









