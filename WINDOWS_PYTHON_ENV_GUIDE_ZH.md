# Windows Python 环境说明（中文版）

这份说明是写给你当前这台 Windows 机器和这个工作区的。
但它背后的思路，也适用于大多数 Windows 上的 Python 环境问题。

目标不是把你变成 Python 工程师。
目标更直接：

- 你知道自己现在用的是哪一层 Python
- 你知道为什么某条命令能跑，或为什么会失败
- 你知道我在修环境时，实际改动的是什么

## 一句话先说结论

你现在这台机器上，一共有 3 层 Python：

1. 全局 Python
2. Windows 的 `py` 启动器
3. 当前项目自己的虚拟环境 `.venv`

当前实际路径如下：

- 全局 Python：`C:\Users\qianchen\AppData\Local\Programs\Python\Python312\python.exe`
- Python 启动器：`C:\Users\qianchen\AppData\Local\Programs\Python\Launcher\py.exe`
- 项目虚拟环境：`C:\Users\qianchen\Desktop\youtube automation research\.venv\Scripts\python.exe`

你之前遇到的问题，不是“电脑没装 Python”。
真正的问题是：Windows 在解析 `python` 这个命令时，先命中了 Microsoft Store 的假别名，而不是你真正安装的 Python。

我已经把真实 Python 安装目录放到了用户 PATH 里更靠前的位置，所以现在：

- 不进虚拟环境，`python` 也能正常工作
- 进了 `.venv` 后，`python` 会自动切到项目解释器

## 核心心智模型

当你在 PowerShell 里输入 `python` 时，Windows 并不会“理解 Python 是什么语言”。
它只会做一件事：

- 按照 `PATH` 里的目录顺序，从上到下找第一个叫 `python.exe` 的程序

所以真正的问题从来不是：

- “我有没有 Python？”

真正要问的是：

- “Windows 现在先找到的是哪个 `python.exe`？”
- “那个是不是我想用的那个？”

这也是为什么很多环境问题看起来很玄。
你明明装了 Python，但命令还是会表现得像坏掉了一样。

## 这三层分别是什么

### 1. 全局 Python

这就是装在你电脑上的基础 Python。

适合什么时候用：

- 你想在电脑任意目录下直接用 `python`
- 你想创建新的虚拟环境
- 你想在项目外有一个稳定默认解释器

你这台机器上的全局 Python 是：

- `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\python.exe`

现在 PATH 修好以后，如果你没有激活任何虚拟环境，那么普通的 `python` 会默认走它。

### 2. `py` 启动器

`py` 是 Windows 上 Python 安装器自带的一个辅助入口。

它的好处是：

- 就算 `python` 本身路径有点乱，`py` 往往还能找到注册过的 Python 解释器

常见用法：

- `py --version`
- `py -0p`：列出当前机器上已注册的解释器
- `py -3.12`：强制使用 Python 3.12

你这台机器上，`py` 在修复前其实就能正常工作。

所以在 Windows 上排查 Python 环境时，`py` 是很好用的备用诊断工具。

### 3. 项目虚拟环境 `.venv`

虚拟环境可以理解为：

- 项目专属的 Python 沙箱

它有自己独立的：

- `python.exe`
- `pip`
- 安装包集合

这个项目的虚拟环境在这里：

- `C:\Users\qianchen\Desktop\youtube automation research\.venv\Scripts\python.exe`

适合什么时候用：

- 你正在这个仓库里干活
- 你希望项目严格使用它自己的依赖版本
- 你不想让全局 Python 的包污染项目

对项目开发来说，这一层是最稳的默认选择。

## 激活虚拟环境，到底发生了什么

当你执行：

```powershell
& '.\.venv\Scripts\Activate.ps1'
```

PowerShell 并不是“进入了 Python 模式”。
它做的事情其实很朴素：

- 修改当前终端会话里的环境变量，最关键的是 `PATH`

激活以后，`.venv\Scripts` 会被临时放到 PATH 前面。

于是下面这些命令就会优先指向项目环境：

- `python`
- `pip`

也就是说，激活后：

- `python` -> `.venv\Scripts\python.exe`
- `pip` -> `.venv\Scripts\pip.exe`

这正是你在项目里想要的效果。

## 之前为什么会坏

你修之前的用户 PATH 里，有这些目录：

