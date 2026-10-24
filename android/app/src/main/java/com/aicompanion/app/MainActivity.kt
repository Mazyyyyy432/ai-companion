package com.aicompanion.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.TextView

/**
 * 极简 WebView 外壳 + 一个「换地址」的小按钮。
 *
 * 换地址：点右上角的齿轮，改完立即生效，不用清应用数据。
 */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var root: FrameLayout

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        root = FrameLayout(this)

        web = WebView(this)
        web.layoutParams = FrameLayout.LayoutParams(
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
            userAgentString = userAgentString + " AICompanionApp/1.3"
        }
        web.webViewClient = WebViewClient()
        root.addView(web)

        // 右上角齿轮：随时改地址
        val gear = TextView(this).apply {
            text = "⚙"
            textSize = 17f
            setTextColor(Color.parseColor("#E8D9E2"))
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#66000000"))
            setOnClickListener { showUrlDialog(prefill = true) }
        }
        val lp = FrameLayout.LayoutParams(dp(38), dp(38), Gravity.TOP or Gravity.END).apply {
            topMargin = dp(46)
            rightMargin = dp(10)
        }
        root.addView(gear, lp)

        setContentView(root)

        ensureNotificationPermission()

        val saved = getSharedPreferences("app", Context.MODE_PRIVATE).getString("url", "").orEmpty()
        if (saved.isBlank()) showUrlDialog(prefill = false) else open(saved)
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun open(url: String) {
        web.loadUrl(url)
        startNotifyService()
    }

    private fun ensureNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100)
            }
        }
    }

    private fun startNotifyService() {
        try {
            val intent = Intent(this, NotifyService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
        } catch (t: Throwable) {
            android.util.Log.w("MainActivity", "service start failed: ${t.message}")
        }
    }

    private fun showUrlDialog(prefill: Boolean) {
        val current = getSharedPreferences("app", Context.MODE_PRIVATE).getString("url", "").orEmpty()
        val input = EditText(this).apply {
            hint = "https://desktop-xxxx.tailxxxx.ts.net"
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            setText(if (prefill && current.isNotBlank()) current else "https://")
            setSingleLine()
        }

        AlertDialog.Builder(this)
            .setTitle("电脑地址")
            .setMessage("在家：http://电脑IP:8000\n在外面：Tailscale 的 https 地址")
            .setView(input)
            .setCancelable(current.isNotBlank())
            .setPositiveButton("连接") { _, _ ->
                val url = input.text.toString().trim()
                if (url.isNotEmpty()) {
                    getSharedPreferences("app", Context.MODE_PRIVATE)
                        .edit().putString("url", url).apply()
                    open(url)
                }
            }
            .setNegativeButton(if (current.isNotBlank()) "取消" else "退出") { _, _ ->
                if (current.isBlank()) finish()
            }
            .show()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (this::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
