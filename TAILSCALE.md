# 出门也能用 + 消息提醒（Tailscale 步骤）

目标：手机在外面（4G/5G、别人家 Wi-Fi）也能打开这个页面，并且能收到锁屏通知。
原理：Tailscale 把你手机和电脑放进同一个加密的私有网络，手机访问电脑就像在家里一样。不开端口、不暴露到公网、不经过第三方中转内容。

整个过程大概 10 分钟，全部免费。

---

## 一、电脑上装 Tailscale

1. 打开 https://tailscale.com/download/windows 下载安装
2. 装完点托盘图标 → **Log in**，用 Google / 微软 / GitHub 账号登录都行
3. 登录后记下这台电脑的设备名（托盘菜单里能看到，类似 `desktop-abc123`）

## 二、手机上装 Tailscale

- iPhone：App Store 搜 **Tailscale**
- 安卓：应用商店或 https://tailscale.com/download/android

**用同一个账号登录**，打开开关。

## 三、打开 HTTPS（关键，通知功能必须）

1. 电脑浏览器打开 https://login.tailscale.com/admin/dns
2. 确认 **MagicDNS** 是 Enabled
3. 找到 **HTTPS Certificates**，点 **Enable**

## 四、让电脑把这个服务发布到 443 端口

在电脑上开一个 PowerShell（不用管理员），执行：

```powershell
tailscale serve --bg http://127.0.0.1:8000
```

它会打印出你的地址，形如：

```
https://desktop-abc123.tailxxxx.ts.net
```

**这个地址就是你以后在手机上用的地址**（不用加 :8000）。

> `--bg` 表示后台常驻，重启电脑后依然生效。想关掉用 `tailscale serve reset`。

## 五、手机上打开并装成 App

1. 手机浏览器打开上面那个 `https://....ts.net` 地址
2. iPhone：分享 → **添加到主屏幕**（必须做这步，iOS 只有装到主屏的网页才能收推送）
3. 安卓：菜单 → **添加到主屏幕 / 安装应用**
4. 从主屏幕图标打开 → 点右上角 **🔔** → 允许通知
5. 看到"通知开好了"并且收到一条测试通知，就成功了

之后把手机切到 4G、锁屏，让 AI 过一分钟主动说话，应该能收到通知。

---

## 常见问题

**手机在外面打不开**
先确认手机 Tailscale 开关是开的（iOS 上是一个 VPN 图标）。Tailscale 在后台可能被系统杀掉，需要允许它后台运行。

**打开是 HTTPS 但提示不安全**
说明 `tailscale serve` 没跑起来，或者第四节没做。重新执行一次看输出。

**通知时有时无**
iOS 的网页推送本身是"尽力而为"，锁屏久了可能被系统合并或延迟。要绝对可靠只能做原生 App（要开发者账号），这个方案是免费能拿到的最好效果。

**担心隐私**
Tailscale 是点对点加密，内容不经过他们的服务器，只有登录和密钥交换走他们的协调服务器。你的聊天记录、玩具控制数据都只在你自己两台设备之间。
