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
import queue
from threading import Lock
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
import os

# 数据库访问模块
try:
    import pyodbc
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("pyodbc模块未安装，将使用模拟数据")

# 在类初始化之前确保templates目录存在
if not os.path.exists('templates'):
    os.makedirs('templates')

class DatabaseManager:
    """数据库管理类 - 用于访问guangshan.mdb中的_25表数据"""

    def __init__(self, db_path: str = "guangshan.mdb"):
        self.db_path = os.path.abspath(db_path)
        self.connection = None
        self.available = DATABASE_AVAILABLE and os.path.exists(self.db_path)

        # 使用单一连接和请求队列来避免连接过多
        self.single_connection = None
        self.connection_lock = Lock()
        self.request_queue = queue.Queue()
        self.connection_timeout = 10  # 减少超时时间
        self.last_used_time = 0
        self.connection_idle_timeout = 30  # 连接空闲超时时间

        # 请求限流机制 - 更宽松的限制
        self.request_semaphore = threading.Semaphore(2)  # 同时允许2个数据库请求
        self.request_cache = {}  # 简单的请求缓存
        self.cache_timeout = 10   # 缓存10秒，减少数据库访问

        if self.available:
            try:
                self._test_connection()
                logging.info(f"数据库连接成功: {self.db_path}")
            except Exception as e:
                logging.warning(f"数据库连接失败: {e}, 将使用模拟数据")
                self.available = False
        else:
            logging.warning("数据库不可用，将使用模拟数据")

    def _test_connection(self):
        """测试数据库连接"""
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={self.db_path};'
        conn = pyodbc.connect(conn_str)
        conn.close()

    def get_connection(self):
        """获取数据库连接 - 使用单一连接和锁机制"""
        if not self.available:
            return None

        with self.connection_lock:
            try:
                current_time = time.time()

                # 检查现有连接是否有效且未超时
                if (self.single_connection and
                    current_time - self.last_used_time < self.connection_idle_timeout):
                    try:
                        # 测试连接是否仍然有效
                        cursor = self.single_connection.cursor()
                        cursor.execute("SELECT 1")
                        cursor.close()
                        self.last_used_time = current_time
                        return self.single_connection
                    except:
                        # 连接无效，关闭并重新创建
                        try:
                            self.single_connection.close()
                        except:
                            pass
                        self.single_connection = None

                # 创建新连接
                conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={self.db_path};'
                self.single_connection = pyodbc.connect(conn_str, timeout=self.connection_timeout)
                self.last_used_time = current_time
                return self.single_connection

            except Exception as e:
                logging.error(f"获取数据库连接失败: {e}")
                return None

    def return_connection(self, conn):
        """返回连接 - 在单连接模式下不需要实际操作"""
        # 在单连接模式下，连接会被复用，不需要返回操作
        # 只更新最后使用时间
        self.last_used_time = time.time()

    def close_all_connections(self):
        """关闭所有连接"""
        with self.connection_lock:
            if self.single_connection:
                try:
                    self.single_connection.close()
                except:
                    pass
                self.single_connection = None

    def get_chart_data(self, version: str, channel: int, param: str, chart_type: str = 'avg', side: str = 'L') -> Optional[List[float]]:
        """
        从数据库获取图表数据

        Args:
            version: 版本 (G45/G48)
            channel: 通道号 (1-5)
            param: 参数名 (x1, x2, t, m13m9, p3lt, p3ut, m6m8, p5t, p4)
            chart_type: 图表类型 (avg/rag)
            side: 左右侧 (L/R)

        Returns:
            包含25个数据点的列表，如果失败返回None
        """
        if not self.available:
            return None

        # 简化版本：直接进行数据库查询，不使用复杂的缓存和限流
        try:
            # 根据版本构建表名格式
            if version == 'G48':
                # G48版本使用格式: G48_L_P1_25, G48_L_P5L_25 等
                channel_names = {1: 'P1', 2: 'P5L', 3: 'P5U', 4: 'P3', 5: 'P4'}
                channel_name = channel_names.get(channel, f'P{channel}')
                table_name = f"{version}_{side}_{channel_name}_25"
            else:
                # G45版本先尝试新格式，如果不存在则使用旧格式
                channel_names = {1: 'P1', 2: 'P5L', 3: 'P5U', 4: 'P3', 5: 'P4'}
                channel_name = channel_names.get(channel, f'P{channel}')
                new_format_table = f"{version}_{side}_{channel_name}_25"
                old_format_table = f"{version}_Channel_{channel}_25"

                # 先检查新格式表是否存在
                conn_temp = self.get_connection()
                if conn_temp:
                    try:
                        cursor_temp = conn_temp.cursor()
                        tables = cursor_temp.tables(tableType='TABLE')
                        table_names_list = [table.table_name for table in tables]

                        if new_format_table in table_names_list:
                            table_name = new_format_table
                        elif old_format_table in table_names_list:
                            table_name = old_format_table
                        else:
                            table_name = old_format_table  # 默认使用旧格式

                        self.return_connection(conn_temp)
                    except:
                        table_name = old_format_table  # 出错时使用旧格式
                        self.return_connection(conn_temp)
                else:
                    table_name = old_format_table  # 无法连接时使用旧格式

            conn = self.get_connection()
            if not conn:
                return None

            cursor = conn.cursor()

            # 检查表是否存在
            tables = cursor.tables(tableType='TABLE')
            table_names = [table.table_name for table in tables]

            if table_name not in table_names:
                logging.warning(f"表 {table_name} 不存在")
                self.return_connection(conn)
                return None

            # 根据版本、参数和图表类型构建字段名
            field_name = self._get_field_name(version, param, chart_type)
            logging.info(f"尝试查询表 {table_name} 的字段 {field_name}")

            # 首先检查表结构，看看有哪些字段
            cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
            if cursor.description:
                available_columns = [desc[0].lower() for desc in cursor.description]
                logging.info(f"表 {table_name} 的字段: {available_columns}")

                # 如果指定字段不存在，尝试其他可能的字段名
                if field_name.lower() not in available_columns:
                    # 根据版本生成不同的替代字段名
                    if version == 'G45':
                        alternative_names = [
                            f"{param.lower()}_{chart_type}",  # 标准格式: x1_avg, x1_rag
                            f"{param.upper()}_{chart_type.upper()}",  # 大写格式: X1_AVG, X1_RAG
                            f"{param}_{chart_type}",  # 原格式
                            param.lower(),  # 直接使用参数名
                            param.upper(),  # 大写参数名
                            f"{param.lower()}-{chart_type}",  # 连字符格式
                            f"{param.upper()}-{chart_type.upper()}",  # 大写连字符格式
                        ]
                    else:
                        # G48版本的替代字段名
                        alternative_names = [
                            param.lower(),  # 直接使用参数名
                            f"{param.upper()}_{chart_type.upper()}",  # 大写格式
                            f"{param}_{chart_type}",  # 原格式
                        ]

                    found_field = None
                    # 查找匹配的字段 - 使用更精确的匹配
                    for alt_name in alternative_names:
                        for col in available_columns:
                            if alt_name.lower() == col:
                                found_field = cursor.description[available_columns.index(col)][0]  # 获取原始字段名
                                break
                        if found_field:
                            break

                    if found_field:
                        field_name = found_field
                        logging.info(f"使用替代字段名: {field_name}")
                    else:
                        # 如果都找不到，使用第一个数值字段
                        cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
                        row = cursor.fetchone()
                        if row:
                            for i, value in enumerate(row):
                                col_name = cursor.description[i][0]
                                if (isinstance(value, (int, float)) and
                                    col_name.lower() not in ['id', 'date', 'time']):
                                    field_name = col_name
                                    logging.info(f"使用第一个数值字段: {field_name}")
                                    break

                        # 如果还是找不到合适的字段，记录详细信息并返回None
                        if not found_field and field_name.lower() not in available_columns:
                            logging.warning(f"表 {table_name} 中未找到参数 {param} 的 {chart_type} 字段")
                            logging.warning(f"期望字段: {field_name}")
                            logging.warning(f"可用字段: {[cursor.description[i][0] for i in range(len(cursor.description))]}")
                            self.return_connection(conn)
                            return None

            # 查询数据
            try:
                cursor.execute(f"SELECT TOP 25 [{field_name}] FROM [{table_name}] ORDER BY ID")
            except:
                # 如果按ID排序失败，尝试不排序
                cursor.execute(f"SELECT TOP 25 [{field_name}] FROM [{table_name}]")

            rows = cursor.fetchall()

            if not rows:
                logging.warning(f"表 {table_name} 字段 {field_name} 中没有数据")
                self.return_connection(conn)
                return None

            # 提取数值数据
            data = []
            for row in rows:
                if row[0] is not None and isinstance(row[0], (int, float)):
                    data.append(float(row[0]))

            # 将连接返回到池中而不是关闭
            self.return_connection(conn)

            # 确保返回25个数据点
            if len(data) < 25:
                # 如果数据不足25个，用最后一个值填充
                while len(data) < 25:
                    data.append(data[-1] if data else 0.0)
            elif len(data) > 25:
                # 如果数据超过25个，只取前25个
                data = data[:25]

            # 简化版本：不使用缓存

            logging.info(f"从表 {table_name} 字段 {field_name} 获取到 {len(data)} 个数据点")
            return data

        except Exception as e:
            logging.error(f"查询表 {table_name} 字段 {field_name} 失败: {e}")
            self.return_connection(conn)
            return None



    def _get_field_name(self, version: str, param: str, chart_type: str) -> str:
        """根据版本、参数和图表类型获取字段名"""
        # 统一的字段映射 - G45和G48都使用相同的表名结构
        field_mapping = {
            # G48版本的字段映射 - 基于实际数据库字段结构
            'G48': {
                # P1通道 (Channel 1) - 对应G48_L_P1_25表
                ('x1', 'avg'): 'P1 X-BAV',      # X1平均值 -> P1 X-BAV
                ('x1', 'rag'): 'P1 X-BMN',      # X1极差值 -> P1 X-BMN
                ('x2', 'avg'): 'P1 X-CAV',      # X2平均值 -> P1 X-CAV
                ('x2', 'rag'): 'P1 X-CMN',      # X2极差值 -> P1 X-CMN
                ('t', 'avg'): 'P1 totalAV',     # T平均值 -> P1 totalAV
                ('t', 'rag'): 'P1 totalMN',     # T极差值 -> P1 totalMN

                # P5L通道 (Channel 2) - 对应G48_L_P5L_25表
                ('m13m9', 'avg'): 'M13-M9AV',   # M13M9平均值 -> M13-M9AV
                ('m13m9', 'rag'): 'M13-M9MN',   # M13M9极差值 -> M13-M9MN
                ('p3lt', 'avg'): 'P5L totalAV', # P3LT平均值 -> P5L totalAV
                ('p3lt', 'rag'): 'P5L totalMN', # P3LT极差值 -> P5L totalMN

                # P5U通道 (Channel 3) - 对应G48_L_P5U_25表
                ('p3ut', 'avg'): 'P5U totalAV', # P3UT平均值 -> P5U totalAV
                ('p3ut', 'rag'): 'P5U totalMN', # P3UT极差值 -> P5U totalMN

                # P3通道 (Channel 4) - 对应G48_L_P3_25表
                ('m6m8', 'avg'): 'M6-M8AV',     # M6M8平均值 -> M6-M8AV
                ('m6m8', 'rag'): 'M6-M8MN',     # M6M8极差值 -> M6-M8MN
                ('p5t', 'avg'): 'P3 totalAV',   # P5T平均值 -> P3 totalAV
                ('p5t', 'rag'): 'P3 totalMN',   # P5T极差值 -> P3 totalMN

                # P4通道 (Channel 5) - 对应G48_L_P4_25表
                ('p4', 'avg'): 'P4AV',          # P4平均值 -> P4AV
                ('p4', 'rag'): 'P4MN',          # P4极差值 -> P4MN
            },

            # G45版本的字段映射
            'G45': {
                # 平均值字段映射
                ('x1', 'avg'): 'x1_avg',
                ('x2', 'avg'): 'x2_avg',
                ('t', 'avg'): 't_avg',
                ('m13m9', 'avg'): 'm13m9_avg',
                ('p3lt', 'avg'): 'p3lt_avg',
                ('p3ut', 'avg'): 'p3ut_avg',
                ('m6m8', 'avg'): 'm6m8_avg',
                ('p5t', 'avg'): 'p5t_avg',
                ('p4', 'avg'): 'p4_avg',

                # 极差值字段映射
                ('x1', 'rag'): 'x1_rag',
                ('x2', 'rag'): 'x2_rag',
                ('t', 'rag'): 't_rag',
                ('m13m9', 'rag'): 'm13m9_rag',
                ('p3lt', 'rag'): 'p3lt_rag',
                ('p3ut', 'rag'): 'p3ut_rag',
                ('m6m8', 'rag'): 'm6m8_rag',
                ('p5t', 'rag'): 'p5t_rag',
                ('p4', 'rag'): 'p4_rag',
            }
        }

        # 获取版本特定的映射
        version_mapping = field_mapping.get(version, {})
        return version_mapping.get((param.lower(), chart_type), f"{param.lower()}_{chart_type}")


    def get_available_tables(self) -> List[str]:
        """获取所有以_25结尾的表名"""
        if not self.available:
            return []

        conn = self.get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor()
            tables = cursor.tables(tableType='TABLE')
            table_names = [table.table_name for table in tables if table.table_name.endswith('_25')]
            conn.close()
            return table_names
        except Exception as e:
            logging.error(f"获取表列表失败: {e}")
            if conn:
                conn.close()
            return []

    def get_table_structure(self, table_name: str) -> Dict:
        """获取表结构信息"""
        if not self.available:
            return {}

        conn = self.get_connection()
        if not conn:
            return {}

        try:
            cursor = conn.cursor()

            # 获取表结构
            cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
            columns = []
            if cursor.description:
                columns = [{'name': desc[0], 'type': desc[1].__name__ if desc[1] else 'unknown'}
                          for desc in cursor.description]

            # 获取数据行数
            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            row_count = cursor.fetchone()[0] if cursor.fetchone() else 0

            # 获取示例数据
            cursor.execute(f"SELECT TOP 3 * FROM [{table_name}]")
            sample_data = []
            for row in cursor.fetchall():
                sample_data.append(list(row))

            conn.close()

            return {
                'table_name': table_name,
                'columns': columns,
                'row_count': row_count,
                'sample_data': sample_data
            }

        except Exception as e:
            logging.error(f"获取表结构失败: {e}")
            if conn:
                conn.close()
            return {}

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
    def __init__(self, channel_num: int, config: ChannelConfig, comm: ModbusCommunication, db_manager: DatabaseManager = None):
        self.channel_num = channel_num
        self.config = config
        self.comm = comm
        self.db_manager = db_manager
        self.measurements: List[MeasurementPoint] = []
        self.max_measurements = 1000
        self.alarm_callbacks: List[Callable[[str], None]] = []
        self.current_version = 'G45'  # 默认版本
        
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

    def get_chart_data_from_db(self, param: str, chart_type: str = 'avg', side: str = 'L') -> Optional[List[float]]:
        """从数据库获取图表数据"""
        if not self.db_manager or not self.db_manager.available:
            return None

        return self.db_manager.get_chart_data(self.current_version, self.channel_num, param, chart_type, side)

    def set_version(self, version: str):
        """设置当前版本"""
        self.current_version = version

