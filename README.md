# WIFITNT
<img src="./wifitnt-logo.jpg" width="150">

## 免责声明
**本工具仅供学习和安全测试用途，禁止用于任何非法用途。由此产生的任何法律责任与作者无关！**

### 简介
WIFITNT 是一个基于 Python 的 WiFi 密码多线程爆破工具，实现自动 MAC 更换，适用于Linux 平台。支持密码本爆破和随机密码生成两种模式，且支持多线程、多网卡同时破解。自动调度系统network-manager，效率更高。

### 环境要求
- linux
- Python 3.7 及以上
- 需以root身份运行
- 推荐使用支持更改 MAC 的 USB 无线网卡

### 安装依赖
```shell
pip install -r requirements.txt
```

### 使用方法
> [!IMPORTANT]
>pywifi库由于长期没有维护，代码存在BUG,如果需要，请修改修改 `_wifiutil_linux `部分代码为
>```
>    def connect(self, obj, network):
>        """Connect to the specified AP."""
>
>        network_summary = self._send_cmd_to_wpas(
>            obj['name'],
>            'LIST_NETWORKS',
>            True)
>        network_summary = network_summary[:-1].split('\n')
>        if len(network_summary) == 1:
>            return network
>
>        for l in network_summary[1:]:
>            values = l.split('\t')
>            if len(values) > 1 and values[1] == network.ssid:
>                network_summary = self._send_cmd_to_wpas(
>                    obj['name'],
>                    'SELECT_NETWORK {}'.format(values[0]),
>                    True)
>```                    
>我们同样提供了解决方案，优先调用系统命令，所以请确保安装好工具：
>```
>sudo apt update && sudo apt install network-manager
>```

1. 以或root身份运行 main.py。
2. 选择要使用的无线网卡编号。
3. 等待 WiFi 扫描完成，选择要破解的 WiFi。
4. 选择密码模式：
   - 1：使用密码本（需输入密码本文件路径，每行一个密码）
   - 2：随机生成密码（需输入密码长度、数量、字符集）
5. 程序自动多线程爆破，并每隔一分钟自动更换一次网卡 MAC 地址。
6. 破解成功会显示密码，失败会提示。

> [!TIP]
>如果需要手动生成密码本，我们提供了一个效率极高的生成程序，你可以手动编译它：
>```bash
>g++ create_password.cpp -o create_password
>```

### 注意事项
- 部分网卡不支持更改 MAC。
- 密码本建议每行一个密码，编码为 UTF-8。
- 若使用随机密码模式，字符集建议包含大小写字母和数字。
- 程序运行期间请勿手动断开/启用网卡。
- 请按照说明进行配置！