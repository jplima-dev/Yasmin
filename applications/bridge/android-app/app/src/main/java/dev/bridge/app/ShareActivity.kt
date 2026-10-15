package dev.bridge.app

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch

class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val text = intent.getStringExtra(Intent.EXTRA_TEXT)
        if (text == null) { Toast.makeText(this,"Arquivos binários serão enviados pelo fluxo de upload do Bridge; esta etapa envia texto/links.",Toast.LENGTH_LONG).show(); finish(); return }
        MainScope().launch {
            try { BridgeClient.sendText(this@ShareActivity,text,if(text.startsWith("http")) "link" else "text"); Toast.makeText(this@ShareActivity,"Enviado pelo Bridge",Toast.LENGTH_SHORT).show() }
            catch(error:Exception){ Toast.makeText(this@ShareActivity,error.message,Toast.LENGTH_LONG).show() }
            finally { finish() }
        }
    }
}

