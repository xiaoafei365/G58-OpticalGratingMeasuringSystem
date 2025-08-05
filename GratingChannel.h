#ifndef GRATINGCHANNEL_H
#define GRATINGCHANNEL_H

#include <vector>
#include <string>
#include <map>
#include "CommunicationManager.h"
#include "ConfigManager.h"

struct MeasurementData {
    double p1_avg;
    double p1_range;
    double p5u_avg;
    double p5u_range;
    double p5l_avg;
    double p5l_range;
    double p3_avg;
    double p3_range;
    double p4_avg;
    double p4_range;
    double timestamp;
};

class GratingChannel
{
public:
    GratingChannel(int channelNum, const ChannelConfig& config, CommunicationManager* comm);
    ~GratingChannel();
    
    bool readGratingData();
    MeasurementData getLatestMeasurement() const;
    std::vector<MeasurementData> getMeasurementHistory(int count = 25) const;
    
    double calculateCPK(const std::string& parameter) const;
    std::vector<std::string> checkAlarms() const;
    
    int getChannelNumber() const { return m_channelNum; }
    
private:
    int m_channelNum;
    ChannelConfig m_config;
    CommunicationManager* m_comm;
    
    std::vector<MeasurementData> m_measurements;
    static const int MAX_MEASUREMENTS = 1000;
    
    MeasurementData processRawData(const std::vector<uint16_t>& leftData, const std::vector<uint16_t>& rightData);
    double generateSimulatedValue(const std::string& parameter);
};

#endif // GRATINGCHANNEL_H