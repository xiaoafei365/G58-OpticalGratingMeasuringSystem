#include "MainWindow.h"
#include "ConfigManager.h"
#include "resource.h"
#include <random>
#include <sstream>
#include <iomanip>

const wchar_t* CLASS_NAME = L"OpticalGratingMainWindow";

MainWindow::MainWindow() : m_hwnd(nullptr), m_hInstance(nullptr), m_running(false), m_currentPage(L"L-P1")
{
    // 初始化页面参数映射
    m_pageParams[L"L-P1"] = L"P1";
    m_pageParams[L"L-P5U"] = L"P5U";
    m_pageParams[L"L-P5L"] = L"P5L";
    m_pageParams[L"L-P3"] = L"P3";
    m_pageParams[L"L-P4"] = L"P4";
    m_pageParams[L"R-P1"] = L"P1";
    m_pageParams[L"R-P5U"] = L"P5U";
    m_pageParams[L"R-P5L"] = L"P5L";
    m_pageParams[L"R-P3"] = L"P3";
    m_pageParams[L"R-P4"] = L"P4";
    
    // 初始化测量数据
    for (const auto& pair : m_pageParams) {
        m_measurementData[pair.second + L"_avg"] = std::vector<double>(25, 0.0);
        m_measurementData[pair.second + L"_range"] = std::vector<double>(25, 0.0);
    }
}

MainWindow::~MainWindow()
{
    if (m_running) {
        m_running = false;
        if (m_measurementThread.joinable()) {
            m_measurementThread.join();
        }
    }
}

bool MainWindow::create(HINSTANCE hInstance, int nCmdShow)
{
    m_hInstance = hInstance;
    
    // 注册窗口类
    WNDCLASS wc = {};
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = CLASS_NAME;
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    
    RegisterClass(&wc);
    
    // 创建窗口
    m_hwnd = CreateWindowEx(
        0,
        CLASS_NAME,
        L"G45-L-P1X光栅测量系统",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 1400, 900,
        NULL, NULL, hInstance, this
    );
    
    if (m_hwnd == NULL) {
        return false;
    }
    
    ShowWindow(m_hwnd, nCmdShow);
    UpdateWindow(m_hwnd);
    
    // 设置定时器
    SetTimer(m_hwnd, TIMER_UPDATE, 1000, NULL); // 每秒更新时间
    
    return true;
}

LRESULT CALLBACK MainWindow::WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam)
{
    MainWindow* pThis = NULL;
    
    if (uMsg == WM_NCCREATE) {
        CREATESTRUCT* pCreate = (CREATESTRUCT*)lParam;
        pThis = (MainWindow*)pCreate->lpCreateParams;
        SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)pThis);
        pThis->m_hwnd = hwnd;
    } else {
        pThis = (MainWindow*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    }
    
    if (pThis) {
        return pThis->handleMessage(uMsg, wParam, lParam);
    } else {
        return DefWindowProc(hwnd, uMsg, wParam, lParam);
    }
}

LRESULT MainWindow::handleMessage(UINT uMsg, WPARAM wParam, LPARAM lParam)
{
    switch (uMsg) {
    case WM_CREATE:
        createControls();
        return 0;
        
    case WM_COMMAND:
        {
            int wmId = LOWORD(wParam);
            
            // 检查是否是页面按钮
            for (const auto& pair : m_pageButtons) {
                if ((HWND)lParam == pair.second) {
                    switchPage(pair.first);
                    return 0;
                }
            }
            
            if ((HWND)lParam == m_startButton) {
                startMeasurement();
            } else if ((HWND)lParam == m_stopButton) {
                stopMeasurement();
            }
        }
        return 0;
        
    case WM_TIMER:
        if (wParam == TIMER_UPDATE) {
            // 更新时间显示
            SYSTEMTIME st;
            GetLocalTime(&st);
            std::wstringstream ss;
            ss << std::setfill(L'0') << std::setw(2) << st.wHour << L":"
               << std::setw(2) << st.wMinute << L":"
               << std::setw(2) << st.wSecond;
            SetWindowText(m_timeLabel, ss.str().c_str());
        }
        return 0;
        
    case WM_PAINT:
        {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(m_hwnd, &ps);
            
            // 绘制图表
            updateCharts();
            
            EndPaint(m_hwnd, &ps);
        }
        return 0;
        
    case WM_DESTROY:
        KillTimer(m_hwnd, TIMER_UPDATE);
        PostQuitMessage(0);
        return 0;
    }
    
    return DefWindowProc(m_hwnd, uMsg, wParam, lParam);
}

