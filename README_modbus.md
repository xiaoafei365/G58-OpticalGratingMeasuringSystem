# Modbus TCP设备通讯模块

本模块用于与C2000-A2-SDD8020-B83 Modbus TCP设备进行通讯，支持DI状态读取和DO控制。

## 文件说明

- `modbus_device.py` - 核心Modbus TCP通讯模块
- `test_modbus_device.py` - 测试和演示程序
- `requirements.txt` - 依赖包列表

## 设备信息

- **设备型号**: C2000-A2-SDD8020-B83
- **默认IP地址**: 192.168.0.10
- **默认端口**: 502
- **协议**: Modbus TCP

## 功能特性

### 支持的功能
- ✅ DI状态读取 (DI1-DI8)
- ✅ DO状态读取 (DO1-DO2)
- ✅ DO输出控制 (DO1-DO2)
- ✅ 设备信息读取 (MAC地址、版本号、IP等)
- ✅ 连接管理和错误处理
- ✅ 上下文管理器支持
- ✅ 实时监控功能

### 寄存器地址映射

| 功能 | 寄存器地址 | 类型 | 说明 |
|------|------------|------|------|
| MAC地址 | 40100-40102 | 保持寄存器 | 设备MAC地址 |
| 设备型号 | 40103 | 保持寄存器 | 设备型号 |
| 版本号 | 40104 | 保持寄存器 | 固件版本 |
| IP地址 | 40105-40106 | 保持寄存器 | 设备IP地址 |
| Modbus端口 | 40107 | 保持寄存器 | Modbus TCP端口 |
| DO状态 | 100 | 保持寄存器 | DO1-DO2当前状态 |
| DO控制 | 102 | 保持寄存器 | DO1-DO2控制 |
| DI状态 | 10200 | 输入寄存器 | DI1-DI8当前状态 |
| DI滤波 | 40300-40307 | 保持寄存器 | DI滤波参数 |

## 使用方法

### 1. 基本使用

```python
from modbus_device import ModbusTCPDevice

# 创建设备实例
device = ModbusTCPDevice(ip="192.168.0.10", port=502)

# 连接设备
if device.connect():
    # 读取DI状态
    di_status = device.get_di_status()
    print("DI状态:", di_status)
    
    # 控制DO输出
    device.set_do_output(1, True)   # DO1输出高电平
    device.set_do_output(2, False)  # DO2输出低电平
    
    # 断开连接
    device.disconnect()
```

### 2. 使用上下文管理器

```python
from modbus_device import ModbusTCPDevice

# 使用with语句自动管理连接
with ModbusTCPDevice(ip="192.168.0.10", port=502) as device:
    # 获取设备信息
    info = device.get_device_info()
    print("设备信息:", info)
    
    # 读取所有状态
    di_status = device.get_di_status()
    do_status = device.get_do_status()
    
    # 控制输出
    device.set_all_do_output(True, False)  # DO1=高, DO2=低
```

### 3. 在主程序中集成

```python
from test_modbus_device import ModbusDeviceManager

# 创建设备管理器
manager = ModbusDeviceManager(ip="192.168.0.10", port=502)

# 连接设备
if manager.connect_device():
    # 获取设备信息
    manager.get_device_info()
    
    # 读取DI状态
    di_status = manager.read_di_status()
    
    # 控制DO输出
    manager.control_do(1, True)
    
    # 开始监控DI状态变化
    manager.start_monitoring(interval=0.5)
    
    # ... 其他业务逻辑 ...
    
    # 停止监控并断开连接
    manager.stop_monitoring()
    manager.disconnect_device()
```

## 运行测试

### 交互式测试
```bash
python test_modbus_device.py
```

### 演示测试
```bash
python test_modbus_device.py demo
```

### 直接运行模块
```bash
python modbus_device.py
```

## API参考

### ModbusTCPDevice类

#### 构造函数
```python
ModbusTCPDevice(ip="192.168.0.10", port=502, timeout=5)
```

#### 连接管理
- `connect()` - 连接设备
- `disconnect()` - 断开连接

#### DI/DO操作
- `get_di_status()` - 获取所有DI状态
- `get_do_status()` - 获取所有DO状态
- `set_do_output(do_num, state)` - 设置单个DO输出
- `set_all_do_output(do1_state, do2_state)` - 设置所有DO输出

#### 设备信息
- `get_device_info()` - 获取设备信息

#### 底层Modbus操作
- `read_holding_registers(address, count)` - 读取保持寄存器
- `read_input_registers(address, count)` - 读取输入寄存器
- `write_single_register(address, value)` - 写单个寄存器

## 错误处理

模块包含完整的错误处理机制：

- 连接超时处理
- Modbus协议错误检测
- 网络异常处理
- 数据格式验证
- 详细的日志记录

## 注意事项

1. **网络配置**: 确保设备IP地址和端口配置正确
2. **防火墙**: 确保502端口未被防火墙阻止
3. **设备状态**: 确保设备正常运行且网络连接正常
4. **并发访问**: 避免多个程序同时访问同一设备
5. **资源管理**: 使用完毕后及时断开连接

## 故障排除

### 常见问题

1. **连接失败**
   - 检查设备IP地址和端口
   - 检查网络连接
   - 检查防火墙设置

2. **读取数据失败**
   - 检查寄存器地址是否正确
   - 检查设备是否支持该功能
   - 检查网络稳定性

3. **控制失败**
   - 检查DO控制权限
   - 检查寄存器写入权限
   - 检查设备工作模式

### 调试方法

启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 扩展功能

如需添加更多功能，可以扩展`ModbusTCPDevice`类：

- 添加更多寄存器读写方法
- 实现批量操作
- 添加数据缓存机制
- 实现自动重连功能
- 添加数据记录功能
