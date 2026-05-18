# coderun — Local GUI-Based C/C++ Runner Tool

A native Windows desktop utility for compiling and running C and C++ files from a terminal-triggered working directory, designed to mimic the rapid launcher flow of tools like Jupyter Notebook while retaining a professional, modern, lightweight developer IDE aesthetic.

---

# Coderun Tool Guide: Install & Setup

This section explains how to install, develop, package, and globally register the `coderun` tool on any Windows PC after cloning this repository.

## Prerequisites
- **Python 3.10+** (Python 3.14 recommended/fully supported)
- **GCC / G++ Compilers** (If you don't have them, refer to the [Compiler Setup Guide](#cc-compiler-setup-guide-gcc--g-on-windows) below!)

---

## Step 1 — Install Python Modules
Open a terminal in the cloned repository folder and run:
```bash
pip install -r requirements.txt
```
This automatically installs:
* `PySide6` (Official stable-ABI Qt bindings for Python)
* `PyInstaller` (To compile into a standalone `.exe`)

---

## Step 2 — Run in Development Mode
You can run the GUI application immediately from source inside your repository directory by executing:
```bash
python coderun.py
```
*(By default, it will detect files in your current working directory. You can also pass a directory as a parameter, e.g., `python coderun.py C:\Projects\DSA`)*

---

## Step 3 — Compile Standalone Executable
To package the app into a single, highly optimized, standalone `.exe` without terminal windows popping up behind it:
```bash
python build_exe.py
```
This script automates PyInstaller configuration and generates `dist/coderun_gui.exe`.

---

## Step 4 — Install Globally on Windows (Recommended)
To run `coderun` from any command prompt folder globally:
1. Open a **standard command prompt (CMD)** inside the repository folder.
2. Run the automated installer batch script:
   ```cmd
   install.bat
   ```
This installer will:
- Clean up any legacy installations.
- Copy the newly built executable to `%LOCALAPPDATA%\coderun\coderun_gui.exe`.
- Create a global launcher batch script `coderun.bat` which inherits your active shell directory `%CD%` and forwards it directly to the GUI on startup.
- Append `%LOCALAPPDATA%\coderun` directly to your Windows **User PATH** using safe, non-truncating PowerShell APIs.

### Verify Global Launching
Once the installer finishes successfully:
1. Open a **brand new** CMD or PowerShell window.
2. Change directory (`cd`) to *any* folder containing C/C++ scripts (e.g. `cd C:\MyCode\DSA`).
3. Type:
   ```cmd
   coderun
   ```
The native dark GUI will instantly load, showing all your files in that directory!

---

## GUI Features & Keyboard Shortcuts

- **Interactive Folder Search**: A live filter search bar immediately filters files in the selected tab as you type.
- **Asynchronous Compile & Run**: Powered by `QProcess` streams, the application never freezes or blocks the GUI while compiling or executing code.
- **Interactive Stdin Console Bar**: A custom standard input field allows you to feed input variables directly to programs utilizing `scanf`, `cin`, or `std::getline` in real-time.
- **Performance Timing metrics**: Displays precise Compile Time and Execution Time accurate to 3 decimal places (e.g., `Compile: 0.245s | Run: 0.082s`).
- **Stop Action**: Instantly kill a running executable (ideal for resolving infinite loop bugs) by clicking **STOP** or hitting the `Escape` key.
- **Dynamic Auto-Refresh**: Uses a native file system watcher. If you add, delete, or rename C/C++ files inside the folder, the GUI updates automatically.
- **Open Folder Button**: Easily browse to other folders on your PC without having to restart the application.

### Hotkeys:
* **F5** or **Ctrl + R** — Compile and Run selected file.
* **F6** or **Ctrl + Shift + R** — Refresh file list manually.
* **Ctrl + L** — Clear output console.
* **Escape (Esc)** — Force kill running process.

---
---

# C/C++ Compiler Setup Guide (GCC & G++ on Windows)

This guide explains how to install and configure the GCC/G++ compiler on Windows using MSYS2.

---

# What We Are Installing

* GCC Compiler → for C programs
* G++ Compiler → for C++ programs
* MSYS2 → package manager and development environment for Windows

---

# Step 1 — Download MSYS2

Download MSYS2 from:

https://www.msys2.org/

Download the Windows installer.

Example:
msys2-x86_64-xxxx.exe

---

# Step 2 — Install MSYS2

Run the installer.

Recommended installation path:

```text
C:\msys64
```

Complete installation using default settings.

---

# Step 3 — Open MSYS2 UCRT64 Terminal

After installation:

Open:

**MSYS2 UCRT64**

from the Start Menu.

This terminal is used to install GCC/G++.

---

# Step 4 — Update MSYS2 Packages

Run:

```bash
pacman -Syu
```

Press:

```text
Y
```

If terminal closes after update:

* Reopen MSYS2 UCRT64
* Run:

```bash
pacman -Su
```

---

# Step 5 — Install GCC and G++

Run:

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc
```

Press:

```text
Y
```

This installs:

* gcc
* g++
* related build tools

---

# Step 6 — Verify Installation in MSYS2

Run:

```bash
gcc --version
```

and

```bash
g++ --version
```

If version information appears, installation is successful.

Example:

```text
gcc (Rev5, Built by MSYS2 project) 16.1.0
```

---

# Step 7 — Add GCC/G++ to Windows PATH

This step allows using gcc and g++ from normal CMD or terminal.

---

## Locate Compiler Folder

Compiler binaries are usually located at:

```text
C:\msys64\ucrt64\bin
```

Copy this path.

---

# Step 8 — Open Environment Variables

1. Search:

```text
environment variables
```

2. Open:

```text
Edit the system environment variables
```

3. Click:

```text
Environment Variables
```

---

# Step 9 — Edit PATH Variable

Under:

**System Variables**

1. Select:

```text
Path
```

2. Click:

```text
Edit
```

3. Click:

```text
New
```

4. Paste:

```text
C:\msys64\ucrt64\bin
```

5. Click:

* OK
* OK
* OK

to save changes.

---

# Step 10 — Restart Command Prompt

Close all CMD windows.

Open a new CMD window.

---

# Step 11 — Verify GCC/G++ in CMD

Run:

```bash
gcc --version
```

and

```bash
g++ --version
```

If version information appears:

* PATH is configured correctly
* GCC/G++ are ready to use

---

# Compile and Run a C Program

---

## Create a C File

Example:

```text
hello.c
```

Code:

```c
#include <stdio.h>

int main() {
    printf("Hello World");
    return 0;
}
```

---

# Compile the Program

Run:

```bash
gcc hello.c -o hello
```

This creates:

```text
hello.exe
```

---

# Run the Program

Run:

```bash
hello
```

or

```bash
.\hello
```

Output:

```text
Hello World
```

---

# Compile and Run a C++ Program

---

## Create a C++ File

Example:

```text
hello.cpp
```

Code:

```cpp
#include <iostream>
using namespace std;

int main() {
    cout << "Hello C++";
    return 0;
}
```

---

# Compile the Program

Run:

```bash
g++ hello.cpp -o hello
```

---

# Run the Program

Run:

```bash
hello
```

Output:

```text
Hello C++
```

---

# Useful Commands

## Show files in current folder

```bash
dir
```

---

## Change directory

```bash
cd foldername
```

---

## Go back one folder

```bash
cd ..
```

---

# Common Errors

---

## gcc is not recognized

Reason:

* PATH variable not configured correctly

Fix:

* Add:

```text
C:\msys64\ucrt64\bin
```

to Windows PATH.

---

## No such file or directory

Reason:

* Wrong folder
* Incorrect filename

Check files using:

```bash
dir
```

---

# Installed Components Summary

| Component     | Purpose                  |
| ------------- | ------------------------ |
| MSYS2         | Development environment  |
| GCC           | C compiler               |
| G++           | C++ compiler             |
| PATH Variable | Access compiler globally |

---

# Recommended Next Step

Install Visual Studio Code and use:

* GCC/G++
* VS Code terminal
* C/C++ extension

for a complete development setup.
