#include <windows.h>
#include <commctrl.h>
#include <string>
#include <vector>
#include <map>
#include <random>
#include <thread>
#include <chrono>
#include "MainWindow.h"
#include "ConfigManager.h"
#include "resource.h"

#pragma comment(lib, "comctl32.lib")

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
    // 初始化通用控件
    INITCOMMONCONTROLSEX icex;
    icex.dwSize = sizeof(INITCOMMONCONTROLSEX);
    icex.dwICC = ICC_WIN95_CLASSES;
    InitCommonControlsEx(&icex);
    
    // 初始化配置管理器
    ConfigManager::getInstance()->loadConfiguration(L"ProductSetup.ini");
    
    // 创建主窗口
    MainWindow mainWindow;
    if (!mainWindow.create(hInstance, nCmdShow)) {
        return -1;
    }
    
    // 消息循环
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    return (int)msg.wParam;
}
