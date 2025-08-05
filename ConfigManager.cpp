#include "ConfigManager.h"
#include <shlwapi.h>

#pragma comment(lib, "shlwapi.lib")

ConfigManager* ConfigManager::instance = nullptr;

ConfigManager* ConfigManager::getInstance()
{
    if (!instance) {
        instance = new ConfigManager();
    }
    return instance;
}

bool ConfigManager::loadConfiguration(const std::wstring& iniPath)
{
    configPath = iniPath;
    
    // 检查文件是否存在
    if (!PathFileExists(iniPath.c_str())) {
        // 创建默认配置文件
        WritePrivateProfileString(L"FrontOrBack", L"setVal", L"1", iniPath.c_str());
        WritePrivateProfileString(L"COM", L"Port", L"3", iniPath.c_str());
        WritePrivateProfileString(L"COM", L"Baud", L"9600", iniPath.c_str());
        WritePrivateProfileString(L"COM", L"DEBUG", L"1", iniPath.c_str());
        WritePrivateProfileString(L"RoundDisplay", L"ReadSlaveTimeInterval", L"200", iniPath.c_str());
        return false;
    }
    
    return true;
}

int ConfigManager::getFrontOrBack() const
{
    return getPrivateProfileIntW(L"FrontOrBack", L"setVal", 1);
}

ComSettings ConfigManager::getComSettings() const
{
    ComSettings settings;
    settings.port = getPrivateProfileIntW(L"COM", L"Port", 3);
    settings.baud = getPrivateProfileIntW(L"COM", L"Baud", 9600);
    settings.debug = getPrivateProfileIntW(L"COM", L"DEBUG", 1) != 0;
    settings.preSendDelay = getPrivateProfileIntW(L"COM", L"PreSendDelay", 10);
    settings.preReceiveDelay = getPrivateProfileIntW(L"COM", L"PreReceiveDelay", 10);
    return settings;
}

ChannelConfig ConfigManager::getChannelConfig(int channelNum) const
{
    ChannelConfig config;
    
    std::wstring leftSection = L"Channel_" + std::to_wstring(channelNum) + L"LeftGrating";
    std::wstring rightSection = L"Channel_" + std::to_wstring(channelNum) + L"RightGrating";
    
    config.leftGrating.slaveAddress = getPrivateProfileIntW(leftSection, L"SlaveAddress", 10 + channelNum);
    config.leftGrating.regAddress = getPrivateProfileIntW(leftSection, L"RegAddress", 20);
    config.leftGrating.regCount = getPrivateProfileIntW(leftSection, L"RegCount", 2);
    
    config.rightGrating.slaveAddress = getPrivateProfileIntW(rightSection, L"SlaveAddress", 20 + channelNum);
    config.rightGrating.regAddress = getPrivateProfileIntW(rightSection, L"RegAddress", 20);
    config.rightGrating.regCount = getPrivateProfileIntW(rightSection, L"RegCount", 2);
    
    config.x1_halarm_avg = 220.90;
    config.x1_lalarm_avg = 219.10;
    config.x1_base_avg = 220.0;
    
    return config;
}

int ConfigManager::getReadSlaveInterval() const
{
    return getPrivateProfileIntW(L"RoundDisplay", L"ReadSlaveTimeInterval", 200);
}

int ConfigManager::getPrivateProfileIntW(const std::wstring& section, const std::wstring& key, int defaultValue) const
{
    return GetPrivateProfileInt(section.c_str(), key.c_str(), defaultValue, configPath.c_str());
}

std::wstring ConfigManager::getPrivateProfileStringW(const std::wstring& section, const std::wstring& key, const std::wstring& defaultValue) const
{
    wchar_t buffer[256];
    GetPrivateProfileString(section.c_str(), key.c_str(), defaultValue.c_str(), buffer, 256, configPath.c_str());
    return std::wstring(buffer);
}
