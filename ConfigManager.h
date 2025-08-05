#ifndef CONFIGMANAGER_H
#define CONFIGMANAGER_H

#include <windows.h>
#include <string>
#include <map>

struct GratingConfig {
    int slaveAddress;
    int regAddress;
    int regCount;
};

struct ChannelConfig {
    GratingConfig leftGrating;
    GratingConfig rightGrating;
    double x1_ymax_avg;
    double x1_ymin_avg;
    double x1_halarm_avg;
    double x1_lalarm_avg;
    double x1_base_avg;
};

struct ComSettings {
    int port;
    int baud;
    bool debug;
    int preSendDelay;
    int preReceiveDelay;
};

class ConfigManager
{
public:
    static ConfigManager* getInstance();
    bool loadConfiguration(const std::wstring& iniPath);
    
    // 配置读取方法
    int getFrontOrBack() const;
    ComSettings getComSettings() const;
    ChannelConfig getChannelConfig(int channelNum) const;
    int getReadSlaveInterval() const;

private:
    ConfigManager() = default;
    static ConfigManager* instance;
    std::wstring configPath;
    
    int getPrivateProfileIntW(const std::wstring& section, const std::wstring& key, int defaultValue) const;
    std::wstring getPrivateProfileStringW(const std::wstring& section, const std::wstring& key, const std::wstring& defaultValue) const;
};

#endif // CONFIGMANAGER_H
