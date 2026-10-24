package com.aicompanion.app

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText

/**
 * 极简 WebView 外壳：把本机跑的网页包成一个能装进手机的 App。
 *
 * 为什么需要它：部分手机浏览器不给「添加到主屏幕」，也有人的系统版本太旧。
 * 这个壳子只做一件事——记住一个地址，然后全屏打开它。
 *
 * 首次启动会让你填地址：
 *   在家：http://192.168.1.3:8000
 *   在外面：http://desktop-xxxx.tailxxxx.ts.net
 * 想改地址：长按标题栏位置没做，直接清除应用数据即可重新填写。
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
            userAgentString = userAgentString + " AICompanionApp/1.0"
        }
        web.webViewClient = WebViewClient()
        setContentView(web)

        val prefs = getSharedPreferences("app", Context.MODE_PRIVATE)
        val saved = prefs.getString("url", "").orEmpty()
        if (saved.isBlank()) askForUrl() else web.loadUrl(saved)
    }

    private fun askForUrl() {
        val input = EditText(this).apply {
            hint = "http://192.168.1.3:8000"
            setText("http://")
            setSingleLine()
        }

        AlertDialog.Builder(this)
            .setTitle("电脑地址")
            .setMessage("在家填 http://电脑IP:8000\n在外面填 Tailscale 给的地址")
            .setView(input)
            .setCancelable(false)
            .setPositiveButton("连接") { _, _ ->
                val url = input.text.toString().trim()
                if (url.isNotEmpty()) {
                    getSharedPreferences("app", Context.MODE_PRIVATE)
                        .edit().putString("url", url).apply()
                    web.loadUrl(url)
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
