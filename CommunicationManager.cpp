#include "CommunicationManager.h"
#include <iostream>

CommunicationManager::CommunicationManager() 
    : m_serialHandle(INVALID_HANDLE_VALUE), m_port(0), m_baudRate(9600)
{
}

CommunicationManager::~CommunicationManager()
{
    closeSerial();
}

bool CommunicationManager::initializeSerial(int port, int baudRate)
{
    m_port = port;
    m_baudRate = baudRate;
    
    std::wstring portName = L"\\\\.\\COM" + std::to_wstring(port);
    
    m_serialHandle = CreateFile(
        portName.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        0,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );
    
    if (m_serialHandle == INVALID_HANDLE_VALUE) {
        return false;
    }
    
    // 配置串口参数
    DCB dcb = {};
    dcb.DCBlength = sizeof(DCB);
    
    if (!GetCommState(m_serialHandle, &dcb)) {
        closeSerial();
        return false;
    }
    
    dcb.BaudRate = baudRate;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    dcb.fBinary = TRUE;
    dcb.fParity = FALSE;
    dcb.fOutxCtsFlow = FALSE;
    dcb.fOutxDsrFlow = FALSE;
    dcb.fDtrControl = DTR_CONTROL_DISABLE;
    dcb.fDsrSensitivity = FALSE;
    dcb.fTXContinueOnXoff = FALSE;
    dcb.fOutX = FALSE;
    dcb.fInX = FALSE;
    dcb.fErrorChar = FALSE;
    dcb.fNull = FALSE;
    dcb.fRtsControl = RTS_CONTROL_DISABLE;
    dcb.fAbortOnError = FALSE;
    
    if (!SetCommState(m_serialHandle, &dcb)) {
        closeSerial();
        return false;
    }
    
    // 设置超时
    COMMTIMEOUTS timeouts = {};
    timeouts.ReadIntervalTimeout = 50;
    timeouts.ReadTotalTimeoutConstant = 1000;
    timeouts.ReadTotalTimeoutMultiplier = 10;
    timeouts.WriteTotalTimeoutConstant = 1000;
    timeouts.WriteTotalTimeoutMultiplier = 10;
    
    if (!SetCommTimeouts(m_serialHandle, &timeouts)) {
        closeSerial();
        return false;
    }
    
    return true;
}

void CommunicationManager::closeSerial()
{
    if (m_serialHandle != INVALID_HANDLE_VALUE) {
        CloseHandle(m_serialHandle);
        m_serialHandle = INVALID_HANDLE_VALUE;
    }
}

std::vector<uint16_t> CommunicationManager::readHoldingRegisters(uint8_t slaveAddr, uint16_t regAddr, uint16_t regCount)
{
    std::vector<uint16_t> result;
    
    if (!isConnected()) {
        // 模拟数据
        for (int i = 0; i < regCount; ++i) {
            result.push_back(22000 + i * 100);
        }
        return result;
    }
    
    std::vector<uint8_t> command = createModbusReadCommand(slaveAddr, regAddr, regCount);
    std::vector<uint8_t> response;
    
    if (sendModbusCommand(command, response)) {
        if (response.size() >= 5 && response[1] == 0x03) {
            uint8_t byteCount = response[2];
            if (response.size() >= 3 + byteCount + 2) {
                for (int i = 0; i < regCount; ++i) {
                    uint16_t value = (response[3 + i * 2] << 8) | response[4 + i * 2];
                    result.push_back(value);
                }
            }
        }
    }
    
    return result;
}

bool CommunicationManager::sendModbusCommand(const std::vector<uint8_t>& command, std::vector<uint8_t>& response)
{
    if (!isConnected()) {
        return false;
    }
    
    DWORD bytesWritten;
    if (!WriteFile(m_serialHandle, command.data(), command.size(), &bytesWritten, NULL)) {
        return false;
    }
    
    Sleep(50); // 等待响应
    
    uint8_t buffer[256];
    DWORD bytesRead;
    if (ReadFile(m_serialHandle, buffer, sizeof(buffer), &bytesRead, NULL)) {
        response.assign(buffer, buffer + bytesRead);
        return bytesRead > 0;
    }
    
    return false;
}

uint16_t CommunicationManager::calculateCRC16(const std::vector<uint8_t>& data)
{
    uint16_t crc = 0xFFFF;
    
    for (uint8_t byte : data) {
        crc ^= byte;
        for (int i = 0; i < 8; ++i) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    
    return crc;
}

std::vector<uint8_t> CommunicationManager::createModbusReadCommand(uint8_t slaveAddr, uint16_t regAddr, uint16_t regCount)
{
    std::vector<uint8_t> command;
    command.push_back(slaveAddr);
    command.push_back(0x03); // 读保持寄存器
    command.push_back((regAddr >> 8) & 0xFF);
    command.push_back(regAddr & 0xFF);
    command.push_back((regCount >> 8) & 0xFF);
    command.push_back(regCount & 0xFF);
    
    uint16_t crc = calculateCRC16(command);
    command.push_back(crc & 0xFF);
    command.push_back((crc >> 8) & 0xFF);
    
    return command;
}