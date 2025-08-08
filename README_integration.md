# Modbus TCP设备集成到光栅测量系统

本文档说明如何使用集成了Modbus TCP设备功能的光栅测量系统。

## 系统概述

光栅测量系统现已集成Modbus TCP设备支持，可以同时进行：
- 光栅测量数据采集（Modbus RTU）
- Modbus TCP设备的DI状态监控和DO控制

## 文件结构

```
G58_OpticalGratingMeasuringSystem/
├── optical_grating_web_system.py      # 主系统文件（已集成）
├── modbus_device.py                   # Modbus TCP通讯模块
├── test_modbus_device.py              # Modbus设备测试程序
├── test_integration.py                # 集成测试脚本
├── ProductSetup_example.ini           # 配置文件示例
├── README_modbus.md                   # Modbus模块说明
├── README_integration.md              # 本文档
└── templates/
    ├── index.html                     # 主页面（已添加Modbus TCP按钮）
    └── modbus_tcp_control.html        # Modbus TCP控制页面
```

## 快速开始

### 1. 配置设备

编辑 `ProductSetup.ini` 文件，添加Modbus TCP设备配置：

```ini
[ModbusTCP]
device_count = 1
device_1_ip = 192.168.0.10
device_1_port = 502
device_1_name = C2000-A2-SDD8020-B83
timeout = 5
```

### 2. 启动系统

```bash
python optical_grating_web_system.py
```

### 3. 访问界面

- **主系统**: http://localhost:5000
- **Modbus TCP控制**: http://localhost:5000/modbus_tcp

## 功能特性

### 1. 设备管理
- 自动发现和连接配置的Modbus TCP设备
- 设备状态监控和连接管理
- 支持多设备同时管理

### 2. DI状态监控
- 实时读取DI1-DI8状态
- 状态变化自动推送
- 历史状态记录

### 3. DO输出控制
- 单个DO控制（DO1、DO2）
- 批量DO控制
- 实时状态反馈

### 4. Web界面
- 现代化响应式设计
- 实时状态显示
- 直观的控制面板

### 5. API接口
- RESTful API设计
- JSON数据格式
- 完整的错误处理

## API接口说明

### 获取设备列表
```http
GET /api/modbus_tcp/devices
```

### 获取DI状态
```http
GET /api/modbus_tcp/device/{device_id}/di_status
```

### 获取DO状态
```http
GET /api/modbus_tcp/device/{device_id}/do_status
```

### 控制DO输出
```http
POST /api/modbus_tcp/device/{device_id}/do_control
Content-Type: application/json

{
    "do_num": 1,
    "state": true
}
```

### 获取设备信息
```http
GET /api/modbus_tcp/device/{device_id}/info
```

## Socket.IO事件

### 客户端发送事件
- `request_tcp_device_status` - 请求设备状态
- `control_tcp_device_do` - 控制DO输出
- `start_tcp_device_monitoring` - 启动监控
- `stop_tcp_device_monitoring` - 停止监控

### 服务器推送事件
- `device_status_change` - 设备状态变化
- `tcp_device_status_update` - 设备状态更新
- `tcp_device_control_result` - 控制结果
- `tcp_device_monitoring_status` - 监控状态

## 测试和验证

### 1. 单元测试
```bash
# 测试Modbus TCP模块
python test_modbus_device.py

# 交互式测试
python test_modbus_device.py

# 演示测试
python test_modbus_device.py demo
```

### 2. 集成测试
```bash
# 运行集成测试
python test_integration.py
```

### 3. 手动测试
1. 启动系统
2. 访问 http://localhost:5000/modbus_tcp
3. 查看设备状态
4. 测试DO控制功能

## 配置说明

### Modbus TCP设备配置
在 `ProductSetup.ini` 中配置：

```ini
[ModbusTCP]
device_count = 2                    # 设备数量
device_1_ip = 192.168.0.10         # 设备1 IP地址
device_1_port = 502                # 设备1 端口
device_1_name = Device1            # 设备1 名称
device_2_ip = 192.168.0.11         # 设备2 IP地址
device_2_port = 502                # 设备2 端口
device_2_name = Device2            # 设备2 名称
timeout = 5                        # 连接超时时间
```

### 网络配置
确保：
1. 设备IP地址正确
2. 网络连通性良好
3. 防火墙允许502端口通信

## 故障排除

### 1. 连接问题
- 检查设备IP地址和端口
- 验证网络连接
- 检查防火墙设置

### 2. 功能问题
- 查看系统日志
- 运行集成测试
- 检查设备配置

### 3. 性能问题
- 调整监控间隔
- 检查网络延迟
- 优化设备响应时间

## 扩展开发

### 添加新设备类型
1. 继承 `ModbusTCPDevice` 类
2. 实现特定的寄存器映射
3. 更新设备管理器

### 自定义Web界面
1. 修改 `modbus_tcp_control.html`
2. 添加新的CSS样式
3. 扩展JavaScript功能

### 集成其他协议
1. 创建新的通讯模块
2. 更新设备管理器
3. 添加相应的Web接口

## 技术支持

如遇问题，请：
1. 查看系统日志文件
2. 运行诊断测试
3. 检查配置文件
4. 联系技术支持

## 版本历史

- v1.0 - 初始集成版本
- 支持C2000-A2-SDD8020-B83设备
- 完整的Web界面和API
- 实时监控和控制功能