- `C:\Users\qianchen\AppData\Local\Programs\Python\Launcher\`
- `C:\Users\qianchen\AppData\Local\Microsoft\WindowsApps`

但缺了真正的 Python 安装目录。

这就导致：

- `py` 能工作
- `python` 先撞上 WindowsApps 里的别名
- 那个别名不是你真正想运行的解释器

现在 PATH 的关键顺序已经变成：

1. `C:\Users\qianchen\AppData\Local\Programs\Python\Launcher\`
2. `C:\Users\qianchen\AppData\Local\Programs\Python\Python312`
3. `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\Scripts`
4. `C:\Users\qianchen\AppData\Local\Microsoft\WindowsApps`

这个顺序非常关键。
因为真正的 Python 终于排在假别名前面了。

## 你现在的健康状态

在项目虚拟环境外：

- `python --version` -> `Python 3.12.1`
- `python` -> 全局 Python 3.12
- `pip` -> 全局 Python 3.12 的 pip
- `py` -> Python 启动器，也指向 3.12

在项目虚拟环境内：

- `python` -> `.venv\Scripts\python.exe`
- `pip` -> `.venv\Scripts\pip.exe`

这就是一套正常而且健康的状态。

## 你真正需要记住的唯一原则

只要是在这个项目里工作，优先用项目解释器。

具体就是两种模式：

### 方案 A：先激活虚拟环境

```powershell
& '.\.venv\Scripts\Activate.ps1'
python --version
pip --version
```

### 方案 B：直接点名调用项目解释器

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe app.py
```

方案 B 更直接，也更不容易有歧义。
如果你想完全知道自己在调用谁，这个方式最好用。

## 为什么 `python -m pip` 比 `pip` 更稳

这是最值得养成的习惯之一。

不要默认写：

```powershell
pip install requests
```

优先写：

```powershell
python -m pip install requests
```

原因很简单：

- `pip` 可能不是你以为的那个 `pip.exe`
- `python -m pip` 会强制使用“这个 Python 对应的 pip”

所以如果你已经在项目虚拟环境里：

```powershell
python -m pip install -r requirements.txt
```

会比裸跑 `pip` 更安全。

## 以后出问题，优先用这几个诊断命令

### 1. 看当前 `python` 到底指向谁

```powershell
python -c "import sys; print(sys.executable)"
```

### 2. 看 `py` 识别到哪些 Python

```powershell
py -0p
```

### 3. 看 PowerShell 当前解析结果

```powershell
Get-Command python -All
Get-Command pip -All
```

### 4. 看是不是在虚拟环境里

```powershell
python -c "import sys; print(sys.prefix); print(sys.base_prefix)"
```

如果 `sys.prefix` 和 `sys.base_prefix` 不一样，就说明你当前在 venv 里。

## VS Code 为什么看起来会“自动激活”

VS Code 往往会在新终端里自动激活你当前选中的 Python 解释器。

所以你有时会看到：

- 终端一打开就像已经进了虚拟环境

这是正常现象。
它只是尽量帮你把项目命令指向项目 Python。

所以这里其实有两个不同问题：

- Windows 全局 `python` 能不能正常工作？
- 当前项目终端是不是在用项目 venv？

这两个问题相关，但不是一回事。

## 我这次实际改了什么

我修改了你的用户 PATH，让下面这两个目录排到 `WindowsApps` 前面：

- `C:\Users\qianchen\AppData\Local\Programs\Python\Python312`
- `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\Scripts`

所以现在普通的 `python` 已经能在全局正常工作。

## 你不需要死记的东西

你没必要背 PATH 全细节。
你只要记住下面这张最小清单：

1. 在项目里工作，就优先用项目 Python。
2. 如果 `python` 看起来不对，先查 `sys.executable`。
3. 如果 `pip` 看起来不对，就用 `python -m pip`。
4. 如果 Windows 行为很怪，就跑 `py -0p`。

## 一套低摩擦工作流

### 平时看全局 Python 是否正常

```powershell
python --version
py -0p
```

### 在这个项目里正常工作

```powershell
& '.\.venv\Scripts\Activate.ps1'
python -m pip install -r requirements.txt
streamlit run app.py
```

### 如果你想完全避免歧义

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 后续可选清理

你现在机器已经是可用状态了，这一步不是必须。

如果以后你还想进一步减少干扰，可以去 Windows 设置里把：

- `python.exe`
- `python3.exe`

对应的 App Execution Aliases 关掉。

但现在不是必须，因为真正的 Python 已经在 PATH 里排在前面了。

## 最后的理解方式

你可以把它想成三层入口：

- 全局 Python = 大楼正门
- `py` = 前台工作人员，知道楼里有哪些门
- `.venv` = 这个项目自己的办公室门

如果你只是在大楼里走动，用正门就够了。
如果你在这个项目里办公，就直接进这个项目自己的门。

一旦你知道“我现在到底进的是哪扇门”，Python 环境问题就会清晰很多。