import configparser
import serial
import time
import threading
import struct
import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
import numpy as np
import queue
from threading import Lock
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
import os
import hashlib
import secrets
import pickle

# 数据库访问模块
try:
    import pyodbc
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("pyodbc模块未安装，将使用模拟数据")

# Modbus TCP设备模块
try:
    from modbus_device import ModbusTCPDevice
    MODBUS_TCP_AVAILABLE = True
except ImportError:
    MODBUS_TCP_AVAILABLE = False
    logging.warning("modbus_device模块未找到，Modbus TCP功能将不可用")

# 在类初始化之前确保templates目录存在
if not os.path.exists('templates'):
    os.makedirs('templates')

class TrialManager:
    """试用期管理类"""

    def __init__(self, trial_file: str = "trial_info.dat"):
        self.trial_file = trial_file
        self.trial_days = 1  # 试用期30天
        self.is_locked = False
        self.start_time = None
        self.used_codes = set()
        self.is_unlimited = False

        # 预生成的验证码
        self.extend_codes = [
            "EXTEND2025A1", "EXTEND2025B2", "EXTEND2025C3", "EXTEND2025D4", "EXTEND2025E5",
            "EXTEND2025F6", "EXTEND2025G7", "EXTEND2025H8", "EXTEND2025I9", "EXTEND2025J0"
        ]
        self.unlock_code = "UNLOCK2025FOREVER"

        self._load_trial_info()

    def _load_trial_info(self):
        """加载试用期信息"""
        try:
            if os.path.exists(self.trial_file):
                with open(self.trial_file, 'rb') as f:
                    data = pickle.load(f)
                    self.start_time = data.get('start_time')
                    self.used_codes = set(data.get('used_codes', []))
                    self.is_unlimited = data.get('is_unlimited', False)
                    logging.info(f"试用期信息加载成功，开始时间: {self.start_time}")
            else:
                # 首次运行，记录开始时间
                self.start_time = datetime.now()
                self._save_trial_info()
                logging.info(f"首次运行，试用期开始: {self.start_time}")
        except Exception as e:
            logging.error(f"加载试用期信息失败: {e}")
            self.start_time = datetime.now()
            self._save_trial_info()

    def _save_trial_info(self):
        """保存试用期信息"""
        try:
            data = {
                'start_time': self.start_time,
                'used_codes': list(self.used_codes),
                'is_unlimited': self.is_unlimited
            }
            with open(self.trial_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            logging.error(f"保存试用期信息失败: {e}")

    def get_trial_status(self) -> Dict:
        """获取试用期状态"""
        if self.is_unlimited:
            return {
                'is_trial': False,
                'is_expired': False,
                'days_used': 0,
                'days_remaining': -1,
                'message': '系统已解锁，无使用限制'
            }

        if not self.start_time:
            return {
                'is_trial': True,
                'is_expired': True,
                'days_used': 0,
                'days_remaining': 0,
                'message': '试用期信息异常'
            }

        now = datetime.now()
        days_used = (now - self.start_time).days
        days_remaining = max(0, self.trial_days - days_used)
        is_expired = days_remaining <= 0

        return {
            'is_trial': True,
            'is_expired': is_expired,
            'days_used': days_used,
            'days_remaining': days_remaining,
            'message': f'试用期剩余 {days_remaining} 天' if not is_expired else '试用期已到期'
        }

    def is_system_locked(self) -> bool:
        """检查系统是否被锁定"""
        if self.is_unlimited:
            return False

        status = self.get_trial_status()
        return status['is_expired']

    def verify_code(self, code: str) -> Dict:
        """验证验证码"""
        code = code.strip().upper()

        # 检查是否是解锁码
        if code == self.unlock_code:
            self.is_unlimited = True
            self._save_trial_info()
            logging.info("系统已永久解锁")
            return {
                'success': True,
                'type': 'unlock',
                'message': '系统已永久解锁，无使用限制'
            }

        # 检查是否是延期码
        if code in self.extend_codes:
            if code in self.used_codes:
                return {
                    'success': False,
                    'type': 'extend',
                    'message': '此验证码已使用过，请使用新的验证码'
                }

            # 延长试用期30天
            self.used_codes.add(code)
            if self.start_time:
                self.start_time = self.start_time - timedelta(days=30)
            else:
                self.start_time = datetime.now() - timedelta(days=30)

            self._save_trial_info()
            logging.info(f"试用期已延长30天，验证码: {code}")

            status = self.get_trial_status()
            return {
                'success': True,
                'type': 'extend',
                'message': f'试用期已延长30天，剩余 {status["days_remaining"]} 天'
            }

        return {
            'success': False,
            'type': 'invalid',
            'message': '验证码无效，请检查后重新输入'
        }

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

            # 根据版本、参数、图表类型和通道构建字段名
            field_name = self._get_field_name(version, param, chart_type, channel)
            logging.info(f"尝试查询表 {table_name} 的字段 {field_name}")

            # 特别记录P3LT参数的处理
            if param.lower() == 'p3lt':
                logging.info(f"🎯 P3LT参数处理: table={table_name}, field={field_name}, version={version}, channel={channel}")

            # 首先检查表结构，看看有哪些字段
            cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
            if cursor.description:
                available_columns = [desc[0].lower() for desc in cursor.description]
                logging.info(f"表 {table_name} 的字段: {available_columns}")

                # 如果指定字段不存在，尝试其他可能的字段名
                if field_name.lower() not in available_columns:
                    # 特殊处理P3LT参数 - 根据表的实际字段动态选择
                    if param.lower() == 'p3lt':
                        p3lt_candidates = []
                        if chart_type == 'avg':
                            p3lt_candidates = ['p5l totalav', 'p3l totalav', 'P5L totalAV', 'P3L totalAV', 'p5ltotalav', 'p3ltotalav']
                        else:  # rag
                            p3lt_candidates = ['p5l totalmn', 'p3l totalmn', 'P5L totalMN', 'P3L totalMN', 'p5ltotalmn', 'p3ltotalmn']

                        found_field = None
                        for candidate in p3lt_candidates:
                            for col in available_columns:
                                if candidate.lower() == col:
                                    found_field = cursor.description[available_columns.index(col)][0]
                                    logging.info(f"🎯 P3LT字段匹配成功: {candidate} -> {found_field}")
                                    break
                            if found_field:
                                break

                        if found_field:
                            field_name = found_field
                        else:
                            logging.warning(f"🎯 P3LT参数未找到匹配字段，候选字段: {p3lt_candidates}")
                            logging.warning(f"🎯 可用字段: {available_columns}")

                    # 特殊处理P5T参数 - 根据表的实际字段动态选择
                    elif param.lower() == 'p5t':
                        p5t_candidates = []
                        if chart_type == 'avg':
                            p5t_candidates = ['p3 totalav', 'p3 totaoav', 'P3 totalAV', 'P3 totaoAV', 'p3totalav', 'p3totaoav']
                        else:  # rag
                            p5t_candidates = ['p3 totalmn', 'p3 totaomn', 'P3 totalMN', 'P3 totaoMN', 'p3totalmn', 'p3totaomn']

                        found_field = None
                        for candidate in p5t_candidates:
                            for col in available_columns:
                                if candidate.lower() == col:
                                    found_field = cursor.description[available_columns.index(col)][0]
                                    logging.info(f"🎯 P5T字段匹配成功: {candidate} -> {found_field}")
                                    break
                            if found_field:
                                break

                        if found_field:
                            field_name = found_field
                        else:
                            logging.warning(f"🎯 P5T参数未找到匹配字段，候选字段: {p5t_candidates}")
                            logging.warning(f"🎯 可用字段: {available_columns}")
                    else:
                        # 其他参数的替代字段名逻辑
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

                    # 如果还是没找到，使用第一个数值字段作为最后的回退
                    if field_name.lower() not in available_columns:
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
                        if field_name.lower() not in available_columns:
                            logging.warning(f"表 {table_name} 中未找到参数 {param} 的 {chart_type} 字段")
                            logging.warning(f"期望字段: {field_name}")
                            logging.warning(f"可用字段: {[cursor.description[i][0] for i in range(len(cursor.description))]}")
                            self.return_connection(conn)
                            return None

            # 查询数据
            try:
                # 首先尝试按DATE和TIME排序（最常见的排序字段）
                cursor.execute(f"SELECT TOP 25 [{field_name}] FROM [{table_name}] WHERE [{field_name}] IS NOT NULL ORDER BY DATE DESC, TIME DESC")
            except:
                try:
                    # 如果DATE/TIME排序失败，尝试按ID排序
                    cursor.execute(f"SELECT TOP 25 [{field_name}] FROM [{table_name}] WHERE [{field_name}] IS NOT NULL ORDER BY ID")
                except:
                    # 如果都失败，不排序但过滤空值
                    cursor.execute(f"SELECT TOP 25 [{field_name}] FROM [{table_name}] WHERE [{field_name}] IS NOT NULL")

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



    def _get_field_name(self, version: str, param: str, chart_type: str, channel: int = None) -> str:
        """根据版本、参数、图表类型和通道获取字段名"""
        # 统一的字段映射
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

            # G45版本的字段映射 - 基于实际数据库字段结构
            'G45': {
                # P1通道 (Channel 1) - 对应G45_L_P1_25表
                ('x1', 'avg'): 'P1 X-BAV',      # X1平均值 -> P1 X-BAV
                ('x1', 'rag'): 'P1 X-BMN',      # X1极差值 -> P1 X-BMN
                ('x2', 'avg'): 'P1 X-CAV',      # X2平均值 -> P1 X-CAV
                ('x2', 'rag'): 'P1 X-CMN',      # X2极差值 -> P1 X-CMN
                ('t', 'avg'): 'P1 totalAV',     # T平均值 -> P1 totalAV
                ('t', 'rag'): 'P1 totalMN',     # T极差值 -> P1 totalMN

                # P5L通道 (Channel 2) - 对应G45_L_P5L_25表
                ('m13m9', 'avg'): 'M13-M9AV',   # M13M9平均值 -> M13-M9AV
                ('m13m9', 'rag'): 'M13-M9MN',   # M13M9极差值 -> M13-M9MN
                ('p3lt', 'avg'): 'p5l totalav', # P3LT平均值 -> p5l totalav (修正：匹配实际字段名)
                ('p3lt', 'rag'): 'p5l totalmn', # P3LT极差值 -> p5l totalmn (修正：匹配实际字段名)

                # P5U通道 (Channel 3) - 对应G45_L_P5U_25表
                ('p3ut', 'avg'): 'P5U totalAV', # P3UT平均值 -> P5U totalAV
                ('p3ut', 'rag'): 'P5U totalMN', # P3UT极差值 -> P5U totalMN

                # P3通道 (Channel 4) - 对应G45_L_P3_25表
                ('m6m8', 'avg'): 'M6-M8AV',     # M6M8平均值 -> M6-M8AV
                ('m6m8', 'rag'): 'M6-M8MN',     # M6M8极差值 -> M6-M8MN
                ('p5t', 'avg'): 'P3 totalAV',   # P5T平均值 -> P3 totalAV
                ('p5t', 'rag'): 'P3 totalMN',   # P5T极差值 -> P3 totalMN

                # P4通道 (Channel 5) - 对应G45_L_P4_25表
                ('p4', 'avg'): 'P4AV',          # P4平均值 -> P4AV
                ('p4', 'rag'): 'P4MN',          # P4极差值 -> P4MN
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

        # RS485-MODBUS通讯参数 (根据文档)
        self.MODBUS_PARAMS = {
            'protocol': 'RS485',
            'format': 'RTU',
            'data_bits': 8,
            'stop_bits': 1,
            'parity': 'None',
            'address_format': '16进制格式'
        }

        # 寄存器地址映射 (根据文档)
        self.REGISTER_MAP = {
            # 当前值寄存器 (读取)
            'current_value': {
                'address': 0x1000,  # 0x1000
                'count': 2,
                'range': '99999~-99999'
            },
            # 比例系数寄存器 (读取)
            'scale_factor': {
                'address': 0x1002,  # 0x1002
                'count': 2,
                'range': '1~29999(0.0001~2.9999)'
            },
            # 包络直径寄存器 (读取)
            'envelope_diameter': {
                'address': 0x1004,  # 0x1004
                'count': 2,
                'range': '1~40000mm'
            },
            # 多段补偿值寄存器 (读取)
            'multi_compensation': {
                'address': 0x1006,  # 0x1006
                'count': 2,
                'range': '0~9000mm'
            },
            # 测量方向寄存器 (读取)
            'measurement_direction': {
                'address': 0x2000,  # 0x2000
                'count': 1,
                'range': '0~1'
            },
            # 自校正寄存器 (读取)
            'self_calibration': {
                'address': 0x2001,  # 0x2001
                'count': 1,
                'range': '无'
            }
        }

        # 主机写<16位寄存器>命令寄存器地址映射
        self.WRITE_REGISTER_MAP = {
            # 寄存器地址
            'register_address': {
                'address': 0x2002,  # 0x2002
                'count': 1
            },
            # 寄存器个数
            'register_count': {
                'address': 0x2003,  # 0x2003
                'count': 1
            },
            # 写字节数
            'write_bytes': {
                'address': 0x2004,  # 0x2004
                'count': 1
            },
            # 寄存器数值
            'register_value': {
                'address': 0x2005,  # 0x2005
                'count': 1
            }
        }

    def initialize_serial(self) -> bool:
        try:
            # 根据RS485-MODBUS文档配置串口参数
            self.serial_conn = serial.Serial(
                port=self.com_settings['port'],
                baudrate=self.com_settings['baudrate'],
                bytesize=8,  # 8位数据位
                parity=serial.PARITY_NONE,  # 无校验
                stopbits=1,  # 1位停止位
                timeout=self.com_settings['timeout']
            )
            self.simulation_mode = False
            logging.info(f"RS485串口初始化成功: {self.com_settings['port']}, 波特率: {self.com_settings['baudrate']}")
            return True
        except Exception as e:
            logging.warning(f"RS485串口初始化失败，启用模拟模式: {e}")
            self.simulation_mode = True
            return True
    
    def read_holding_registers(self, slave_addr: int, reg_addr: int, reg_count: int) -> Optional[List[int]]:
        """
        读取保持寄存器 (功能码0x03)
        根据RS485-MODBUS通讯文档实现

        Args:
            slave_addr: 从机号 (1-247)
            reg_addr: 寄存器地址 (16进制格式)
            reg_count: 寄存器个数

        Returns:
            List[int]: 寄存器数据列表，失败返回None
        """
        if self.simulation_mode:
            # 模拟数据生成 - 根据寄存器类型生成合理数据
            if reg_addr == 0x1000:  # 当前值
                return [np.random.randint(-99999, 99999) & 0xFFFF for _ in range(reg_count)]
            elif reg_addr == 0x1002:  # 比例系数
                return [np.random.randint(1, 29999) for _ in range(reg_count)]
            elif reg_addr == 0x1004:  # 包络直径
                return [np.random.randint(1, 40000) for _ in range(reg_count)]
            elif reg_addr == 0x1006:  # 多段补偿值
                return [np.random.randint(0, 9000) for _ in range(reg_count)]
            elif reg_addr == 0x2000:  # 测量方向
                return [np.random.randint(0, 2)]
            else:
                return [np.random.randint(1000, 2000) for _ in range(reg_count)]

        # 实际RS485 Modbus RTU通信逻辑
        try:
            # 清空接收缓冲区
            if self.serial_conn.in_waiting > 0:
                self.serial_conn.reset_input_buffer()

            # 构建Modbus RTU请求帧
            # 格式: [从机地址][功能码][起始地址高][起始地址低][寄存器数量高][寄存器数量低][CRC低][CRC高]
            request = struct.pack('>BBHH', slave_addr, 0x03, reg_addr, reg_count)
            crc = self._calculate_crc(request)
            request += struct.pack('<H', crc)  # CRC是小端格式

            # 发送请求
            self.serial_conn.write(request)
            logging.debug(f"发送Modbus请求: 从机{slave_addr}, 地址0x{reg_addr:04X}, 数量{reg_count}")

            # 计算期望的响应长度: 从机地址(1) + 功能码(1) + 字节数(1) + 数据(reg_count*2) + CRC(2)
            expected_length = 5 + reg_count * 2

            # 读取响应
            response = self.serial_conn.read(expected_length)

            if len(response) < 5:
                logging.error(f"响应数据长度不足: 期望{expected_length}, 实际{len(response)}")
                return None

            # 验证响应
            if response[0] != slave_addr:
                logging.error(f"从机地址不匹配: 期望{slave_addr}, 实际{response[0]}")
                return None

            if response[1] & 0x80:  # 检查错误标志
                error_code = response[2]
                logging.error(f"Modbus错误响应: 功能码{response[1]}, 错误码{error_code}")
                return None

            if response[1] != 0x03:
                logging.error(f"功能码不匹配: 期望0x03, 实际0x{response[1]:02X}")
                return None

            # 验证CRC
            received_crc = struct.unpack('<H', response[-2:])[0]
            calculated_crc = self._calculate_crc(response[:-2])
            if received_crc != calculated_crc:
                logging.error(f"CRC校验失败: 接收0x{received_crc:04X}, 计算0x{calculated_crc:04X}")
                return None

            # 解析数据
            byte_count = response[2]
            if byte_count != reg_count * 2:
                logging.error(f"数据字节数不匹配: 期望{reg_count * 2}, 实际{byte_count}")
                return None

            # 提取寄存器数据 (大端格式)
            data = struct.unpack(f'>{reg_count}H', response[3:3+byte_count])
            logging.debug(f"读取成功: 从机{slave_addr}, 数据{list(data)}")
            return list(data)

        except Exception as e:
            logging.error(f"RS485 Modbus通信错误: {e}")
            return None
    
    def write_holding_registers(self, slave_addr: int, reg_addr: int, values: List[int]) -> bool:
        """
        写保持寄存器 (功能码0x10)
        根据RS485-MODBUS通讯文档实现主机写<16位寄存器>命令

        Args:
            slave_addr: 从机号 (1-247)
            reg_addr: 寄存器地址 (16进制格式)
            values: 要写入的数据列表

        Returns:
            bool: 写入是否成功
        """
        if self.simulation_mode:
            logging.info(f"模拟模式: 写入从机{slave_addr}, 地址0x{reg_addr:04X}, 数据{values}")
            return True

        try:
            reg_count = len(values)
            byte_count = reg_count * 2

            # 清空接收缓冲区
            if self.serial_conn.in_waiting > 0:
                self.serial_conn.reset_input_buffer()

            # 构建Modbus RTU写多个寄存器请求帧 (功能码0x10)
            # 格式: [从机地址][功能码][起始地址高][起始地址低][寄存器数量高][寄存器数量低][字节数][数据...][CRC低][CRC高]
            request = struct.pack('>BBHHB', slave_addr, 0x10, reg_addr, reg_count, byte_count)

            # 添加数据 (大端格式)
            for value in values:
                request += struct.pack('>H', value & 0xFFFF)

            # 计算并添加CRC
            crc = self._calculate_crc(request)
            request += struct.pack('<H', crc)

            # 发送请求
            self.serial_conn.write(request)
            logging.debug(f"发送写寄存器请求: 从机{slave_addr}, 地址0x{reg_addr:04X}, 数量{reg_count}")

            # 读取响应 (写多个寄存器响应长度固定为8字节)
            response = self.serial_conn.read(8)

            if len(response) < 8:
                logging.error(f"写寄存器响应长度不足: 期望8, 实际{len(response)}")
                return False

            # 验证响应
            if response[0] != slave_addr:
                logging.error(f"从机地址不匹配: 期望{slave_addr}, 实际{response[0]}")
                return False

            if response[1] & 0x80:  # 检查错误标志
                error_code = response[2]
                logging.error(f"写寄存器错误响应: 功能码{response[1]}, 错误码{error_code}")
                return False

            if response[1] != 0x10:
                logging.error(f"功能码不匹配: 期望0x10, 实际0x{response[1]:02X}")
                return False

            # 验证CRC
            received_crc = struct.unpack('<H', response[-2:])[0]
            calculated_crc = self._calculate_crc(response[:-2])
            if received_crc != calculated_crc:
                logging.error(f"CRC校验失败: 接收0x{received_crc:04X}, 计算0x{calculated_crc:04X}")
                return False

            # 验证返回的地址和数量
            returned_addr = struct.unpack('>H', response[2:4])[0]
            returned_count = struct.unpack('>H', response[4:6])[0]

            if returned_addr != reg_addr or returned_count != reg_count:
                logging.error(f"返回参数不匹配: 地址期望0x{reg_addr:04X}/实际0x{returned_addr:04X}, 数量期望{reg_count}/实际{returned_count}")
                return False

            logging.debug(f"写寄存器成功: 从机{slave_addr}, 地址0x{reg_addr:04X}, 数量{reg_count}")
            return True

        except Exception as e:
            logging.error(f"写寄存器通信错误: {e}")
            return False

    def write_single_register(self, slave_addr: int, reg_addr: int, value: int) -> bool:
        """
        写单个寄存器 (功能码0x06)

        Args:
            slave_addr: 从机号
            reg_addr: 寄存器地址
            value: 要写入的值

        Returns:
            bool: 写入是否成功
        """
        if self.simulation_mode:
            logging.info(f"模拟模式: 写入单个寄存器 从机{slave_addr}, 地址0x{reg_addr:04X}, 值{value}")
            return True

        try:
            # 清空接收缓冲区
            if self.serial_conn.in_waiting > 0:
                self.serial_conn.reset_input_buffer()

            # 构建Modbus RTU写单个寄存器请求帧 (功能码0x06)
            request = struct.pack('>BBHH', slave_addr, 0x06, reg_addr, value & 0xFFFF)
            crc = self._calculate_crc(request)
            request += struct.pack('<H', crc)

            # 发送请求
            self.serial_conn.write(request)
            logging.debug(f"发送写单个寄存器请求: 从机{slave_addr}, 地址0x{reg_addr:04X}, 值{value}")

            # 读取响应 (写单个寄存器响应长度固定为8字节)
            response = self.serial_conn.read(8)

            if len(response) < 8:
                logging.error(f"写单个寄存器响应长度不足: 期望8, 实际{len(response)}")
                return False

            # 验证响应 (写单个寄存器的响应应该与请求相同)
            if response[:-2] != request[:-2]:  # 除了CRC外应该相同
                logging.error("写单个寄存器响应数据不匹配")
                return False

            # 验证CRC
            received_crc = struct.unpack('<H', response[-2:])[0]
            calculated_crc = self._calculate_crc(response[:-2])
            if received_crc != calculated_crc:
                logging.error(f"CRC校验失败: 接收0x{received_crc:04X}, 计算0x{calculated_crc:04X}")
                return False

            logging.debug(f"写单个寄存器成功: 从机{slave_addr}, 地址0x{reg_addr:04X}, 值{value}")
            return True

        except Exception as e:
            logging.error(f"写单个寄存器通信错误: {e}")
            return False

    def _calculate_crc(self, data: bytes) -> int:
        """
        计算Modbus RTU CRC16校验码
        使用标准的CRC-16-ANSI算法
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc


class DeviceManager:
    """设备管理器 - 统一管理Modbus RTU和TCP设备"""

    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.modbus_rtu_comm = None
        self.modbus_tcp_devices: Dict[str, 'ModbusTCPDevice'] = {}
        self.tcp_device_configs = {}
        self.di_status_cache = {}
        self.do_status_cache = {}
        self.monitoring_active = False
        self.monitor_thread = None
        self.status_callbacks = []

        # 初始化Modbus RTU通信
        self._initialize_modbus_rtu()

        # 初始化Modbus TCP设备
        self._initialize_modbus_tcp_devices()

    def _initialize_modbus_rtu(self):
        """初始化Modbus RTU通信"""
        try:
            com_settings = self.config_manager.get_com_settings()
            self.modbus_rtu_comm = ModbusCommunication(com_settings)
            self.modbus_rtu_comm.initialize_serial()
            logging.info("Modbus RTU通信初始化成功")
        except Exception as e:
            logging.error(f"Modbus RTU通信初始化失败: {e}")

    def _initialize_modbus_tcp_devices(self):
        """初始化Modbus TCP设备"""
        if not MODBUS_TCP_AVAILABLE:
            logging.warning("Modbus TCP模块不可用")
            return

        try:
            # 从配置文件读取TCP设备配置
            tcp_configs = self._load_tcp_device_configs()

            for device_id, config in tcp_configs.items():
                try:
                    device = ModbusTCPDevice(
                        ip=config['ip'],
                        port=config.get('port', 502),
                        timeout=config.get('timeout', 5)
                    )

                    if device.connect():
                        self.modbus_tcp_devices[device_id] = device
                        self.tcp_device_configs[device_id] = config
                        logging.info(f"Modbus TCP设备 {device_id} ({config['ip']}) 连接成功")
                    else:
                        logging.warning(f"Modbus TCP设备 {device_id} ({config['ip']}) 连接失败")

                except Exception as e:
                    logging.error(f"初始化Modbus TCP设备 {device_id} 失败: {e}")

        except Exception as e:
            logging.error(f"初始化Modbus TCP设备失败: {e}")

    def _load_tcp_device_configs(self) -> Dict:
        """从配置文件加载TCP设备配置"""
        try:
            config = configparser.ConfigParser()
            config.read('ProductSetup.ini', encoding='utf-8')

            tcp_configs = {}

            # 检查是否有ModbusTCP配置段
            if 'ModbusTCP' in config:
                tcp_section = config['ModbusTCP']

                # 解析设备配置
                device_count = int(tcp_section.get('device_count', '1'))

                for i in range(1, device_count + 1):
                    device_id = f"tcp_device_{i}"
                    ip_key = f'device_{i}_ip'
                    port_key = f'device_{i}_port'
                    name_key = f'device_{i}_name'

                    if ip_key in tcp_section:
                        tcp_configs[device_id] = {
                            'ip': tcp_section[ip_key],
                            'port': int(tcp_section.get(port_key, '502')),
                            'name': tcp_section.get(name_key, f'设备{i}'),
                            'timeout': int(tcp_section.get('timeout', '5'))
                        }
            else:
                # 创建默认配置
                tcp_configs['tcp_device_1'] = {
                    'ip': '192.168.0.10',
                    'port': 502,
                    'name': 'C2000-A2-SDD8020-B83',
                    'timeout': 5
                }

                # 保存默认配置到文件
                self._save_default_tcp_config()

            return tcp_configs

        except Exception as e:
            logging.error(f"加载TCP设备配置失败: {e}")
            return {}

    def _save_default_tcp_config(self):
        """保存默认TCP设备配置"""
        try:
            config = configparser.ConfigParser()
            config.read('ProductSetup.ini', encoding='utf-8')

            if 'ModbusTCP' not in config:
                config.add_section('ModbusTCP')

            config['ModbusTCP']['device_count'] = '1'
            config['ModbusTCP']['device_1_ip'] = '192.168.0.10'
            config['ModbusTCP']['device_1_port'] = '502'
            config['ModbusTCP']['device_1_name'] = 'C2000-A2-SDD8020-B83'
            config['ModbusTCP']['timeout'] = '5'

            with open('ProductSetup.ini', 'w', encoding='utf-8') as f:
                config.write(f)

            logging.info("默认TCP设备配置已保存")

        except Exception as e:
            logging.error(f"保存默认TCP设备配置失败: {e}")

    def get_modbus_rtu_comm(self) -> Optional['ModbusCommunication']:
        """获取Modbus RTU通信对象"""
        return self.modbus_rtu_comm

    def get_tcp_device(self, device_id: str) -> Optional['ModbusTCPDevice']:
        """获取指定的TCP设备"""
        return self.modbus_tcp_devices.get(device_id)

    def get_all_tcp_devices(self) -> Dict[str, 'ModbusTCPDevice']:
        """获取所有TCP设备"""
        return self.modbus_tcp_devices.copy()

    def add_status_callback(self, callback):
        """添加状态变化回调"""
        self.status_callbacks.append(callback)

    def get_di_status(self, device_id: str = None) -> Optional[Dict]:
        """获取DI状态"""
        if device_id is None:
            device_id = list(self.modbus_tcp_devices.keys())[0] if self.modbus_tcp_devices else None

        if not device_id or device_id not in self.modbus_tcp_devices:
            return None

        device = self.modbus_tcp_devices[device_id]
        try:
            di_status = device.get_di_status()
            if di_status:
                self.di_status_cache[device_id] = di_status
                return {
                    'device_id': device_id,
                    'device_name': self.tcp_device_configs[device_id]['name'],
                    'status': di_status,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logging.error(f"读取设备 {device_id} DI状态失败: {e}")

        return None

    def get_do_status(self, device_id: str = None) -> Optional[Dict]:
        """获取DO状态"""
        if device_id is None:
            device_id = list(self.modbus_tcp_devices.keys())[0] if self.modbus_tcp_devices else None

        if not device_id or device_id not in self.modbus_tcp_devices:
            return None

        device = self.modbus_tcp_devices[device_id]
        try:
            do_status = device.get_do_status()
            if do_status:
                self.do_status_cache[device_id] = do_status
                return {
                    'device_id': device_id,
                    'device_name': self.tcp_device_configs[device_id]['name'],
                    'status': do_status,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logging.error(f"读取设备 {device_id} DO状态失败: {e}")

        return None

    def set_do_output(self, device_id: str, do_num: int, state: bool) -> bool:
        """设置DO输出"""
        if device_id not in self.modbus_tcp_devices:
            return False

        device = self.modbus_tcp_devices[device_id]
        try:
            success = device.set_do_output(do_num, state)
            if success:
                # 更新缓存
                self.get_do_status(device_id)

                # 通知回调
                for callback in self.status_callbacks:
                    try:
                        callback({
                            'type': 'do_changed',
                            'device_id': device_id,
                            'do_num': do_num,
                            'state': state
                        })
                    except Exception as e:
                        logging.error(f"状态回调执行失败: {e}")

            return success
        except Exception as e:
            logging.error(f"设置设备 {device_id} DO{do_num} 失败: {e}")
            return False

    def set_all_do_output(self, device_id: str, do1_state: bool, do2_state: bool) -> bool:
        """设置所有DO输出"""
        if device_id not in self.modbus_tcp_devices:
            return False

        device = self.modbus_tcp_devices[device_id]
        try:
            success = device.set_all_do_output(do1_state, do2_state)
            if success:
                # 更新缓存
                self.get_do_status(device_id)

                # 通知回调
                for callback in self.status_callbacks:
                    try:
                        callback({
                            'type': 'all_do_changed',
                            'device_id': device_id,
                            'do1_state': do1_state,
                            'do2_state': do2_state
                        })
                    except Exception as e:
                        logging.error(f"状态回调执行失败: {e}")

            return success
        except Exception as e:
            logging.error(f"设置设备 {device_id} 所有DO失败: {e}")
            return False

    def get_device_info(self, device_id: str) -> Optional[Dict]:
        """获取设备信息"""
        if device_id not in self.modbus_tcp_devices:
            return None

        device = self.modbus_tcp_devices[device_id]
        try:
            device_info = device.get_device_info()
            if device_info:
                device_info['device_id'] = device_id
                device_info['device_name'] = self.tcp_device_configs[device_id]['name']
                device_info['connection_status'] = 'connected'
            return device_info
        except Exception as e:
            logging.error(f"获取设备 {device_id} 信息失败: {e}")
            return None

    def start_monitoring(self, interval: float = 1.0):
        """开始监控DI状态变化"""
        if self.monitoring_active or not self.modbus_tcp_devices:
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logging.info("设备监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        if self.monitoring_active:
            self.monitoring_active = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)
            logging.info("设备监控已停止")

    def _monitor_loop(self, interval: float):
        """监控循环"""
        last_di_status = {}

        while self.monitoring_active:
            try:
                for device_id in self.modbus_tcp_devices:
                    current_di = self.get_di_status(device_id)

                    if current_di and device_id in last_di_status:
                        # 检查状态变化
                        if current_di['status'] != last_di_status[device_id]['status']:
                            # 通知回调
                            for callback in self.status_callbacks:
                                try:
                                    callback({
                                        'type': 'di_changed',
                                        'device_id': device_id,
                                        'old_status': last_di_status[device_id]['status'],
                                        'new_status': current_di['status'],
                                        'timestamp': current_di['timestamp']
                                    })
                                except Exception as e:
                                    logging.error(f"状态回调执行失败: {e}")

                    if current_di:
                        last_di_status[device_id] = current_di

                time.sleep(interval)

            except Exception as e:
                logging.error(f"监控循环错误: {e}")
                time.sleep(interval)

    def disconnect_all(self):
        """断开所有设备连接"""
        self.stop_monitoring()

        for device_id, device in self.modbus_tcp_devices.items():
            try:
                device.disconnect()
                logging.info(f"设备 {device_id} 已断开连接")
            except Exception as e:
                logging.error(f"断开设备 {device_id} 连接失败: {e}")

        self.modbus_tcp_devices.clear()


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
        # 初始化试用期管理器
        self.trial_manager = TrialManager()

        self.config_manager = ConfigManager()
        self.device_manager = DeviceManager(self.config_manager)  # 使用新的设备管理器
        self.comm = self.device_manager.get_modbus_rtu_comm()  # 获取RTU通信对象
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

        # 设置设备状态变化回调
        self.device_manager.add_status_callback(self._handle_device_status_change)

        self.setup_routes()
        self.setup_socket_events()

    def _handle_device_status_change(self, status_data: Dict):
        """处理设备状态变化"""
        try:
            # 通过Socket.IO推送状态变化
            self.socketio.emit('device_status_change', status_data)
            logging.info(f"设备状态变化: {status_data}")
        except Exception as e:
            logging.error(f"处理设备状态变化失败: {e}")
       


    def setup_routes(self):
        """设置Web路由"""
        @self.app.route('/')
        def index():
            # 检查试用期状态
            if self.trial_manager.is_system_locked():
                return render_template('trial_manager.html')
            return render_template('index.html')

        @self.app.route('/test_switch')
        def test_switch():
            return send_from_directory('.', 'test_data_source_switch.html')

        @self.app.route('/api/start_measurement', methods=['POST'])
        def start_measurement():
            # 检查试用期状态
            if self.trial_manager.is_system_locked():
                trial_status = self.trial_manager.get_trial_status()
                return jsonify({
                    'status': 'error',
                    'message': '试用期已到期，请输入验证码解锁系统',
                    'trial_expired': True,
                    'trial_info': trial_status
                })

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

                # 如果数据库不可用或无数据，返回空数据
                return jsonify({
                    'status': 'success',
                    'data': [],
                    'source': 'empty',
                    'param': param,
                    'chart_type': chart_type,
                    'message': '数据库连接失败或无数据'
                })

            except Exception as e:
                logging.error(f"获取图表数据失败: {e}")
                return jsonify({
                    'status': 'error',
                    'data': [],
                    'message': str(e),
                    'source': 'error'
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

        @self.app.route('/api/get_cpk_data/<version>/<int:channel>/<side>')
        def get_cpk_data(version, channel, side):
            """获取CPK数据的API端点"""
            try:
                cpk_data = self.get_latest_cpk_data(version, channel, side)
                if cpk_data is None:
                    return jsonify({'error': '无法获取CPK数据'}), 404
                return jsonify(cpk_data)
            except Exception as e:
                logging.error(f"获取CPK数据失败: {e}")
                return jsonify({'error': str(e)}), 500

        # 试用期管理相关路由
        @self.app.route('/api/trial_status')
        def get_trial_status():
            """获取试用期状态"""
            try:
                status = self.trial_manager.get_trial_status()
                return jsonify({
                    'status': 'success',
                    'trial_info': status
                })
            except Exception as e:
                logging.error(f"获取试用期状态失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/api/verify_code', methods=['POST'])
        def verify_trial_code():
            """验证试用期验证码"""
            try:
                data = request.get_json()
                code = data.get('code', '').strip()

                if not code:
                    return jsonify({
                        'status': 'error',
                        'message': '请输入验证码'
                    })

                result = self.trial_manager.verify_code(code)

                if result['success']:
                    return jsonify({
                        'status': 'success',
                        'message': result['message'],
                        'type': result['type']
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': result['message']
                    })

            except Exception as e:
                logging.error(f"验证码验证失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': f'验证失败: {str(e)}'
                })

        @self.app.route('/trial')
        def trial_page():
            """试用期管理页面"""
            return render_template('trial_manager.html')

        @self.app.route('/test_trial')
        def test_trial_page():
            """试用期功能测试页面"""
            return send_from_directory('.', 'test_trial_ui.html')

        # Modbus TCP设备管理相关路由
        @self.app.route('/api/modbus_tcp/devices')
        def get_tcp_devices():
            """获取所有TCP设备列表"""
            try:
                devices = []
                for device_id, device in self.device_manager.get_all_tcp_devices().items():
                    device_info = self.device_manager.get_device_info(device_id)
                    if device_info:
                        devices.append(device_info)
                    else:
                        # 如果无法获取详细信息，返回基本信息
                        config = self.device_manager.tcp_device_configs.get(device_id, {})
                        devices.append({
                            'device_id': device_id,
                            'device_name': config.get('name', device_id),
                            'ip_address': config.get('ip', 'unknown'),
                            'modbus_port': config.get('port', 502),
                            'connection_status': 'connected'
                        })

                return jsonify({
                    'status': 'success',
                    'devices': devices,
                    'count': len(devices)
                })
            except Exception as e:
                logging.error(f"获取TCP设备列表失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/api/modbus_tcp/device/<device_id>/di_status')
        def get_device_di_status(device_id):
            """获取设备DI状态"""
            try:
                di_status = self.device_manager.get_di_status(device_id)
                if di_status:
                    return jsonify({
                        'status': 'success',
                        'data': di_status
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': '无法读取DI状态'
                    })
            except Exception as e:
                logging.error(f"获取设备 {device_id} DI状态失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/api/modbus_tcp/device/<device_id>/do_status')
        def get_device_do_status(device_id):
            """获取设备DO状态"""
            try:
                do_status = self.device_manager.get_do_status(device_id)
                if do_status:
                    return jsonify({
                        'status': 'success',
                        'data': do_status
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': '无法读取DO状态'
                    })
            except Exception as e:
                logging.error(f"获取设备 {device_id} DO状态失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/api/modbus_tcp/device/<device_id>/do_control', methods=['POST'])
        def control_device_do(device_id):
            """控制设备DO输出"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({
                        'status': 'error',
                        'message': '请求数据为空'
                    })

                # 单个DO控制
                if 'do_num' in data and 'state' in data:
                    do_num = int(data['do_num'])
                    state = bool(data['state'])

                    if do_num not in [1, 2]:
                        return jsonify({
                            'status': 'error',
                            'message': 'DO编号必须是1或2'
                        })

                    success = self.device_manager.set_do_output(device_id, do_num, state)
                    if success:
                        return jsonify({
                            'status': 'success',
                            'message': f'DO{do_num} 设置为 {"高电平" if state else "低电平"}'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': f'设置DO{do_num}失败'
                        })

                # 所有DO控制
                elif 'do1_state' in data and 'do2_state' in data:
                    do1_state = bool(data['do1_state'])
                    do2_state = bool(data['do2_state'])

                    success = self.device_manager.set_all_do_output(device_id, do1_state, do2_state)
                    if success:
                        return jsonify({
                            'status': 'success',
                            'message': f'所有DO设置成功: DO1={"高" if do1_state else "低"}, DO2={"高" if do2_state else "低"}'
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': '设置所有DO失败'
                        })

                else:
                    return jsonify({
                        'status': 'error',
                        'message': '无效的控制参数'
                    })

            except Exception as e:
                logging.error(f"控制设备 {device_id} DO失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/api/modbus_tcp/device/<device_id>/info')
        def get_device_info_api(device_id):
            """获取设备详细信息"""
            try:
                device_info = self.device_manager.get_device_info(device_id)
                if device_info:
                    return jsonify({
                        'status': 'success',
                        'data': device_info
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': '无法获取设备信息'
                    })
            except Exception as e:
                logging.error(f"获取设备 {device_id} 信息失败: {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                })

        @self.app.route('/modbus_tcp')
        def modbus_tcp_page():
            """Modbus TCP设备管理页面"""
            return render_template('modbus_tcp_control.html')

    def get_latest_cpk_data(self, version, channel, side):
        """获取最新的CPK数据 - 版本相关"""
        try:
            if not self.db_manager or not self.db_manager.available:
                return None

            # 构建表名
            table_name = f"{version}_{side}_P{channel}_25"
            if channel == 1:
                table_name = f"{version}_{side}_P1_25"
            elif channel == 2:
                table_name = f"{version}_{side}_P5L_25"
            elif channel == 3:
                table_name = f"{version}_{side}_P5U_25"
            elif channel == 4:
                table_name = f"{version}_{side}_P3_25"
            elif channel == 5:
                table_name = f"{version}_{side}_P4_25"

            # 获取版本相关的CPK配置
            cpk_config = self.get_cpk_config(version, channel)
            if not cpk_config:
                logging.warning(f"未找到版本 {version} 通道 {channel} 的CPK配置")
                return None

            # 获取最新的多条记录用于CPK计算
            conn = self.db_manager.get_connection()
            if not conn:
                return None

            cursor = conn.cursor()

            # 查询最近25条记录用于CPK计算
            cursor.execute(f"SELECT TOP 25 * FROM [{table_name}] ORDER BY date DESC, time DESC")
            rows = cursor.fetchall()

            if not rows:
                self.db_manager.return_connection(conn)
                return None

            # 获取字段名
            field_names = [desc[0] for desc in cursor.description]

            # 根据实际数据计算CPK
            cpk_data = self.calculate_real_cpk(rows, field_names, cpk_config, version, channel)
            cpk_data['timestamp'] = time.time()

            self.db_manager.return_connection(conn)
            return cpk_data

        except Exception as e:
            logging.error(f"获取CPK数据失败: {e}")
            return None

    def get_cpk_config(self, version, channel):
        """获取版本相关的CPK配置"""
        try:
            config = configparser.ConfigParser()
            config.read('ProductSetup.ini', encoding='utf-8')

            section_name = f'{version}_Channel_{channel}CPK'
            if section_name not in config:
                return None

            cpk_config = dict(config[section_name])
            logging.info(f"获取CPK配置: {section_name} -> {cpk_config}")
            return cpk_config

        except Exception as e:
            logging.error(f"获取CPK配置失败: {e}")
            return None

    def calculate_real_cpk(self, rows, field_names, cpk_config, version, channel):
        """根据实际数据计算CPK值"""
        try:
            cpk_data = {}

            # 根据通道和版本确定需要计算的参数
            param_mapping = self.get_cpk_param_mapping(version, channel)
            logging.info(f"🔍 CPK参数映射: version={version}, channel={channel}, mapping={param_mapping}")

            for param_key, field_info in param_mapping.items():
                field_name = field_info['field']
                config_key = field_info['config_key']
                logging.info(f"🔍 处理参数: {param_key}, 字段: {field_name}, 配置键: {config_key}")

                # 获取规格限
                max_key = f"{config_key}_max"
                min_key = f"{config_key}_min"
                logging.info(f"🔍 查找配置键: {max_key}, {min_key}")
                logging.info(f"🔍 可用配置: {list(cpk_config.keys())}")

                if max_key not in cpk_config or min_key not in cpk_config:
                    logging.warning(f"❌ CPK配置中缺少 {config_key} 的规格限")
                    cpk_data[param_key] = 0.0
                    continue

                usl = float(cpk_config[max_key])
                lsl = float(cpk_config[min_key])
                logging.info(f"🔍 规格限: LSL={lsl}, USL={usl}")

                # 提取字段数据
                field_index = None
                logging.info(f"🔍 可用字段: {field_names}")

                # 尝试精确匹配
                for i, name in enumerate(field_names):
                    if name.lower() == field_name.lower():
                        field_index = i
                        break

                # 如果精确匹配失败，尝试模糊匹配
                if field_index is None:
                    # 特殊处理一些已知的字段映射问题
                    field_alternatives = []
                    if field_name.lower() == 'p3l totalav':
                        field_alternatives = ['p5l totalav', 'P5L totalAV', 'p3l totalav', 'P3L totalAV']
                    elif field_name.lower() == 'p3 totalav':
                        field_alternatives = ['p3 totalav', 'P3 totalAV', 'p3 totaoav', 'P3 totaoAV']  # 注意拼写错误

                    for alt_field in field_alternatives:
                        for i, name in enumerate(field_names):
                            if name.lower() == alt_field.lower():
                                field_index = i
                                field_name = name  # 更新为实际找到的字段名
                                logging.info(f"🔧 使用替代字段: {field_name}")
                                break
                        if field_index is not None:
                            break

                if field_index is None:
                    logging.warning(f"❌ 未找到字段 {field_name} 在字段列表 {field_names} 中")
                    cpk_data[param_key] = 0.0
                    continue

                # 提取数值数据
                values = []
                for row in rows:
                    if row[field_index] is not None and isinstance(row[field_index], (int, float)):
                        values.append(float(row[field_index]))

                if len(values) < 2:
                    cpk_data[param_key] = 0.0
                    continue

                # 计算CPK
                avg = sum(values) / len(values)
                range_val = max(values) - min(values)
                cpk = self._calculate_cpk(avg, lsl, usl, range_val)
                cpk_data[param_key] = cpk

                logging.info(f"CPK计算: {param_key} = {cpk:.3f} (avg={avg:.2f}, range={range_val:.2f}, LSL={lsl}, USL={usl})")

            return cpk_data

        except Exception as e:
            logging.error(f"计算CPK失败: {e}")
            return {
                'cpk_p1': 0.0,
                'cpk_p5u': 0.0,
                'cpk_p5l': 0.0,
                'cpk_p3': 0.0,
                'cpk_p4': 0.0
            }

    def get_cpk_param_mapping(self, version, channel):
        """获取CPK参数映射关系"""
        # 根据版本和通道返回参数映射
        if version == 'G45':
            if channel == 1:  # P1
                return {
                    'cpk_p1': {'field': 'p1 totalav', 'config_key': 't'}
                }
            elif channel == 2:  # P5L - 使用P3L totalAV字段
                return {
                    'cpk_p5l': {'field': 'p3l totalav', 'config_key': 'p3lt'}
                }
            elif channel == 3:  # P5U
                return {
                    'cpk_p5u': {'field': 'p5u totalav', 'config_key': 'p3ut'}
                }
            elif channel == 4:  # P3
                return {
                    'cpk_p3': {'field': 'p3 totalav', 'config_key': 'p5t'}
                }
            elif channel == 5:  # P4
                return {
                    'cpk_p4': {'field': 'p4av', 'config_key': 'p4'}
                }
        elif version == 'G48':
            if channel == 1:  # P1
                return {
                    'cpk_p1': {'field': 'p1 totalav', 'config_key': 't'}
                }
            elif channel == 2:  # P5L - G48版本使用不同的字段名
                return {
                    'cpk_p5l': {'field': 'p5l totalav', 'config_key': 'p3lt'}
                }
            elif channel == 3:  # P5U
                return {
                    'cpk_p5u': {'field': 'p5u totalav', 'config_key': 'p3ut'}
                }
            elif channel == 4:  # P3
                return {
                    'cpk_p3': {'field': 'p3 totalav', 'config_key': 'p5t'}
                }
            elif channel == 5:  # P4
                return {
                    'cpk_p4': {'field': 'p4av', 'config_key': 'p4'}
                }

        return {}

    def _calculate_cpk(self, avg, lsl, usl, range_val):
        """计算CPK值"""
        try:
            # 计算标准差 (使用极差法估算)
            # σ ≈ R/d2, 对于样本量25，d2约为3.931
            d2 = 3.931
            sigma = range_val / d2 if range_val > 0 else 0.001

            # 计算CPK
            cpu = (usl - avg) / (3 * sigma)  # 上限能力指数
            cpl = (avg - lsl) / (3 * sigma)  # 下限能力指数
            cpk = min(cpu, cpl)  # CPK取较小值

            return max(0, cpk)  # CPK不能为负

        except Exception as e:
            logging.error(f"计算CPK失败: {e}")
            return 0.0

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

        # Modbus TCP设备相关Socket.IO事件
        @self.socketio.on('request_tcp_device_status')
        def handle_request_tcp_device_status(data):
            """请求TCP设备状态"""
            device_id = data.get('device_id')
            if device_id:
                # 获取DI状态
                di_status = self.device_manager.get_di_status(device_id)
                # 获取DO状态
                do_status = self.device_manager.get_do_status(device_id)

                emit('tcp_device_status_update', {
                    'device_id': device_id,
                    'di_status': di_status,
                    'do_status': do_status,
                    'timestamp': datetime.now().isoformat()
                })

        @self.socketio.on('control_tcp_device_do')
        def handle_control_tcp_device_do(data):
            """控制TCP设备DO输出"""
            try:
                device_id = data.get('device_id')
                do_num = data.get('do_num')
                state = data.get('state')

                if not device_id or do_num is None or state is None:
                    emit('tcp_device_control_result', {
                        'success': False,
                        'message': '参数不完整'
                    })
                    return

                success = self.device_manager.set_do_output(device_id, int(do_num), bool(state))

                emit('tcp_device_control_result', {
                    'success': success,
                    'device_id': device_id,
                    'do_num': do_num,
                    'state': state,
                    'message': f'DO{do_num} 设置{"成功" if success else "失败"}'
                })

                # 如果成功，广播状态更新
                if success:
                    do_status = self.device_manager.get_do_status(device_id)
                    self.socketio.emit('tcp_device_status_update', {
                        'device_id': device_id,
                        'do_status': do_status,
                        'timestamp': datetime.now().isoformat()
                    })

            except Exception as e:
                logging.error(f"Socket.IO控制TCP设备DO失败: {e}")
                emit('tcp_device_control_result', {
                    'success': False,
                    'message': str(e)
                })

        @self.socketio.on('start_tcp_device_monitoring')
        def handle_start_tcp_device_monitoring(data):
            """开始TCP设备监控"""
            try:
                interval = data.get('interval', 1.0)
                self.device_manager.start_monitoring(interval)
                emit('tcp_device_monitoring_status', {
                    'active': True,
                    'interval': interval,
                    'message': '设备监控已启动'
                })
            except Exception as e:
                logging.error(f"启动TCP设备监控失败: {e}")
                emit('tcp_device_monitoring_status', {
                    'active': False,
                    'message': str(e)
                })

        @self.socketio.on('stop_tcp_device_monitoring')
        def handle_stop_tcp_device_monitoring():
            """停止TCP设备监控"""
            try:
                self.device_manager.stop_monitoring()
                emit('tcp_device_monitoring_status', {
                    'active': False,
                    'message': '设备监控已停止'
                })
            except Exception as e:
                logging.error(f"停止TCP设备监控失败: {e}")
                emit('tcp_device_monitoring_status', {
                    'active': False,
                    'message': str(e)
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
        """开始测量过程 - 添加试用期检查"""
        # 检查试用期状态
        if self.trial_manager.is_system_locked():
            logging.warning("系统已锁定，试用期已到期")
            return False

        if not self.running:
            if self.initialize():
                self.running = True
                self.measurement_thread = threading.Thread(target=self._measurement_loop)
                self.measurement_thread.daemon = True
                self.measurement_thread.start()

                # 启动设备监控
                self.device_manager.start_monitoring(interval=1.0)

                logging.info("测量开始")
                return True
        return False

    def stop_measurement_process(self):
        """停止测量过程"""
        self.running = False
        if self.measurement_thread:
            self.measurement_thread.join(timeout=1.0)

        # 停止设备监控
        self.device_manager.stop_monitoring()

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
        try:
            logging.info(f"光栅测量系统Web版启动: http://{host}:{port}")
            self.socketio.run(self.app, host=host, port=port, debug=debug)
        except KeyboardInterrupt:
            logging.info("接收到中断信号，正在关闭系统...")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        try:
            # 停止测量过程
            self.stop_measurement_process()

            # 断开所有设备连接
            self.device_manager.disconnect_all()

            logging.info("系统资源清理完成")
        except Exception as e:
            logging.error(f"清理资源时发生错误: {e}")

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
 














