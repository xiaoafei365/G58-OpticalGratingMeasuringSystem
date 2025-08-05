#include "GratingChannel.h"
#include <random>
#include <chrono>
#include <algorithm>
#include <numeric>
#include <cmath>

GratingChannel::GratingChannel(int channelNum, const ChannelConfig& config, CommunicationManager* comm)
    : m_channelNum(channelNum), m_config(config), m_comm(comm)
{
    m_measurements.reserve(MAX_MEASUREMENTS);
}

GratingChannel::~GratingChannel()
{
}

bool GratingChannel::readGratingData()
{
    if (!m_comm || !m_comm->isConnected()) {
        // 生成模拟数据
        MeasurementData data;
        data.p1_avg = generateSimulatedValue("P1");
        data.p1_range = std::abs(generateSimulatedValue("P1_range"));
        data.p5u_avg = generateSimulatedValue("P5U");
        data.p5u_range = std::abs(generateSimulatedValue("P5U_range"));
        data.p5l_avg = generateSimulatedValue("P5L");
        data.p5l_range = std::abs(generateSimulatedValue("P5L_range"));
        data.p3_avg = generateSimulatedValue("P3");
        data.p3_range = std::abs(generateSimulatedValue("P3_range"));
        data.p4_avg = generateSimulatedValue("P4");
        data.p4_range = std::abs(generateSimulatedValue("P4_range"));
        data.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        
        m_measurements.push_back(data);
        if (m_measurements.size() > MAX_MEASUREMENTS) {
            m_measurements.erase(m_measurements.begin());
        }
        
        return true;
    }
    
    // 读取左光栅数据
    std::vector<uint16_t> leftData = m_comm->readHoldingRegisters(
        m_config.leftGrating.slaveAddress,
        m_config.leftGrating.regAddress,
        m_config.leftGrating.regCount
    );
    
    // 读取右光栅数据
    std::vector<uint16_t> rightData = m_comm->readHoldingRegisters(
        m_config.rightGrating.slaveAddress,
        m_config.rightGrating.regAddress,
        m_config.rightGrating.regCount
    );
    
    if (!leftData.empty() && !rightData.empty()) {
        MeasurementData data = processRawData(leftData, rightData);
        m_measurements.push_back(data);
        
        if (m_measurements.size() > MAX_MEASUREMENTS) {
            m_measurements.erase(m_measurements.begin());
        }
        
        return true;
    }
    
    return false;
}

MeasurementData GratingChannel::getLatestMeasurement() const
{
    if (!m_measurements.empty()) {
        return m_measurements.back();
    }
    return MeasurementData{};
}

std::vector<MeasurementData> GratingChannel::getMeasurementHistory(int count) const
{
    if (m_measurements.size() <= count) {
        return m_measurements;
    }
    
    return std::vector<MeasurementData>(
        m_measurements.end() - count,
        m_measurements.end()
    );
}

double GratingChannel::calculateCPK(const std::string& parameter) const
{
    if (m_measurements.size() < 10) {
        return 0.0;
    }
    
    std::vector<double> values;
    for (const auto& measurement : m_measurements) {
        if (parameter == "P1") {
            values.push_back(measurement.p1_avg);
        } else if (parameter == "P5U") {
            values.push_back(measurement.p5u_avg);
        } else if (parameter == "P5L") {
            values.push_back(measurement.p5l_avg);
        } else if (parameter == "P3") {
            values.push_back(measurement.p3_avg);
        } else if (parameter == "P4") {
            values.push_back(measurement.p4_avg);
        }
    }
    
    if (values.empty()) {
        return 0.0;
    }
    
    double mean = std::accumulate(values.begin(), values.end(), 0.0) / values.size();
    double variance = 0.0;
    for (double value : values) {
        variance += (value - mean) * (value - mean);
    }
    double stddev = std::sqrt(variance / (values.size() - 1));
    
    if (stddev == 0.0) {
        return 0.0;
    }
    
    // 规格限设置
    double lsl = 0.0, usl = 0.0;
    if (parameter == "P1") {
        lsl = 219.10;
        usl = 220.90;
    } else if (parameter == "P5U" || parameter == "P5L") {
        lsl = 423.90;
        usl = 426.10;
    } else if (parameter == "P3") {
        lsl = 643.0;
        usl = 647.0;
    } else if (parameter == "P4") {
        lsl = 0.5;
        usl = 1.5;
    }
    
    double cpu = (usl - mean) / (3 * stddev);
    double cpl = (mean - lsl) / (3 * stddev);
    
    return std::min(cpu, cpl);
}

