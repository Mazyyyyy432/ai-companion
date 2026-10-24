package com.aicompanion.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText

/**
 * 极简 WebView 外壳：把本机跑的网页包成一个能装进手机的 App。
 *
 * 同时会拉起 NotifyService —— 那个前台服务自己保持一条 WebSocket，
 * 这样即使 App 在后台、屏幕锁着，她说的话也能用系统通知弹出来，
 * 完全不依赖 Google 的推送通道。
 *
 * 首次启动会让你填地址：
 *   在家：http://192.168.1.3:8000
 *   在外面：https://desktop-xxxx.tailxxxx.ts.net
 */
class MainActivity : Activity() {

    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        web = WebView(this)
        web.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            mediaPlaybackRequiresUserGesture = false
            userAgentString = userAgentString + " AICompanionApp/1.1"
        }
        web.webViewClient = WebViewClient()
        setContentView(web)

        ensureNotificationPermission()

        val prefs = getSharedPreferences("app", Context.MODE_PRIVATE)
        val saved = prefs.getString("url", "").orEmpty()
        if (saved.isBlank()) askForUrl() else {
            web.loadUrl(saved)
            startNotifyService()
        }
    }

    private fun ensureNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100)
            }
        }
    }

    private fun startNotifyService() {
        val url = getSharedPreferences("app", Context.MODE_PRIVATE).getString("url", "").orEmpty()
        if (url.isBlank()) return
        val intent = Intent(this, NotifyService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
    }

    private fun askForUrl() {
        val input = EditText(this).apply {
            hint = "https://desktop-xxxx.tailxxxx.ts.net"
            setText("http://")
            setSingleLine()
        }

        AlertDialog.Builder(this)
            .setTitle("电脑地址")
            .setMessage("填 Tailscale 的 https 地址（推荐），或家里的 http://电脑IP:8000")
            .setView(input)
            .setCancelable(false)
            .setPositiveButton("连接") { _, _ ->
                val url = input.text.toString().trim()
                if (url.isNotEmpty()) {
                    getSharedPreferences("app", Context.MODE_PRIVATE)
                        .edit().putString("url", url).apply()
                    web.loadUrl(url)
                    startNotifyService()
                }
            }
            .setNegativeButton("退出") { _, _ -> finish() }
            .show()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (this::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
