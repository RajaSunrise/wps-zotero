:: 设置中文环境
chcp 65001

@echo off

echo. 检查本机上是否安装了python
:: Check for python in PATH
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo. 未找到 Python，请确保已安装 Python 并添加到 PATH 环境变量。
    echo. Press any key to exit...
    pause
    exit
)
echo. Python found.
echo.

:MENU
echo. 请选择要运行的命令：
echo.
echo. 1. 安装插件 (Install Plugin)
echo. 2. 卸载插件 (Uninstall Plugin)
echo. 3. 退出 (Exit)
echo.

SET /P choice=请输入您的选择（1、2或3）：


if "%choice%"=="1" (
    echo. 开始安装...
    python install.py
    echo. 安装结束,请按任意键退出
    pause
) else if "%choice%"=="2" (
    echo. 开始卸载...
    python install.py -u
    echo. 卸载完成,请按任意键退出
    pause
) else if "%choice%"=="3" (
    echo. 退出...
    exit
) else (
    echo. 无效的选择，请重新输入
    goto MENU
)
