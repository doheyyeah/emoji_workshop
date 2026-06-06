# Windows .exe 打包说明

本项目支持使用 PyInstaller 打包成 Windows 可执行程序 (.exe)。

## 准备工作

1. 确保已安装 Python 环境；
2. 安装项目所需依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 安装 PyInstaller：
   ```bash
   pip install pyinstaller
   ```

## 打包命令

在项目目录下，运行以下命令进行打包：

```bash
pyinstaller --noconfirm --onedir --windowed --add-data "resources;resources" "main.py"
```

如果需要指定图标，可以添加 `--icon=resources/icon.ico`：

```bash
pyinstaller --noconfirm --onedir --windowed --icon "resources/icon.ico" --add-data "resources;resources" "main.py"
```

## 选项说明

- `--noconfirm`：覆盖之前的输出目录而不提示
- `--onedir`：打包为一个文件夹（相比 `--onefile` 单文件模式启动更快）
- `--windowed` / `-w`：隐藏控制台窗口
- `--add-data`：将指定的静态资源目录打包进去（Windows 下使用 `;` 分隔，Linux/macOS 使用 `:`）
- `--icon`：设置可执行文件的图标

## 注意事项

- **资源路径兼容**：代码中通过 `sys._MEIPASS` 兼容了 PyInstaller 运行时的临时资源路径，样式表 (`style.qss`) 等能够正常加载。
- 最终生成的 `.exe` 及相关依赖环境在 `dist/main/` 文件夹下。
