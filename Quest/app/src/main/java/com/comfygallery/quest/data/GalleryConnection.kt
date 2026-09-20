package com.comfygallery.quest.data

import java.io.IOException
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

class GalleryConnection(address: String, token: String) {
    val base: HttpUrl
    private val bearer = token.trim()

    init {
        require(bearer.isNotEmpty() && bearer.none { it.isISOControl() }) { "Enter a valid API token." }
        val parsed = address.trim().toHttpUrl()
        require(parsed.username.isEmpty() && parsed.password.isEmpty() && parsed.query == null && parsed.fragment == null) {
            "Use a server URL without credentials, query, or fragment."
        }
        base = parsed.newBuilder().encodedPath(parsed.encodedPath.trimEnd('/') + "/").build()
    }

    fun resolve(path: String): HttpUrl {
        require(!path.startsWith("//")) { "Invalid media URL." }
        val url = if (path.startsWith("http://") || path.startsWith("https://")) {
            path.toHttpUrl()
        } else {
            val normalized = path.removePrefix("/")
            val prefix = base.encodedPath.trim('/')
            if (prefix.isNotEmpty() && normalized.startsWith("$prefix/")) {
                base.resolve("/$normalized")!!
            } else {
                base.resolve(normalized)!!
            }
        }
        require(owns(url)) { "Media URL must stay on the configured gallery." }
        return url
    }

    fun owns(url: HttpUrl): Boolean = url.scheme == base.scheme && url.host == base.host &&
        url.port == base.port && url.username.isEmpty() && url.password.isEmpty() &&
        url.encodedPath.startsWith(base.encodedPath)

    fun client(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .followRedirects(false)
        .followSslRedirects(false)
        .addInterceptor { chain ->
            if (!owns(chain.request().url)) throw IOException("Resource is outside the configured gallery.")
            chain.proceed(chain.request().newBuilder().header("Authorization", "Bearer $bearer").build())
        }.build()

    override fun toString(): String = "GalleryConnection(credentials=redacted)"
}
