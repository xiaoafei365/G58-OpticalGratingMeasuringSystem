#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus设备测试程序
演示如何在主程序中调用modbus_device模块
"""

import time
import threading
from modbus_device import ModbusTCPDevice


class ModbusDeviceManager:
    """Modbus设备管理器"""
    
    def __init__(self, ip="192.168.0.10", port=502):
        self.device = ModbusTCPDevice(ip, port)
        self.is_connected = False
        self.monitoring = False
        self.monitor_thread = None
    
    def connect_device(self) -> bool:
        """连接设备"""
        if self.device.connect():
            self.is_connected = True
            print(f"✓ 成功连接到设备 {self.device.ip}:{self.device.port}")
            return True
        else:
            print(f"✗ 连接设备失败 {self.device.ip}:{self.device.port}")
            return False
    
    def disconnect_device(self):
        """断开设备连接"""
        self.stop_monitoring()
        if self.is_connected:
            self.device.disconnect()
            self.is_connected = False
            print("✓ 设备连接已断开")
    
    def get_device_info(self):
        """获取并显示设备信息"""
        if not self.is_connected:
            print("✗ 设备未连接")
            return
        
        print("\n" + "="*50)
        print("设备信息")
        print("="*50)
        
        info = self.device.get_device_info()
        if info:
            for key, value in info.items():
                print(f"{key:15}: {value}")
        else:
            print("✗ 获取设备信息失败")
    
    def read_di_status(self):
        """读取并显示DI状态"""
        if not self.is_connected:
            print("✗ 设备未连接")
            return None
        
        di_status = self.device.get_di_status()
        if di_status:
            print("\nDI状态:")
            for di_name, state in di_status.items():
                status_text = "高电平" if state else "低电平"
                print(f"  {di_name}: {status_text}")
            return di_status
        else:
            print("✗ 读取DI状态失败")
            return None
    
    def read_do_status(self):
        """读取并显示DO状态"""
        if not self.is_connected:
            print("✗ 设备未连接")
            return None
        
        do_status = self.device.get_do_status()
        if do_status:
            print("\nDO状态:")
            for do_name, state in do_status.items():
                status_text = "高电平" if state else "低电平"
                print(f"  {do_name}: {status_text}")
            return do_status
        else:
            print("✗ 读取DO状态失败")
            return None
    
    def control_do(self, do_num: int, state: bool):
        """控制DO输出"""
        if not self.is_connected:
            print("✗ 设备未连接")
            return False
        
        state_text = "高电平" if state else "低电平"
        print(f"\n设置DO{do_num}为{state_text}...")
        
        success = self.device.set_do_output(do_num, state)
        if success:
            print(f"✓ DO{do_num}设置成功")
        else:
            print(f"✗ DO{do_num}设置失败")
        
        return success
    
    def control_all_do(self, do1_state: bool, do2_state: bool):
        """控制所有DO输出"""
        if not self.is_connected:
            print("✗ 设备未连接")
            return False
        
        do1_text = "高" if do1_state else "低"
        do2_text = "高" if do2_state else "低"
        print(f"\n设置所有DO: DO1={do1_text}, DO2={do2_text}...")
        
        success = self.device.set_all_do_output(do1_state, do2_state)
        if success:
            print("✓ 所有DO设置成功")
        else:
            print("✗ 所有DO设置失败")
        
        return success
    
    def start_monitoring(self, interval: float = 1.0):
        """开始监控DI状态"""
        if not self.is_connected:
            print("✗ 设备未连接")
            return
        
        if self.monitoring:
            print("监控已在运行中")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print(f"✓ 开始监控DI状态 (间隔: {interval}秒)")
    
    def stop_monitoring(self):
        """停止监控"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)
            print("✓ 停止监控")
    
    def _monitor_loop(self, interval: float):
        """监控循环"""
        last_di_status = None
        
        while self.monitoring:
            try:
                current_di_status = self.device.get_di_status()
                
                if current_di_status and current_di_status != last_di_status:
                    print(f"\n[{time.strftime('%H:%M:%S')}] DI状态变化:")
                    for di_name, state in current_di_status.items():
                        if last_di_status is None or last_di_status.get(di_name) != state:
                            status_text = "高电平" if state else "低电平"
                            print(f"  {di_name}: {status_text}")
                    
                    last_di_status = current_di_status.copy()
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(interval)


def interactive_test():
    """交互式测试程序"""
    print("Modbus TCP设备测试程序")
    print("="*50)
    
    # 创建设备管理器
    manager = ModbusDeviceManager()
    
    try:
        # 连接设备
        if not manager.connect_device():
            return
        
        # 获取设备信息
        manager.get_device_info()
        
        while True:
            print("\n" + "="*50)
            print("请选择操作:")
            print("1. 读取DI状态")
            print("2. 读取DO状态")
            print("3. 控制DO1")
            print("4. 控制DO2")
            print("5. 控制所有DO")
            print("6. 开始监控DI")
            print("7. 停止监控")
            print("8. 设备信息")
            print("0. 退出")
            print("="*50)
            
            choice = input("请输入选择 (0-8): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                manager.read_di_status()
            elif choice == '2':
                manager.read_do_status()
            elif choice == '3':
                state = input("DO1状态 (1=高电平, 0=低电平): ").strip() == '1'
                manager.control_do(1, state)
            elif choice == '4':
                state = input("DO2状态 (1=高电平, 0=低电平): ").strip() == '1'
                manager.control_do(2, state)
            elif choice == '5':
                do1_state = input("DO1状态 (1=高电平, 0=低电平): ").strip() == '1'
                do2_state = input("DO2状态 (1=高电平, 0=低电平): ").strip() == '1'
                manager.control_all_do(do1_state, do2_state)
            elif choice == '6':
                interval = input("监控间隔(秒，默认1): ").strip()
                interval = float(interval) if interval else 1.0
                manager.start_monitoring(interval)
            elif choice == '7':
                manager.stop_monitoring()
            elif choice == '8':
                manager.get_device_info()
            else:
                print("无效选择，请重新输入")
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序错误: {e}")
    finally:
        manager.disconnect_device()


def demo_test():
    """演示测试"""
    print("Modbus TCP设备演示程序")
    print("="*50)
    
    manager = ModbusDeviceManager()
    
    try:
        # 连接设备
        if not manager.connect_device():
            return
        
        # 获取设备信息
        manager.get_device_info()
        
        # 读取初始状态
        print("\n初始状态:")
        manager.read_di_status()
        manager.read_do_status()
        
        # DO控制演示
        print("\n开始DO控制演示...")
        
        # 控制DO1
        manager.control_do(1, True)
        time.sleep(2)
        manager.control_do(1, False)
        
        # 控制DO2
        manager.control_do(2, True)
        time.sleep(2)
        manager.control_do(2, False)
        
        # 同时控制所有DO
        manager.control_all_do(True, True)
        time.sleep(2)
        manager.control_all_do(False, False)
        
        print("\n演示完成")
        
    except Exception as e:
        print(f"演示错误: {e}")
    finally:
        manager.disconnect_device()


if __name__ == "__main__":
    # 可以选择运行交互式测试或演示测试
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo_test()
    else:
        interactive_test()
