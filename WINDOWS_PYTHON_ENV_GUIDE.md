# Windows Python Environment Guide

This note is written for the current machine and workspace, but the mental model also applies to most Windows Python setups.

The goal is not to turn you into a Python developer.
The goal is simpler:

- know what layer you are using
- know why a command works or fails
- know what I am changing when I fix your environment

## The Short Version

On this machine, there are three different Python-related layers:

1. A global Python installation
2. The Windows Python launcher `py`
3. A project virtual environment at `.venv`

Right now they look like this:

- Global Python: `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\python.exe`
- Python launcher: `C:\Users\qianchen\AppData\Local\Programs\Python\Launcher\py.exe`
- Project virtual environment: `C:\Users\qianchen\Desktop\youtube automation research\.venv\Scripts\python.exe`

The problem you hit earlier was not that Python was missing.
The real problem was that Windows was resolving `python` to a fake Microsoft Store alias first, instead of the real Python install.

I fixed that by putting the real Python install directory ahead of `WindowsApps` in your user PATH.

## The Core Mental Model

When you type `python`, Windows does not "know Python" in an abstract sense.
It just searches folders in `PATH` from top to bottom and runs the first matching `python.exe` it finds.

So the actual question is never:

- "Do I have Python?"

The real questions are:

- "Which `python.exe` is Windows finding first?"
- "Is that the one I meant to use?"

That is why environment issues often feel confusing.
You can have Python installed and still have `python` behave incorrectly.

## The Three Layers

### 1. Global Python

This is the base Python installed on your computer.

Use it when:

- you want `python` to work anywhere on the machine
- you want to create new virtual environments
- you want a stable default interpreter outside a project

On your machine, this is the real global Python:

- `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\python.exe`

After the PATH fix, a plain `python` now resolves to this interpreter when you are not inside an activated virtual environment.

### 2. `py` Launcher

`py` is a Windows helper installed with Python.
It is useful because it can find registered Python installations even when `python` itself is messy.

Examples:

- `py --version`
- `py -0p` to list installed interpreters
- `py -3.12` to force Python 3.12

On your machine, `py` already worked even before `python` was fixed.

That is why `py` is a good fallback diagnostic tool on Windows.

### 3. Project Virtual Environment

A virtual environment is a project-local Python sandbox.
It has its own interpreter and its own installed packages.

For this project, the venv lives here:

- `C:\Users\qianchen\Desktop\youtube automation research\.venv\Scripts\python.exe`

Use the venv when:

- you are working inside this repo
- you want the project to use the exact packages it expects
- you do not want global packages to interfere

This is the safest default for project work.

## What Activation Really Does

When you run:

```powershell
& '.\.venv\Scripts\Activate.ps1'
```

PowerShell does not "enter Python mode".
It simply changes environment variables in the current shell, mainly `PATH`.

After activation, the venv `Scripts` folder is moved to the front.
That makes these commands resolve to the project environment first:

- `python`
- `pip`

On this machine, after activation:

- `python` resolves to `.venv\Scripts\python.exe`
- `pip` resolves to `.venv\Scripts\pip.exe`

That is exactly what you want inside the project.

## Why It Broke Before

Before the fix, your user PATH contained:

- `C:\Users\qianchen\AppData\Local\Programs\Python\Launcher\`
- `C:\Users\qianchen\AppData\Local\Microsoft\WindowsApps`

But it did not contain the real Python install directory.

That meant:

- `py` worked
- `python` hit the WindowsApps alias first
- the alias was not the real interpreter you wanted

Now your user PATH contains, in the important order:

1. `C:\Users\qianchen\AppData\Local\Programs\Python\Launcher\`
2. `C:\Users\qianchen\AppData\Local\Programs\Python\Python312`
3. `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\Scripts`
4. `C:\Users\qianchen\AppData\Local\Microsoft\WindowsApps`

That order matters.
The real Python now wins before the Windows alias.

## Your Current Healthy State

Outside the project venv:

- `python --version` -> `Python 3.12.1`
- `python` -> global Python 3.12 install
- `pip` -> global Python 3.12 pip
- `py` -> Python launcher, also pointing at 3.12

Inside the project venv:

- `python` -> `.venv\Scripts\python.exe`
- `pip` -> `.venv\Scripts\pip.exe`

That is a normal and healthy setup.

## The Only Rule You Really Need

When you are doing project work, prefer the project interpreter.

That means one of these two patterns:

### Option A: Activate the venv first

```powershell
& '.\.venv\Scripts\Activate.ps1'
python --version
pip --version
```

### Option B: Call the venv interpreter directly

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe app.py
```

Option B is more explicit and less magical.
It is often easier when you want zero ambiguity.

## Why `python -m pip` Is Safer Than `pip`

This is one of the most useful habits you can learn.

Instead of:

```powershell
pip install requests
```

prefer:

```powershell
python -m pip install requests
```

Why?

- `pip` can point at a different interpreter than you think
- `python -m pip` guarantees that pip belongs to the Python you just invoked

So if you are in the project venv:

```powershell
python -m pip install -r requirements.txt
```

is safer than relying on whichever `pip.exe` happens to be first.

## Quick Diagnosis Commands

If things feel wrong later, these are the only commands you really need.

### Check what `python` really is

```powershell
python -c "import sys; print(sys.executable)"
```

### Check what `py` knows about installed Pythons

```powershell
py -0p
```

### Check what PowerShell is resolving

```powershell
Get-Command python -All
Get-Command pip -All
```

### Check whether your venv is active

```powershell
python -c "import sys; print(sys.prefix); print(sys.base_prefix)"
```

If `sys.prefix` and `sys.base_prefix` are different, you are in a venv.

## VS Code Behavior

VS Code often auto-activates the selected interpreter in new terminals.
That is why you may see a terminal look "already activated" even when the system Python is also fine.

That is normal.
It just means VS Code is trying to help by making project commands use the project environment.

So there are really two different questions:

- "Does Windows have a working global `python` command?"
- "Does this project terminal use the project venv?"

Those are related, but not the same thing.

## What I Changed Today

I updated your user PATH so that these two directories come before `WindowsApps`:

- `C:\Users\qianchen\AppData\Local\Programs\Python\Python312`
- `C:\Users\qianchen\AppData\Local\Programs\Python\Python312\Scripts`

That is why a plain `python` now works globally.

## What You Do Not Need To Memorize

You do not need to memorize every PATH rule.
You only need this checklist:

1. If you are in a project, use the project Python.
2. If `python` feels wrong, check `sys.executable`.
3. If `pip` feels wrong, use `python -m pip`.
4. If Windows is acting strange, check `py -0p`.

## A Simple Working Routine

If you want the low-friction version, use this routine:

### For normal computer-wide Python checks

```powershell
python --version
py -0p
```

### For this project

```powershell
& '.\.venv\Scripts\Activate.ps1'
python -m pip install -r requirements.txt
streamlit run app.py
```

### For zero ambiguity inside this project

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Optional Cleanup Later

Your machine is working now, so this is optional.

If you ever want to reduce confusion further, you can also disable the Windows App Execution Aliases for `python.exe` and `python3.exe` in Windows Settings.

That is not required anymore because the real Python now comes earlier in PATH.
It is only a future cleanup option.

## Final Mental Model

Think of it like this:

- Global Python = the building's main entrance
- Virtual environment = the room for one specific project
- PATH = the signposts telling Windows which door to try first
- `py` = the receptionist who still knows where Python is even if the signposts are messy

When something breaks, the fix is usually not "reinstall everything".
The fix is usually: find out which door Windows is walking through first.