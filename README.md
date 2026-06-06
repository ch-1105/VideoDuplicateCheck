# VideoDuplicateCheck

Windows 桌面应用：基于视频内容特征（dHash + pHash）检测重复或近似重复视频。

## 功能

- 递归扫描目录，识别常见视频格式
- 按视频时长动态抽帧，计算 dHash + pHash 内容指纹
- 相似度阈值可调，支持近似重复聚类
- SQLite 缓存支持增量扫描，采样参数变化时自动重新计算
- 重复组展示 + 智能保留建议
- 批量移动、回收站删除、永久删除
- 结果导出 CSV / JSON
- 首帧预览 + 系统播放器打开

## 扫描策略

扫描精度由“每分钟抽帧数”控制，默认每分钟 3 帧。每个视频最终抽帧数会限制在 12 到 180 帧之间，短视频保留足够样本，长视频避免扫描时间失控。

| 场景     | 建议值          | 说明                 |
|----------|-----------------|----------------------|
| 快速扫描 | 1 到 2 帧/分钟  | 速度优先，适合初筛   |
| 默认扫描 | 3 帧/分钟       | 速度和效果折中       |
| 高精度   | 6 到 12 帧/分钟 | 更稳，耗时也会增加   |

性能档位只控制资源占用，包括后台线程数、OpenCV 线程数和批处理暂停，不改变识别精度。

## 环境要求

- Windows 10/11
- Python 3.11+
- 建议使用虚拟环境

## 本地开发

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m src.main
```

如果本机 uv 管理的 Python 或缓存目录不可用，可以把 uv 的缓存和解释器目录放在项目内后重建环境：

```powershell
$env:UV_CACHE_DIR='.uv-cache'
$env:UV_PYTHON_INSTALL_DIR='.uv-python'
uv venv --python 3.12 --clear
uv pip install -r requirements.txt
```

## 测试与检查

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check src tests
```

## 打包 EXE

项目已内置打包脚本（含图标和版本信息）。打包前需要确保虚拟环境中已安装 PyInstaller：

```powershell
uv pip install pyinstaller
```

- `scripts/build_onedir.bat`：生成目录版（更稳，推荐发布）
- `scripts/build_onefile.bat`：生成单文件版（分发方便，启动通常更慢）
- `scripts/clean_build.bat`：清理构建产物

执行示例：

```bat
scripts\build_onedir.bat
scripts\build_onefile.bat
```

产物路径：

- onedir: `dist/onedir/VideoDuplicateCheck/VideoDuplicateCheck.exe`
- onefile: `dist/onefile/VideoDuplicateCheck.exe`

如果 onefile 产物正在运行，Windows 会锁定 exe 并导致覆盖失败。请先关闭正在运行的程序，再重新执行打包脚本。

## 项目结构

```text
src/
  core/      # 扫描、哈希、指纹、比较、缓存数据库
  gui/       # 主界面、扫描面板、结果面板、预览、设置
  workers/   # 后台扫描任务
  utils/     # 文件操作、视频信息读取
tests/       # 单元测试
scripts/     # 打包脚本
packaging/   # Windows 版本信息
assets/      # 图标等资源
```
