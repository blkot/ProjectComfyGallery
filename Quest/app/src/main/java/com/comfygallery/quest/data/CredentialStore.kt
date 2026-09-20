package com.comfygallery.quest.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class CredentialStore(context: Context) {
    private val preferences = context.getSharedPreferences("connection", Context.MODE_PRIVATE)
    private val alias = "comfygallery.quest.connection"
    val address: String get() = preferences.getString("address", "") ?: ""

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }

    class EncryptedToken(val ciphertext: String, val iv: String)

    fun encrypt(token: String): EncryptedToken {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val data = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        return EncryptedToken(Base64.encodeToString(data, Base64.NO_WRAP), Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
    }

    // Commit the encrypted result on the state owner's thread, so canceled connection attempts
    // cannot persist credentials after Disconnect or a newer connection has taken ownership.
    fun save(address: String, token: EncryptedToken) {
        preferences.edit().putString("address", address).putString("ciphertext", token.ciphertext)
            .putString("iv", token.iv).apply()
    }

    fun token(): String? {
        val encoded = preferences.getString("ciphertext", null) ?: return null
        val iv = preferences.getString("iv", null) ?: return null
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
                init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
            }
            String(cipher.doFinal(Base64.decode(encoded, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (_: Exception) {
            clear()
            null
        }
    }

    fun clear() { preferences.edit().remove("ciphertext").remove("iv").apply() }
}
