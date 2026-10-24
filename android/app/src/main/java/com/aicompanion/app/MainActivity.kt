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
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.TextView

/**
 * 极简 WebView 外壳。
 *
 * 出问题时不再是一片白：任何加载错误都会换成一张说明了原因的面板，
 * 上面写着「当前地址 / 错误码 / 怎么办」，还能一键改地址。
 */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var root: FrameLayout
    private lateinit var errorPanel: TextView
    private lateinit var gear: TextView

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
            userAgentString = userAgentString + " AICompanionApp/1.4"
        }
        web.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                hideError()
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame != true) return
                val code = if (Build.VERSION.SDK_INT >= 23) error?.errorCode else null
                val desc = if (Build.VERSION.SDK_INT >= 23) error?.description?.toString() else ""
                showError(code ?: -1, desc ?: "", request?.url?.toString() ?: currentUrl())
            }
        }
        root.addView(web)

        errorPanel = TextView(this).apply {
            visibility = TextView.GONE
            setBackgroundColor(Color.parseColor("#0B0709"))
            setTextColor(Color.parseColor("#E8D9E2"))
            textSize = 14f
            gravity = Gravity.CENTER
            val p = dp(24)
            setPadding(p, p, p, p)
        }
        root.addView(errorPanel, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ))

        gear = TextView(this).apply {
            text = "⚙"
            textSize = 17f
            setTextColor(Color.parseColor("#E8D9E2"))
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#88000000"))
            setOnClickListener { showUrlDialog(prefill = true) }
            setOnLongClickListener { showDiagnostics(); true }
        }
        root.addView(gear, FrameLayout.LayoutParams(dp(38), dp(38), Gravity.TOP or Gravity.END).apply {
            topMargin = dp(46)
            rightMargin = dp(10)
        })

        setContentView(root)
        ensureNotificationPermission()

        val saved = getSharedPreferences("app", Context.MODE_PRIVATE).getString("url", "").orEmpty()
        if (saved.isBlank()) showUrlDialog(prefill = false) else open(saved)
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun currentUrl(): String =
        getSharedPreferences("app", Context.MODE_PRIVATE).getString("url", "").orEmpty()

    private fun open(url: String) {
        hideError()
        web.loadUrl(url)
        startNotifyService()
    }

    private fun showError(code: Int, desc: String, url: String) {
        if (!this::errorPanel.isInitialized) return
        val hint = when (code) {
            -2 -> "网络连不上。检查一下地址，或者手机上的网络。"
            -6 -> "连不上文件。"
            -8 -> "连接超时。多半是这条线路太慢（比如 Tailscale 走了海外中继）。"
            -10 -> "协议不支持。"
            -11 -> "服务器拒绝了连接。"
            -12 -> "SSL 证书有问题。"
            -13 -> "拒绝连接。"
            else -> "加载失败。"
        }
        errorPanel.text = buildString {
            append("页面没有加载出来\n\n")
            append(hint).append("\n\n")
            append("当前地址\n").append(url.ifBlank { "（空）" }).append("\n\n")
            append("错误码 ").append(code)
            if (desc.isNotBlank()) append("：").append(desc)
            append("\n\n点右上角 ⚙ 换地址\n长按 ⚙ 看诊断")
        }
        errorPanel.visibility = TextView.VISIBLE
        if (this::gear.isInitialized) gear.bringToFront()
    }

    private fun hideError() {
        if (this::errorPanel.isInitialized) errorPanel.visibility = TextView.GONE
    }

    private fun showDiagnostics() {
        val pkg = try {
            WebView.getCurrentWebViewPackage()
        } catch (t: Throwable) {
            null
        }
        val webviewInfo = if (pkg != null) "${pkg.packageName} ${pkg.versionName}" else "取不到 WebView 版本"
        AlertDialog.Builder(this)
            .setTitle("诊断")
            .setMessage(
                "地址：${currentUrl().ifBlank { "（空）" }}\n" +
                "WebView：$webviewInfo\n" +
                "系统：Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
            )
            .setPositiveButton("改地址") { _, _ -> showUrlDialog(prefill = true) }
            .setNegativeButton("关闭", null)
            .show()
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
        val current = currentUrl()
        val input = EditText(this).apply {
            hint = "http://192.168.1.3:8000"
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            setText(if (prefill && current.isNotBlank()) current else "http://")
            setSingleLine()
        }

        AlertDialog.Builder(this)
            .setTitle("电脑地址")
            .setMessage("同一个 Wi-Fi 用 http://电脑IP:8000\n出门用 Tailscale 的 https 地址")
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
