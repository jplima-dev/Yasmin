package dev.bridge.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.security.spec.ECGenParameterSpec
import java.util.UUID
import java.util.concurrent.TimeUnit

data class BridgePrefs(val server: String, val deviceId: String?, val serverPublicKey: String?, val authToken: String?)

object BridgeClient {
    val http = OkHttpClient.Builder().pingInterval(25, TimeUnit.SECONDS).build()
    private val jsonType = "application/json".toMediaType()

    fun prefs(context: Context): BridgePrefs {
        val values = context.getSharedPreferences("bridge", Context.MODE_PRIVATE)
        return BridgePrefs(values.getString("server", "http://10.0.2.2:8876")!!,
            values.getString("deviceId", null), values.getString("serverPublicKey", null),
            values.getString("authToken", null))
    }

    fun save(context: Context, server: String, deviceId: String, serverKey: String, authToken: String) {
        context.getSharedPreferences("bridge", Context.MODE_PRIVATE).edit()
            .putString("server", server.trimEnd('/')).putString("deviceId", deviceId)
            .putString("serverPublicKey", serverKey).putString("authToken", authToken).apply()
    }

    private fun request(server: String, path: String, method: String = "GET", body: JSONObject? = null, token: String? = null): JSONObject {
        val builder = Request.Builder().url(server.trimEnd('/') + "/api" + path)
        if (token != null) builder.header("Authorization", "Bearer $token")
        if (method != "GET") builder.method(method, (body ?: JSONObject()).toString().toRequestBody(jsonType))
        http.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) error("Bridge ${response.code}: $text")
            return if (text.isBlank()) JSONObject() else JSONObject(text)
        }
    }

    private fun devicePublicKey(): String {
        val alias = "bridge-device-identity"
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (!store.containsAlias(alias)) {
            val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
            generator.initialize(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
                .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                .setDigests(KeyProperties.DIGEST_SHA256).build())
            generator.generateKeyPair()
        }
        return Base64.encodeToString(store.getCertificate(alias).publicKey.encoded, Base64.URL_SAFE or Base64.NO_WRAP)
    }

    suspend fun beginPair(server: String, name: String): JSONObject = withContext(Dispatchers.IO) {
        val identity = request(server, "/system/identity")
        val registration = JSONObject().put("name", name).put("device_type", "android")
            .put("public_key", devicePublicKey())
            .put("permissions", JSONObject().put("remote_ring", true).put("remote_lock", false)
                .put("screen_share", false).put("remote_actions", false).put("photos", true).put("clipboard", true))
        request(server, "/pairing/request", "POST", registration).put("server_public_key", identity.getString("public_key"))
    }

    suspend fun confirmPair(context: Context, server: String, pair: JSONObject, code: String) = withContext(Dispatchers.IO) {
        val confirmation = request(server, "/pairing/${pair.getString("device_id")}/confirm", "POST", JSONObject().put("code", code))
        save(context, server, pair.getString("device_id"), pair.getString("server_public_key"), confirmation.getString("auth_token"))
    }

    suspend fun sendText(context: Context, text: String, kind: String = "text") = withContext(Dispatchers.IO) {
        val prefs = prefs(context); val ownId = prefs.deviceId ?: error("Android ainda não pareado")
        val token = prefs.authToken ?: error("Pareie o Android novamente para autenticar")
        val devicesRequest = Request.Builder().url(prefs.server + "/api/devices")
            .header("Authorization", "Bearer $token").build()
        val devices = http.newCall(devicesRequest).execute().use { JSONArray(it.body?.string().orEmpty()) }
        val target = (0 until devices.length()).map { devices.getJSONObject(it) }
            .firstOrNull { it.getString("id") != ownId } ?: error("Nenhum destino pareado")
        request(prefs.server, "/messages", "POST", JSONObject().put("kind", kind).put("source_id", ownId)
            .put("target_id", target.getString("id")).put("content", text).put("behavior", "ask"), token)
    }

    fun websocketUrl(prefs: BridgePrefs): String = prefs.server.replace("https://", "wss://")
        .replace("http://", "ws://") + "/ws/${prefs.deviceId}"

    fun verifyCommand(command: JSONObject, publicKeyRaw: String?): Boolean {
        // O Core fornece Ed25519 bruto; o prefixo X.509 abaixo é o SubjectPublicKeyInfo de Ed25519.
        if (publicKeyRaw == null || !command.has("signature")) return false
        return try {
            val raw = Base64.decode(publicKeyRaw, Base64.URL_SAFE)
            val prefix = byteArrayOf(0x30,0x2a,0x30,0x05,0x06,0x03,0x2b,0x65,0x70,0x03,0x21,0x00)
            val key = KeyFactory.getInstance("Ed25519").generatePublic(X509EncodedKeySpec(prefix + raw))
            val signature = Signature.getInstance("Ed25519"); signature.initVerify(key)
            val unsigned = JSONObject(command.toString()); val encoded = Base64.decode(unsigned.remove("signature") as String, Base64.URL_SAFE)
            signature.update(canonical(unsigned).toByteArray()); signature.verify(encoded)
        } catch (_: Exception) { false }
    }

    private fun canonical(value: Any?): String = when (value) {
        is JSONObject -> value.keys().asSequence().toList().sorted().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + canonical(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") { canonical(value.get(it)) }
        JSONObject.NULL, null -> "null"
        is String -> JSONObject.quote(value)
        is Boolean, is Number -> value.toString()
        else -> JSONObject.quote(value.toString())
    }
}