void MainWindow::createControls()
{
    // 创建标题区域
    CreateWindow(L"STATIC", L"G45", WS_VISIBLE | WS_CHILD | SS_CENTER,
                 20, 20, 60, 30, m_hwnd, NULL, m_hInstance, NULL);
    
    // 创建页面按钮
    std::vector<std::wstring> leftParams = {L"L-P1", L"L-P5U", L"L-P5L", L"L-P3", L"L-P4"};
    std::vector<std::wstring> rightParams = {L"R-P1", L"R-P5U", L"R-P5L", L"R-P3", L"R-P4"};
    
    int x = 150;
    for (size_t i = 0; i < leftParams.size(); ++i) {
        HWND btn = CreateWindow(L"BUTTON", leftParams[i].c_str(),
                               WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                               x + (i % 3) * 80, 20 + (i / 3) * 35, 75, 30,
                               m_hwnd, NULL, m_hInstance, NULL);
        m_pageButtons[leftParams[i]] = btn;
    }
    
    x = 600;
    for (size_t i = 0; i < rightParams.size(); ++i) {
        HWND btn = CreateWindow(L"BUTTON", rightParams[i].c_str(),
                               WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                               x + (i % 3) * 80, 20 + (i / 3) * 35, 75, 30,
                               m_hwnd, NULL, m_hInstance, NULL);
        m_pageButtons[rightParams[i]] = btn;
    }
    
    // 创建中间标题
    CreateWindow(L"STATIC", L"G45-L-P1X光栅", WS_VISIBLE | WS_CHILD | SS_CENTER,
                 500, 30, 200, 30, m_hwnd, NULL, m_hInstance, NULL);
    
    // 创建时间标签
    m_timeLabel = CreateWindow(L"STATIC", L"00:00:00", WS_VISIBLE | WS_CHILD | SS_CENTER,
                              1200, 30, 100, 30, m_hwnd, NULL, m_hInstance, NULL);
    
    // 创建控制按钮
    m_startButton = CreateWindow(L"BUTTON", L"开始测量", WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                                50, 100, 100, 40, m_hwnd, NULL, m_hInstance, NULL);
    
    m_stopButton = CreateWindow(L"BUTTON", L"停止测量", WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                               160, 100, 100, 40, m_hwnd, NULL, m_hInstance, NULL);
    
    m_statusLabel = CreateWindow(L"STATIC", L"系统就绪", WS_VISIBLE | WS_CHILD,
                                280, 110, 200, 20, m_hwnd, NULL, m_hInstance, NULL);
    
    // 创建图表区域
    m_leftChart = CreateWindow(L"STATIC", L"", WS_VISIBLE | WS_CHILD | SS_BLACKFRAME,
                              50, 160, 600, 400, m_hwnd, NULL, m_hInstance, NULL);
    
    m_rightChart = CreateWindow(L"STATIC", L"", WS_VISIBLE | WS_CHILD | SS_BLACKFRAME,
                               700, 160, 600, 400, m_hwnd, NULL, m_hInstance, NULL);
    
    // 设置当前页面按钮状态
    switchPage(m_currentPage);
}

void MainWindow::switchPage(const std::wstring& pageName)
{
    m_currentPage = pageName;
    
    // 更新按钮状态
    for (const auto& pair : m_pageButtons) {
        if (pair.first == pageName) {
            // 设置为选中状态（这里简化处理）
            SetWindowText(pair.second, (L"[" + pair.first + L"]").c_str());
        } else {
            SetWindowText(pair.second, pair.first.c_str());
        }
    }
    
    // 重绘图表
    InvalidateRect(m_hwnd, NULL, TRUE);
}

void MainWindow::startMeasurement()
{
    if (!m_running) {
        m_running = true;
        m_measurementThread = std::thread(&MainWindow::measurementLoop, this);
        
        SetWindowText(m_startButton, L"测量中...");
        EnableWindow(m_startButton, FALSE);
        EnableWindow(m_stopButton, TRUE);
        SetWindowText(m_statusLabel, L"测量中...");
    }
}

void MainWindow::stopMeasurement()
{
    if (m_running) {
        m_running = false;
        if (m_measurementThread.joinable()) {
            m_measurementThread.join();
        }
        
        SetWindowText(m_startButton, L"开始测量");
        EnableWindow(m_startButton, TRUE);
        EnableWindow(m_stopButton, FALSE);
        SetWindowText(m_statusLabel, L"测量已停止");
    }
}

void MainWindow::measurementLoop()
{
    std::random_device rd;
    std::mt19937 gen(rd());
    
    // 不同参数的基准值和噪声
    std::map<std::wstring, std::pair<double, double>> paramSettings = {
        {L"P1", {220.0, 0.3}},
        {L"P5U", {425.0, 0.5}},
        {L"P5L", {425.0, 0.5}},
        {L"P3", {645.0, 0.8}},
        {L"P4", {1.0, 0.1}}
    };
    
    while (m_running) {
        // 更新所有参数的数据
        for (const auto& setting : paramSettings) {
            std::wstring param = setting.first;
            double baseValue = setting.second.first;
            double noise = setting.second.second;
            
            std::normal_distribution<> avgDist(baseValue, noise);
            std::normal_distribution<> rangeDist(0, noise * 0.3);
            
            // 更新平均值数据
            auto& avgData = m_measurementData[param + L"_avg"];
            avgData.erase(avgData.begin());
            avgData.push_back(avgDist(gen));
            
            // 更新极差值数据
            auto& rangeData = m_measurementData[param + L"_range"];
            rangeData.erase(rangeData.begin());
            rangeData.push_back(std::abs(rangeDist(gen)));
        }
        
        // 触发重绘
        InvalidateRect(m_hwnd, NULL, FALSE);
        
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
}

void MainWindow::updateCharts()
{
    // 这里简化图表绘制，实际应用中可以使用GDI+或其他图形库
    // 当前只是占位符，显示当前页面的参数名称
    
    HDC hdc = GetDC(m_leftChart);
    if (hdc) {
        RECT rect;
        GetClientRect(m_leftChart, &rect);
        
        std::wstring param = m_pageParams[m_currentPage];
        std::wstring leftText = param + L" 平均值";
        
        DrawText(hdc, leftText.c_str(), -1, &rect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        ReleaseDC(m_leftChart, hdc);
    }
    
    hdc = GetDC(m_rightChart);
    if (hdc) {
        RECT rect;
        GetClientRect(m_rightChart, &rect);
        
        std::wstring param = m_pageParams[m_currentPage];
        std::wstring rightText = param + L" 极差值";
        
        DrawText(hdc, rightText.c_str(), -1, &rect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        ReleaseDC(m_rightChart, hdc);
    }
}
