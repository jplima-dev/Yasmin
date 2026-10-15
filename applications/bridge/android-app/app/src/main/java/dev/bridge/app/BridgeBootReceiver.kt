package dev.bridge.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

class BridgeBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val prefs = BridgeClient.prefs(context)
        if (prefs.deviceId != null && prefs.authToken != null) {
            ContextCompat.startForegroundService(context, Intent(context, BridgeService::class.java))
        }
    }
}

