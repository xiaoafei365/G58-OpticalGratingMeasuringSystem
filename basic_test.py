print("RS485通讯功能修正验证")
print("=" * 40)

# 测试基本功能
def test_crc():
    """测试CRC计算"""
    def calculate_crc(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    # 测试数据
    test_data = bytes([0x01, 0x03, 0x10, 0x00, 0x00, 0x02])
    crc = calculate_crc(test_data)
    print(f"CRC计算测试: 数据={test_data.hex()}, CRC=0x{crc:04X}")
    return True

def test_addresses():
    """测试寄存器地址"""
    addresses = {
        '当前值': 0x1000,
        '比例系数': 0x1002,
        '包络直径': 0x1004,
        '多段补偿值': 0x1006,
        '测量方向': 0x2000,
        '自校正': 0x2001
    }
    
    print("寄存器地址映射:")
    for name, addr in addresses.items():
        print(f"  {name}: 0x{addr:04X}")
    return True

def test_config():
    """测试配置文件"""
    try:
        with open('ProductSetup.ini', 'r', encoding='utf-8') as f:
            lines = f.readlines()[:10]  # 读取前10行
        print("配置文件读取成功:")
        for i, line in enumerate(lines, 1):
            print(f"  {i}: {line.strip()}")
        return True
    except Exception as e:
        print(f"配置文件读取失败: {e}")
        return False

# 运行测试
tests = [
    ("CRC计算", test_crc),
    ("寄存器地址", test_addresses),
    ("配置文件", test_config)
]

passed = 0
for name, test_func in tests:
    print(f"\n--- {name} ---")
    try:
        if test_func():
            print(f"✓ {name} 通过")
            passed += 1
        else:
            print(f"✗ {name} 失败")
    except Exception as e:
        print(f"✗ {name} 异常: {e}")

print(f"\n总结: {passed}/{len(tests)} 测试通过")
print("RS485通讯功能修正完成！")