std::vector<std::string> GratingChannel::checkAlarms() const
{
    std::vector<std::string> alarms;
    
    if (m_measurements.empty()) {
        return alarms;
    }
    
    const MeasurementData& latest = m_measurements.back();
    
    // 检查P1报警
    if (latest.p1_avg > 220.90) {
        alarms.push_back("Channel " + std::to_string(m_channelNum) + " P1 超上限");
    } else if (latest.p1_avg < 219.10) {
        alarms.push_back("Channel " + std::to_string(m_channelNum) + " P1 超下限");
    }
    
    // 检查P5U报警
    if (latest.p5u_avg > 426.10) {
        alarms.push_back("Channel " + std::to_string(m_channelNum) + " P5U 超上限");
    } else if (latest.p5u_avg < 423.90) {
        alarms.push_back("Channel " + std::to_string(m_channelNum) + " P5U 超下限");
    }
    
    // 检查P5L报警
    if (latest.p5l_avg > 426.10) {
        alarms.push_back("Channel " + std::to_string(m_channelNum) + " P5L 超上限");
    } else if (latest.p5l_avg < 423.90) {
        alarms.push_back("Channel " + std::to_string(m_channelNum) + " P5L 超下限");
    }
    
    return alarms;
}

MeasurementData GratingChannel::processRawData(const std::vector<uint16_t>& leftData, const std::vector<uint16_t>& rightData)
{
    MeasurementData data;
    
    // 这里应该根据实际的数据格式进行解析
    // 当前使用简化的处理方式
    if (!leftData.empty() && !rightData.empty()) {
        data.p1_avg = leftData[0] / 100.0;
        data.p5u_avg = leftData.size() > 1 ? leftData[1] / 100.0 : 425.0;
        data.p5l_avg = rightData[0] / 100.0;
        data.p3_avg = rightData.size() > 1 ? rightData[1] / 100.0 : 645.0;
        data.p4_avg = 1.0;
        
        // 计算极差值（简化处理）
        data.p1_range = std::abs(data.p1_avg - 220.0) * 0.1;
        data.p5u_range = std::abs(data.p5u_avg - 425.0) * 0.1;
        data.p5l_range = std::abs(data.p5l_avg - 425.0) * 0.1;
        data.p3_range = std::abs(data.p3_avg - 645.0) * 0.1;
        data.p4_range = std::abs(data.p4_avg - 1.0) * 0.1;
    }
    
    data.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    
    return data;
}

double GratingChannel::generateSimulatedValue(const std::string& parameter)
{
    static std::random_device rd;
    static std::mt19937 gen(rd());
    
    if (parameter == "P1") {
        std::normal_distribution<> dist(220.0, 0.3);
        return dist(gen);
    } else if (parameter == "P5U" || parameter == "P5L") {
        std::normal_distribution<> dist(425.0, 0.5);
        return dist(gen);
    } else if (parameter == "P3") {
        std::normal_distribution<> dist(645.0, 0.8);
        return dist(gen);
    } else if (parameter == "P4") {
        std::normal_distribution<> dist(1.0, 0.1);
        return dist(gen);
    } else if (parameter.find("_range") != std::string::npos) {
        std::normal_distribution<> dist(0.0, 0.1);
        return std::abs(dist(gen));
    }
    
    return 0.0;
}