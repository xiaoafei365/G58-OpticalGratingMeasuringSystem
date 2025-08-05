#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QLabel>
#include <QPushButton>
#include <QTimer>
#include <QGridLayout>
#include <QtCharts/QChart>
#include <QtCharts/QChartView>
#include <QtCharts/QLineSeries>
#include <QtCharts/QValueAxis>
#include "DataAcquisition.h"

QT_CHARTS_USE_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    void startMeasurement();
    void stopMeasurement();
    void updateDisplay();
    void onMeasurementUpdate(int channel, const QMap<QString, double>& measurement);

private:
    void setupUI();
    void createCharts();
    void updateChart(const QString& param, double value);
    
    // UI组件
    QWidget* centralWidget;
    QGridLayout* mainLayout;
    QPushButton* startButton;
    QPushButton* stopButton;
    QLabel* statusLabel;
    QLabel* timeLabel;
    
    // 图表组件
    QMap<QString, QChart*> charts;
    QMap<QString, QChartView*> chartViews;
    QMap<QString, QLineSeries*> series;
    QMap<QString, QLabel*> cpkLabels;
    
    // 数据采集
    DataAcquisition* dataAcquisition;
    QTimer* updateTimer;
    
    // 测量参数
    QStringList parameters;
    int measurementCount;
};

#endif // MAINWINDOW_H