package dev.bridge.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.widget.Toast

class ScreenCaptureActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val manager=getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        startActivityForResult(manager.createScreenCaptureIntent(),71)
    }
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        Toast.makeText(this,if(resultCode==RESULT_OK) "Consentimento concedido; encoder/WebRTC é a próxima etapa isolada." else "Captura recusada",Toast.LENGTH_LONG).show()
        // O protótipo encerra aqui de propósito: nunca persiste token de captura nem inicia silenciosamente.
        finish()
    }
}

