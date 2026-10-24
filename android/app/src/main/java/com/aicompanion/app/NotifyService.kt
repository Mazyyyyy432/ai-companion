package com.aicompanion.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
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
 * 为什么不用 Web Push：安卓的网页推送走 Google 的 FCM，国内网络连不上，
 * 注册时直接报 "push service error"。所以这里自己保持一条 WebSocket 到电脑，
 * 收到她说的话就用系统通知弹出来——完全不依赖 Google。
 *
 * 代价是需要一个常驻通知（安卓对前台服务的硬性要求）。
 */
class NotifyService : Service() {

    private val handler = Handler(Looper.getMainLooper())
    private var ws: WebSocket? = null
    private var stopped = false

    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(NOTIFY_ID_ONGOING, ongoingNotification())
        connect()
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
                webSocket.send("""{"type":"focus","visible":false}""")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val obj = JSONObject(text)
                    if (obj.optString("type") == "message" &&
                        obj.optString("role") == "assistant" &&
                        !obj.optBoolean("echo", false)
                    ) {
                        val body = obj.optString("text", "").trim()
                        if (body.isNotEmpty()) notifyMessage(body)
                    }
                } catch (_: Exception) {
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
        handler.postDelayed({ connect() }, 15_000)
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

        val n = Notification.Builder(this, CHANNEL_MSG)
            .setContentTitle(name)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setContentIntent(open)
            .build()

        nm.notify(text.hashCode(), n)
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

        return builder
            .setContentTitle("她")
            .setContentText("后台连接中")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, "断开", stop).build())
            .build()
    }

    override fun onDestroy() {
        stopped = true
        handler.removeCallbacksAndMessages(null)
        ws?.close(1000, "bye")
        ws = null
        super.onDestroy()
    }

    companion object {
        const val CHANNEL_MSG = "companion_messages"
        const val CHANNEL_ONGOING = "companion_service"
        const val NOTIFY_ID_ONGOING = 1001
        const val ACTION_STOP = "com.aicompanion.app.STOP"
    }
}
