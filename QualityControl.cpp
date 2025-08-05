#include "QualityControl.h"
#include <algorithm>
#include <numeric>
#include <cmath>
#include <sstream>
#include <iomanip>

QualityControl::QualityControl()
{
    initializeDefaultLimits();
}

QualityControl::~QualityControl()
{
}

void QualityControl::setCPKLimits(const std::string& parameter, const CPKLimits& limits)
{
    m_cpkLimits[parameter] = limits;
}

CPKLimits QualityControl::getCPKLimits(const std::string& parameter) const
{
    auto it = m_cpkLimits.find(parameter);
    if (it != m_cpkLimits.end()) {
        return it->second;
    }
    
    // 返回默认限值
    CPKLimits defaultLimits = {0.0, 0.0, 0.0, 1.33, 1.0};
    return defaultLimits;
}

StatisticsData QualityControl::calculateStatistics(const std::vector<double>& data, const std::string& parameter) const
{
    StatisticsData stats = {};
    
    if (data.empty()) {
        return stats;
    }
    
    stats.sampleCount = static_cast<int>(data.size());
    
    // 计算均值
    stats.mean = std::accumulate(data.begin(), data.end(), 0.0) / data.size();
    
    // 计算标准差
    double variance = 0.0;
    for (double value : data) {
        variance += (value - stats.mean) * (value - stats.mean);
    }
    stats.stddev = (data.size() > 1) ? std::sqrt(variance / (data.size() - 1)) : 0.0;
    
    // 计算最小值和最大值
    auto minmax = std::minmax_element(data.begin(), data.end());
    stats.minValue = *minmax.first;
    stats.maxValue = *minmax.second;
    stats.range = stats.maxValue - stats.minValue;
    
    // 计算CPK和CP
    CPKLimits limits = getCPKLimits(parameter);
    if (limits.upperSpecLimit != limits.lowerSpecLimit) {
        stats.cpk = calculateCPK(data, limits.lowerSpecLimit, limits.upperSpecLimit);
        stats.cp = calculateCP(data, limits.lowerSpecLimit, limits.upperSpecLimit);
    }
    
    return stats;
}

double QualityControl::calculateCPK(const std::vector<double>& data, double lsl, double usl) const
{
    if (data.size() < 2) {
        return 0.0;
    }
    
    double mean = std::accumulate(data.begin(), data.end(), 0.0) / data.size();
    
    double variance = 0.0;
    for (double value : data) {
        variance += (value - mean) * (value - mean);
    }
    double stddev = std::sqrt(variance / (data.size() - 1));
    
    if (stddev == 0.0) {
        return 0.0;
    }
    
    double cpu = (usl - mean) / (3 * stddev);
    double cpl = (mean - lsl) / (3 * stddev);
    
    return std::min(cpu, cpl);
}

double QualityControl::calculateCP(const std::vector<double>& data, double lsl, double usl) const
{
    if (data.size() < 2) {
        return 0.0;
    }
    
    double variance = 0.0;
    double mean = std::accumulate(data.begin(), data.end(), 0.0) / data.size();
    
    for (double value : data) {
        variance += (value - mean) * (value - mean);
    }
    double stddev = std::sqrt(variance / (data.size() - 1));
    
    if (stddev == 0.0) {
        return 0.0;
    }
    
    return (usl - lsl) / (6 * stddev);
}

bool QualityControl::isWithinLimits(double value, const std::string& parameter) const
{
    CPKLimits limits = getCPKLimits(parameter);
    return (value >= limits.lowerSpecLimit && value <= limits.upperSpecLimit);
}

std::string QualityControl::getQualityStatus(double cpk) const
{
    if (cpk >= 1.67) {
        return "优秀";
    } else if (cpk >= 1.33) {
        return "良好";
    } else if (cpk >= 1.0) {
        return "可接受";
    } else {
        return "需改进";
    }
}

void QualityControl::updateStatistics(int channelNum, const std::string& parameter, const std::vector<double>& data)
{
    m_channelStatistics[channelNum][parameter] = calculateStatistics(data, parameter);
}

StatisticsData QualityControl::getChannelStatistics(int channelNum, const std::string& parameter) const
{
    auto channelIt = m_channelStatistics.find(channelNum);
    if (channelIt != m_channelStatistics.end()) {
        auto paramIt = channelIt->second.find(parameter);
        if (paramIt != channelIt->second.end()) {
            return paramIt->second;
        }
    }
    
    return StatisticsData{};
}

std::string QualityControl::generateReport(int channelNum) const
{
    std::ostringstream report;
    report << std::fixed << std::setprecision(3);
    
    report << "通道 " << channelNum << " 质量报告\n";
    report << "========================\n";
    
    auto channelIt = m_channelStatistics.find(channelNum);
    if (channelIt != m_channelStatistics.end()) {
        for (const auto& paramPair : channelIt->second) {
            const std::string& param = paramPair.first;
            const StatisticsData& stats = paramPair.second;
            
            report << "\n参数: " << param << "\n";
            report << "  样本数: " << stats.sampleCount << "\n";
            report << "  均值: " << stats.mean << "\n";
            report << "  标准差: " << stats.stddev << "\n";
            report << "  最小值: " << stats.minValue << "\n";
            report << "  最大值: " << stats.maxValue << "\n";
            report << "  极差: " << stats.range << "\n";
            report << "  CPK: " << stats.cpk << "\n";
            report << "  CP: " << stats.cp << "\n";
            report << "  质量状态: " << getQualityStatus(stats.cpk) << "\n";
        }
    }
    
    return report.str();
}

void QualityControl::initializeDefaultLimits()
{
    // P1参数限值
    CPKLimits p1Limits;
    p1Limits.lowerSpecLimit = 219.10;
    p1Limits.upperSpecLimit = 220.90;
    p1Limits.targetValue = 220.0;
    p1Limits.warningLimit = 1.33;
    p1Limits.alarmLimit = 1.0;
    m_cpkLimits["P1"] = p1Limits;
    
    // P5U参数限值
    CPKLimits p5uLimits;
    p5uLimits.lowerSpecLimit = 423.90;
    p5uLimits.upperSpecLimit = 426.10;
    p5uLimits.targetValue = 425.0;
    p5uLimits.warningLimit = 1.33;
    p5uLimits.alarmLimit = 1.0;
    m_cpkLimits["P5U"] = p5uLimits;
    
    // P5L参数限值
    CPKLimits p5lLimits;
    p5lLimits.lowerSpecLimit = 423.90;
    p5lLimits.upperSpecLimit = 426.10;
    p5lLimits.targetValue = 425.0;
    p5lLimits.warningLimit = 1.33;
    p5lLimits.alarmLimit = 1.0;
    m_cpkLimits["P5L"] = p5lLimits;
    
    // P3参数限值
    CPKLimits p3Limits;
    p3Limits.lowerSpecLimit = 643.0;
    p3Limits.upperSpecLimit = 647.0;
    p3Limits.targetValue = 645.0;
    p3Limits.warningLimit = 1.33;
    p3Limits.alarmLimit = 1.0;
    m_cpkLimits["P3"] = p3Limits;
    
    // P4参数限值
    CPKLimits p4Limits;
    p4Limits.lowerSpecLimit = 0.5;
    p4Limits.upperSpecLimit = 1.5;
    p4Limits.targetValue = 1.0;
    p4Limits.warningLimit = 1.33;
    p4Limits.alarmLimit = 1.0;
    m_cpkLimits["P4"] = p4Limits;
}