package dev.bridge.app

import android.Manifest
import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : AppCompatActivity() {
    private val scope = MainScope()
    private var pending: JSONObject? = null
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 20)
        val server = EditText(this).apply { hint = "http://IP-DO-PC:8876"; setText(BridgeClient.prefs(this@MainActivity).server) }
        val name = EditText(this).apply { hint = "Nome do celular"; setText(Build.MODEL) }
        val code = EditText(this).apply { hint = "Código de seis dígitos do Core"; inputType = android.text.InputType.TYPE_CLASS_NUMBER; visibility = android.view.View.GONE }
        val saved = BridgeClient.prefs(this)
        status = TextView(this).apply { text = if (saved.deviceId != null && saved.authToken != null) "Pareado: ${saved.deviceId}" else "Ainda não pareado"; setPadding(0,24,0,24) }
        val pair = Button(this).apply { text = "Gerar código de pareamento"; setOnClickListener { scope.launch {
            try { pending = BridgeClient.beginPair(server.text.toString(), name.text.toString()); code.visibility = android.view.View.VISIBLE; status.text = "Veja o código na janela do Bridge Core e digite abaixo." }
            catch (error: Exception) { status.text = error.message }
        } } }
        val confirm = Button(this).apply { text = "Confirmar código"; setOnClickListener { scope.launch {
            try { BridgeClient.confirmPair(this@MainActivity, server.text.toString(), pending ?: error("Gere o código primeiro"), code.text.toString()); status.text = "Pareamento concluído"; startBridge() }
            catch (error: Exception) { status.text = error.message }
        } } }
        val usage = Button(this).apply { text = "Autorizar atividade de apps"; setOnClickListener { startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) } }
        val admin = Button(this).apply { text = "Autorizar bloqueio remoto"; setOnClickListener {
            startActivity(Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, ComponentName(this@MainActivity, BridgeDeviceAdmin::class.java)).putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, "Permite bloquear somente quando você solicitar pelo Bridge."))
        } }
        val screen = Button(this).apply { text = "Iniciar tela com consentimento"; setOnClickListener { startActivity(Intent(this@MainActivity, ScreenCaptureActivity::class.java)) } }
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(42,50,42,42); addView(TextView(context).apply { text="BRIDGE"; textSize=30f }); addView(server); addView(name); addView(status); addView(pair); addView(code); addView(confirm); addView(usage); addView(admin); addView(screen) }
        setContentView(ScrollView(this).apply { addView(layout, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)) })
        if (saved.deviceId != null && saved.authToken != null) startBridge()
    }

    private fun startBridge() { ContextCompat.startForegroundService(this, Intent(this, BridgeService::class.java)) }
}
