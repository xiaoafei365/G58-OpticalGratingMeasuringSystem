#include "DataAcquisition.h"
#include <chrono>

DataAcquisition::DataAcquisition()
    : m_configManager(nullptr), m_commManager(nullptr), m_running(false), m_measurementInterval(200)
{
    m_configManager = ConfigManager::getInstance();
    m_commManager = new CommunicationManager();
}

DataAcquisition::~DataAcquisition()
{
    stopMeasurement();
    
    for (auto& pair : m_channels) {
        delete pair.second;
    }
    m_channels.clear();
    
    delete m_commManager;
}

bool DataAcquisition::initialize()
{
    // 初始化通信
    ComSettings comSettings = m_configManager->getComSettings();
    if (!m_commManager->initializeSerial(comSettings.port, comSettings.baud)) {
        // 即使串口初始化失败，也继续运行（模拟模式）
    }
    
    // 初始化通道
    for (int i = 1; i <= 5; ++i) {
        try {
            ChannelConfig config = m_configManager->getChannelConfig(i);
            m_channels[i] = new GratingChannel(i, config, m_commManager);
        } catch (...) {
            // 如果配置加载失败，跳过该通道
            continue;
        }
    }
    
    // 获取测量间隔
    m_measurementInterval = m_configManager->getReadSlaveInterval();
    
    return !m_channels.empty();
}

void DataAcquisition::startMeasurement()
{
    if (!m_running) {
        m_running = true;
        m_measurementThread = std::thread(&DataAcquisition::measurementLoop, this);
    }
}

void DataAcquisition::stopMeasurement()
{
    if (m_running) {
        m_running = false;
        if (m_measurementThread.joinable()) {
            m_measurementThread.join();
        }
    }
}

GratingChannel* DataAcquisition::getChannel(int channelNum)
{
    auto it = m_channels.find(channelNum);
    return (it != m_channels.end()) ? it->second : nullptr;
}

void DataAcquisition::measurementLoop()
{
    while (m_running) {
        auto startTime = std::chrono::steady_clock::now();
        
        // 对每个通道进行测量
        for (auto& pair : m_channels) {
            if (!m_running) break;
            
            int channelNum = pair.first;
            GratingChannel* channel = pair.second;
            
            if (channel->readGratingData()) {
                MeasurementData data = channel->getLatestMeasurement();
                
                // 调用测量回调
                if (m_measurementCallback) {
                    m_measurementCallback(channelNum, data);
                }
                
                // 检查报警
                std::vector<std::string> alarms = channel->checkAlarms();
                if (m_alarmCallback) {
                    for (const std::string& alarm : alarms) {
                        m_alarmCallback(alarm);
                    }
                }
            }
        }
        
        // 控制测量间隔
        auto endTime = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
        
        if (elapsed.count() < m_measurementInterval) {
            std::this_thread::sleep_for(std::chrono::milliseconds(m_measurementInterval - elapsed.count()));
        }
    }
}