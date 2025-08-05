#ifndef COMMUNICATIONMANAGER_H
#define COMMUNICATIONMANAGER_H

#include <windows.h>
#include <vector>
#include <string>

class CommunicationManager
{
public:
    CommunicationManager();
    ~CommunicationManager();
    
    bool initializeSerial(int port, int baudRate);
    void closeSerial();
    bool isConnected() const { return m_serialHandle != INVALID_HANDLE_VALUE; }
    
    // Modbus通信
    std::vector<uint16_t> readHoldingRegisters(uint8_t slaveAddr, uint16_t regAddr, uint16_t regCount);
    bool sendModbusCommand(const std::vector<uint8_t>& command, std::vector<uint8_t>& response);
    
private:
    HANDLE m_serialHandle;
    int m_port;
    int m_baudRate;
    
    uint16_t calculateCRC16(const std::vector<uint8_t>& data);
    std::vector<uint8_t> createModbusReadCommand(uint8_t slaveAddr, uint16_t regAddr, uint16_t regCount);
};

#endif // COMMUNICATIONMANAGER_H