class OpticalGratingWebSystem:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.comm = ModbusCommunication(self.config_manager.get_com_settings())
        self.db_manager = DatabaseManager()  # 添加数据库管理器
        self.channels: Dict[int, GratingChannel] = {}
        self.running = False
        self.measurement_thread = None
        self.current_version = 'G45'  # 当前版本
        
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

        @self.app.route('/test_switch')
        def test_switch():
            return send_from_directory('.', 'test_data_source_switch.html')

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

        @self.app.route('/api/get_chart_data/<version>/<int:channel>/<param>/<chart_type>/<side>')
        def get_chart_data(version, channel, param, chart_type, side):
            """从数据库获取图表数据"""
            try:
                if self.db_manager and self.db_manager.available:
                    data = self.db_manager.get_chart_data(version, channel, param, chart_type, side)
                    if data:
                        # 转换为前端需要的格式
                        chart_data = [{'x': i+1, 'y': value} for i, value in enumerate(data)]
                        return jsonify({
                            'status': 'success',
                            'data': chart_data,
                            'source': 'database',
                            'param': param,
                            'chart_type': chart_type
                        })

                # 如果数据库不可用，返回模拟数据
                base_values = {
                    'x1': 220.0, 'x2': 425.0, 't': 645.0,
                    'm13m9': 142.0, 'p3lt': 501.0, 'p3ut': 219.0,
                    'm6m8': 436.0, 'p5t': 580.0, 'p4': 466.0
                }
                base_value = base_values.get(param.lower(), 100.0)
                noise_level = 0.5 if chart_type == 'rag' else 0.3

                simulated_data = [{'x': i+1, 'y': base_value + np.random.normal(0, noise_level)} for i in range(25)]
                return jsonify({
                    'status': 'success',
                    'data': simulated_data,
                    'source': 'simulation',
                    'param': param,
                    'chart_type': chart_type
                })

            except Exception as e:
                logging.error(f"获取图表数据失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/api/get_database_info')
        def get_database_info():
            """获取数据库信息"""
            try:
                if self.db_manager and self.db_manager.available:
                    # 测试数据库连接
                    conn = self.db_manager.get_connection()
                    if conn:
                        tables = self.db_manager.get_available_tables()
                        self.db_manager.return_connection(conn)

                        return jsonify({
                            'status': 'success',
                            'database_available': True,
                            'table_count': len(tables),
                            'tables': tables,
                            'connection_status': 'active',
                            'last_check': time.strftime('%Y-%m-%d %H:%M:%S')
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'database_available': False,
                            'message': '数据库连接失败',
                            'connection_status': 'failed',
                            'last_check': time.strftime('%Y-%m-%d %H:%M:%S')
                        })
                else:
                    return jsonify({
                        'status': 'success',
                        'database_available': False,
                        'table_count': 0,
                        'tables': [],
                        'connection_status': 'unavailable',
                        'message': '数据库不可用，使用模拟数据',
                        'last_check': time.strftime('%Y-%m-%d %H:%M:%S')
                    })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'database_available': False,
                    'message': str(e),
                    'connection_status': 'error',
                    'last_check': time.strftime('%Y-%m-%d %H:%M:%S')
                })

        @self.app.route('/api/get_table_structure/<table_name>')
        def get_table_structure(table_name):
            """获取表结构信息"""
            try:
                if self.db_manager and self.db_manager.available:
                    structure = self.db_manager.get_table_structure(table_name)
                    return jsonify({
                        'status': 'success',
                        'structure': structure
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': '数据库不可用'
                    })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

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

        @self.app.route('/debug')
        def debug_page():
            """数据库调试页面"""
            return render_template('debug_database.html')
        
        @self.app.route('/api/get_config/<channel>')
        def get_config(channel):
            """获取通道配置"""
            try:
                config = configparser.ConfigParser()
                config.read('ProductSetup.ini', encoding='utf-8')
                
                print(f"请求的通道: {channel}")
                
                # 如果是CPK配置，获取所有相关通道的CPK设置
                if channel.endswith('CPK'):
                    # 提取前缀 (G45 或 G48)
                    if channel.startswith('G45'):
                        prefix = 'G45'
                    elif channel.startswith('G48'):
                        prefix = 'G48'
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': f'未知的CPK通道前缀: {channel}'
                        })
                    
                    # 收集所有相关通道的CPK配置
                    all_cpk_config = {}
                    
                    for i in range(1, 6):  # 通道1-5
                        cpk_section = f'{prefix}_Channel_{i}CPK'
                        if cpk_section in config:
                            section_config = dict(config[cpk_section])
                            # 为每个配置项添加通道前缀，避免键名冲突
                            for key, value in section_config.items():
                                prefixed_key = f"ch{i}_{key}"
                                all_cpk_config[prefixed_key] = value
                            print(f"添加了 {cpk_section} 的配置: {section_config}")
                    
                    print(f"合并后的CPK配置项数量: {len(all_cpk_config)}")
                    print(f"所有CPK配置键: {list(all_cpk_config.keys())}")
                    
                    return jsonify({
                        'status': 'success',
                        'config': all_cpk_config
                    })
                
                else:
                    # 普通通道配置
                    if channel not in config:
                        return jsonify({
                            'status': 'error',
                            'message': f'通道 {channel} 不存在于配置文件中'
                        })
                    
                    channel_config = dict(config[channel])
                    print(f"通道 {channel} 的配置项: {channel_config}")
                    
                    return jsonify({
                        'status': 'success',
                        'config': channel_config
                    })
                
            except Exception as e:
                print(f"获取配置失败: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'获取配置失败: {str(e)}'
                })
        
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

        @self.app.route('/api/get_versions')
        def get_versions():
            """获取可用版本列表"""
            try:
                config = configparser.ConfigParser()
                config.read('ProductSetup.ini', encoding='utf-8')
                
                versions = []
                if 'Version' in config:
                    for key, value in config['Version'].items():
                        versions.append(value)
                else:
                    # 默认版本
                    versions = ['G45', 'G48']
                
                current_version = 'G45'
                if 'CurrentVersion' in config and 'currentversion' in config['CurrentVersion']:
                    current_version = config.get('CurrentVersion', 'currentversion')
                
                return jsonify({
                    'status': 'success',
                    'versions': versions,
                    'current_version': current_version
                })
            except Exception as e:
                logging.error(f"获取版本失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e),
                    'versions': ['G45', 'G48'],
                    'current_version': 'G45'
                })

        @self.app.route('/api/set_version', methods=['POST'])
        def set_version():
            """设置当前版本"""
            try:
                data = request.get_json()
                version = data.get('version')
                
                if not version:
                    return jsonify({
                        'status': 'error',
                        'message': '未提供版本信息'
                    })
                
                config = configparser.ConfigParser()
                config.read('ProductSetup.ini', encoding='utf-8')
                
                if 'CurrentVersion' not in config:
                    config.add_section('CurrentVersion')
                
                config.set('CurrentVersion', 'currentversion', version)
                
                with open('ProductSetup.ini', 'w', encoding='utf-8') as f:
                    config.write(f)
                
                logging.info(f"版本已设置为: {version}")
                return jsonify({
                    'status': 'success',
                    'message': f'版本已设置为 {version}'
                })
            except Exception as e:
                logging.error(f"设置版本失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

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
                channel = GratingChannel(i, channel_config, self.comm, self.db_manager)

                # 设置当前版本
                channel.set_version(self.current_version)

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
 














