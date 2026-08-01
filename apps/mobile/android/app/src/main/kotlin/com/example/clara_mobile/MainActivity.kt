package com.example.clara_mobile

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val publicShareChannelName = "clara/public_share_link"
    private var publicShareChannel: MethodChannel? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        publicShareChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            publicShareChannelName,
        ).also { channel ->
            channel.setMethodCallHandler { call, result ->
                if (call.method == "initialLink") {
                    // The opaque URL is forwarded only to the in-memory Dart
                    // capability parser. It is never logged or persisted here.
                    result.success(intent?.dataString)
                } else {
                    result.notImplemented()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        // A warm link replaces the currently displayed public viewer only after
        // Dart validates the exact canonical URL. Do not log bearer tokens.
        publicShareChannel?.invokeMethod("link", intent.dataString)
    }
}
