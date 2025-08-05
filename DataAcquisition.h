#ifndef DATAACQUISITION_H
#define DATAACQUISITION_H

#include <vector>
#include <map>
#include <thread>
#include <atomic>
#include <functional>
#include "CommunicationManager.h"
#include "GratingChannel.h"
#include "ConfigManager.h"

class DataAcquisition
{
public:
    DataAcquisition();
    ~DataAcquisition();
    
    bool initialize();
    void startMeasurement();
    void stopMeasurement();
    bool isRunning() const { return m_running; }
    
    // 回调函数类型
    using MeasurementCallback = std::function<void(int channelNum, const MeasurementData& data)>;
    using AlarmCallback = std::function<void(const std::string& message)>;
    
    void setMeasurementCallback(MeasurementCallback callback) { m_measurementCallback = callback; }
    void setAlarmCallback(AlarmCallback callback) { m_alarmCallback = callback; }
    
    GratingChannel* getChannel(int channelNum);
    
private:
    void measurementLoop();
    
    ConfigManager* m_configManager;
    CommunicationManager* m_commManager;
    std::map<int, GratingChannel*> m_channels;
    
    std::thread m_measurementThread;
    std::atomic<bool> m_running;
    
    MeasurementCallback m_measurementCallback;
    AlarmCallback m_alarmCallback;
    
    int m_measurementInterval; // 毫秒
};

#endif // DATAACQUISITION_H
