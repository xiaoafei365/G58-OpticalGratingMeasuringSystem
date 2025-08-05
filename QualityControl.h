#ifndef QUALITYCONTROL_H
#define QUALITYCONTROL_H

#include <vector>
#include <string>
#include <map>
#include "GratingChannel.h"

struct CPKLimits {
    double upperSpecLimit;
    double lowerSpecLimit;
    double targetValue;
    double warningLimit;
    double alarmLimit;
};

struct StatisticsData {
    double mean;
    double stddev;
    double cpk;
    double cp;
    int sampleCount;
    double minValue;
    double maxValue;
    double range;
};

class QualityControl
{
public:
    QualityControl();
    ~QualityControl();
    
    void setCPKLimits(const std::string& parameter, const CPKLimits& limits);
    CPKLimits getCPKLimits(const std::string& parameter) const;
    
    StatisticsData calculateStatistics(const std::vector<double>& data, const std::string& parameter) const;
    double calculateCPK(const std::vector<double>& data, double lsl, double usl) const;
    double calculateCP(const std::vector<double>& data, double lsl, double usl) const;
    
    bool isWithinLimits(double value, const std::string& parameter) const;
    std::string getQualityStatus(double cpk) const;
    
    void updateStatistics(int channelNum, const std::string& parameter, const std::vector<double>& data);
    StatisticsData getChannelStatistics(int channelNum, const std::string& parameter) const;
    
    std::string generateReport(int channelNum) const;
    
private:
    std::map<std::string, CPKLimits> m_cpkLimits;
    std::map<int, std::map<std::string, StatisticsData>> m_channelStatistics;
    
    void initializeDefaultLimits();
};

#endif // QUALITYCONTROL_H