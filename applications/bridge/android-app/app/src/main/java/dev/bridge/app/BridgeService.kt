package dev.bridge.app

import android.app.*
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.os.BatteryManager
import android.os.IBinder
import androidx.core.app.NotificationCompat
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject

class BridgeService : Service() {
    private val channelId = "bridge_connection"
    override fun onBind(intent: Intent?): IBinder? = null
    override fun onCreate() {
        super.onCreate(); createChannel()
        startForeground(41, NotificationCompat.Builder(this, channelId).setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("Bridge conectado").setContentText("Presença e recebimentos ativos").setOngoing(true).build())
        connect()
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY
    private fun connect() {
        val prefs = BridgeClient.prefs(this); if (prefs.deviceId == null || prefs.authToken == null) { stopSelf(); return }
        val request = okhttp3.Request.Builder().url(BridgeClient.websocketUrl(prefs))
            .header("Authorization", "Bearer ${prefs.authToken}").build()
        BridgeClient.http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                val battery = (getSystemService(BATTERY_SERVICE) as BatteryManager).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                ws.send(JSONObject().put("type","ping").put("presence", JSONObject().put("network_type","mobile-or-lan").put("battery",battery).put("activity","Bridge Android")).toString())
            }
            override fun onMessage(ws: WebSocket, text: String) { handle(ws, JSONObject(text), prefs) }
            override fun onFailure(ws: WebSocket, error: Throwable, response: Response?) { android.os.Handler(mainLooper).postDelayed({ connect() }, 5000) }
        })
    }
    private fun handle(ws: WebSocket, message: JSONObject, prefs: BridgePrefs) {
        val type = message.optString("type"); val payload = message.optJSONObject("payload") ?: JSONObject()
        if (type == "command") {
            val result = if (!BridgeClient.verifyCommand(payload, prefs.serverPublicKey)) Pair("denied","assinatura inválida") else execute(payload)
            ws.send(JSONObject().put("type","command_result").put("payload",JSONObject().put("command_id",payload.optString("id")).put("status",result.first).put("detail",result.second)).toString())
        } else if (type == "message" || type.startsWith("transfer")) showNotice("Bridge", if (type == "message") "Novo ${payload.optString("kind")}" else "Transferência: ${payload.optString("file_name")}")
    }
    private fun execute(command: JSONObject): Pair<String,String> = when(command.optString("action")) {
        "ring" -> { RingtoneManager.getRingtone(this, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)).play(); Pair("completed","som iniciado") }
        "lock" -> { val manager=getSystemService(DEVICE_POLICY_SERVICE) as DevicePolicyManager; val admin=ComponentName(this,BridgeDeviceAdmin::class.java); if(manager.isAdminActive(admin)){ manager.lockNow(); Pair("completed","bloqueado") } else Pair("denied","Device Admin não autorizado") }
        "screen_start" -> { showNotice("Bridge", "Toque para aprovar o compartilhamento de tela", Intent(this,ScreenCaptureActivity::class.java)); Pair("needs_local_consent","aguardando MediaProjection") }
        else -> Pair("unsupported","ação não habilitada no agente Android")
    }
    private fun showNotice(title:String, text:String, intent:Intent?=null) {
        val builder=NotificationCompat.Builder(this,channelId).setSmallIcon(android.R.drawable.stat_notify_more).setContentTitle(title).setContentText(text).setAutoCancel(true)
        if(intent!=null) builder.setContentIntent(PendingIntent.getActivity(this,43,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify((System.currentTimeMillis()%100000).toInt(),builder.build())
    }
    private fun createChannel() { if(android.os.Build.VERSION.SDK_INT>=26) (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(NotificationChannel(channelId,"Bridge",NotificationManager.IMPORTANCE_DEFAULT)) }
}
