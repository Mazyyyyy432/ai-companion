package com.aicompanion.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * 后台提醒服务。
 *
 * 安卓的网页推送走 Google 的 FCM，国内网络连不上，所以这里自己保持一条
 * WebSocket 到电脑，收到她说的话就用系统通知弹出来——完全不依赖 Google。
 */
class NotifyService : Service() {

    private val handler = Handler(Looper.getMainLooper())
    private var ws: WebSocket? = null
    private var stopped = false
    private var foregroundStarted = false

    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        safe { createChannel() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            safe { stopForeground(true) }
            stopSelf()
            return START_NOT_STICKY
        }

        // 先把自己变成前台服务；失败也绝不能让进程崩掉，否则 App 看起来就是“打不开”
        safe {
            startForeground(NOTIFY_ID_ONGOING, ongoingNotification())
            foregroundStarted = true
        }

        safe { connect() }
        return START_STICKY
    }

    private fun wsUrl(): String? {
        val raw = getSharedPreferences("app", Context.MODE_PRIVATE)
            .getString("url", "")?.trim().orEmpty()
        if (raw.isEmpty()) return null

        val base = raw.trimEnd('/')
        return when {
            base.startsWith("https://") -> base.replaceFirst("https://", "wss://") + "/ws"
            base.startsWith("http://") -> base.replaceFirst("http://", "ws://") + "/ws"
            else -> "ws://$base/ws"
        }
    }

    private fun connect() {
        val url = wsUrl() ?: return
        ws?.cancel()
        ws = client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                safe { webSocket.send("""{"type":"focus","visible":false}""") }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                safe {
                    val obj = JSONObject(text)
                    if (obj.optString("type") == "message" &&
                        obj.optString("role") == "assistant" &&
                        !obj.optBoolean("echo", false)
                    ) {
                        val body = obj.optString("text", "").trim()
                        if (body.isNotEmpty()) notifyMessage(body)
                    }
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (!stopped) reconnectLater()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (!stopped) reconnectLater()
            }
        })
    }

    private fun reconnectLater() {
        if (stopped) return
        handler.removeCallbacksAndMessages(null)
        handler.postDelayed({ safe { connect() } }, 15_000)
    }

    private fun notifyMessage(text: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val name = getSharedPreferences("app", Context.MODE_PRIVATE)
            .getString("name", "她") ?: "她"

        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val b = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_MSG)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        val n = b
            .setContentTitle(name)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setContentIntent(open)
            .build()

        nm.notify(Math.abs(text.hashCode()), n)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        val msg = NotificationChannel(CHANNEL_MSG, "她说的话", NotificationManager.IMPORTANCE_HIGH)
        msg.description = "她主动发来的消息"
        nm.createNotificationChannel(msg)

        val bg = NotificationChannel(CHANNEL_ONGOING, "后台连接", NotificationManager.IMPORTANCE_LOW)
        bg.description = "保持和电脑的连接，用来接收消息"
        nm.createNotificationChannel(bg)
    }

    private fun ongoingNotification(): Notification {
        val stop = PendingIntent.getService(
            this, 1,
            Intent(this, NotifyService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ONGOING)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }

        // 注意：不能传 null 图标，某些机型会直接抛异常把服务崩掉
        val action = Notification.Action.Builder(
            Icon.createWithResource(this, android.R.drawable.ic_menu_close_clear_cancel),
            "断开",
            stop
        ).build()

        return builder
            .setContentTitle("她")
            .setContentText("后台连接中")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .addAction(action)
            .build()
    }

    override fun onDestroy() {
        stopped = true
        handler.removeCallbacksAndMessages(null)
        safe { ws?.close(1000, "bye") }
        ws = null
        super.onDestroy()
    }

    /** 任何一处异常都不许冒泡，避免整个进程被系统判定为崩溃 */
    private inline fun safe(block: () -> Unit) {
        try {
            block()
        } catch (t: Throwable) {
            android.util.Log.w("NotifyService", "ignored: ${t.message}")
        }
    }

    companion object {
        const val CHANNEL_MSG = "companion_messages"
        const val CHANNEL_ONGOING = "companion_service"
        const val NOTIFY_ID_ONGOING = 1001
        const val ACTION_STOP = "com.aicompanion.app.STOP"
    }
}
